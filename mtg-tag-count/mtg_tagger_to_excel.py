#!/usr/bin/env python3
"""
MTG Tag, Type & Deck Export → Single Excel File with Selection, Images & Excel-Based Cumulative Counts

This script takes lists of MTG card names, target tags, target types,
and a JSON file specifying minimum and optional maximum counts for tags and types (with optional exclusions).
It fetches each card's taggings via Scryfall Tagger's GraphQL endpoint (with ancestors)
and its type line & image URIs via the Scryfall API, using a local cache to avoid refetching.
Then it:
  1. Evaluates every card, marking whether it's Selected and flags cards with NoRelevantTags.
  2. Adds an empty "Image" column, then inserts card images into that column cell (sized larger), keeping names separate.
  3. Applies boolean coloring and dynamic COUNTIFS formulas for cumulative selected counts per tag.

Usage:
    python mtg_tagger_to_excel.py \
      --cards cards.txt --tags tags.txt --types types.txt \
      --counts counts.json --output deck.xlsx [--delay 0.1]

Requirements:
    pip install requests beautifulsoup4 pandas openpyxl
"""
import argparse
import io
import time
import json
import requests
from bs4 import BeautifulSoup
import pandas as pd
import shelve

from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import PatternFill
from openpyxl.formatting.rule import CellIsRule
from openpyxl.utils import get_column_letter

# Constants
USER_AGENT = "MTGTagCounter/1.0"
GRAPHQL_URL = "https://tagger.scryfall.com/graphql"
CACHE_PATH = "mtg_cache.db"

# Initialize cache and session
db = shelve.open(CACHE_PATH)
session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

# GraphQL to fetch taggings
GRAPHQL_QUERY = """
query FetchCard($set: String!, $number: String!) {
  card: cardBySet(set: $set, number: $number) {
    set
    collectorNumber
    taggings(moderatorView: false) {
      tag { name status ancestorTags { name status } }
    }
  }
}
"""


def get_card_info(card_name):
    key = f"info:{card_name.lower()}"
    if key in db:
        return db[key]
    resp = session.get(
        "https://api.scryfall.com/cards/named", params={"exact": card_name}
    )
    resp.raise_for_status()
    info = resp.json()
    db[key] = info
    return info


def get_tagger_tags(set_code, collector_number):
    key = f"tags:{set_code.lower()}:{collector_number}"
    if key in db:
        return set(db[key])
    resp = session.get(
        f"https://tagger.scryfall.com/card/{set_code}/{collector_number}"
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    token = soup.find("meta", {"name": "csrf-token"})["content"]
    headers = {"X-CSRF-Token": token, "Content-Type": "application/json"}
    payload = {
        "query": GRAPHQL_QUERY,
        "variables": {"set": set_code, "number": collector_number},
    }
    r = session.post(GRAPHQL_URL, json=payload, headers=headers)
    r.raise_for_status()
    data = r.json().get("data", {}).get("card", {}) or {}
    tags = set()
    for t in data.get("taggings", []):
        tg = t.get("tag", {})
        if tg.get("status") != "GOOD_STANDING":
            continue
        nm = tg.get("name", "").lower().strip()
        if nm:
            tags.add(nm)
        for anc in tg.get("ancestorTags", []):
            if anc.get("status") == "GOOD_STANDING":
                an = anc.get("name", "").lower().strip()
                if an:
                    tags.add(an)
    db[key] = list(tags)
    return tags


def fetch_image_bytes(info):
    if info.get("image_uris"):
        url = info["image_uris"].get("normal")
    elif info.get("card_faces"):
        url = info["card_faces"][0].get("image_uris", {}).get("normal")
    else:
        return None
    r = session.get(url)
    r.raise_for_status()
    return io.BytesIO(r.content)


def build_deck_indices(df, rules, exclude_map):
    tally = {k: 0 for k in rules}
    selected = []
    for idx, row in df.iterrows():
        if not any(row.get(k, False) for k in rules):
            continue
        if any(
            rules[k].get("max") is not None
            and row.get(k, False)
            and tally[k] >= rules[k]["max"]
            for k in rules
        ):
            continue
        primary = [
            k
            for k in rules
            if tally[k] < rules[k]["min"]
            and row.get(k, False)
            and not any(row.get(ex, False) for ex in exclude_map.get(k, []))
        ]
        if not primary:
            continue
        selected.append(idx)
        for k in primary:
            tally[k] += 1
        extras = [
            k
            for k in rules
            if k not in primary
            and row.get(k, False)
            and rules[k].get("max") is not None
            and tally[k] < rules[k]["max"]
        ]
        for k in extras:
            tally[k] += 1
        if all(tally[k] >= rules[k]["min"] for k in rules):
            break
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", default="cards.txt")
    parser.add_argument("--tags", default="tags.txt")
    parser.add_argument("--types", default="types.txt")
    parser.add_argument("--counts", default="counts.json")
    parser.add_argument("--output", default="deck.xlsx")
    parser.add_argument("--delay", type=float, default=0.1)
    args = parser.parse_args()

    with open(args.cards) as f:
        cards = [l.strip() for l in f if l.strip()]
    with open(args.tags) as f:
        t_tags = [l.strip().lower() for l in f if l.strip()]
    with open(args.types) as f:
        t_types = [l.strip().lower() for l in f if l.strip()]
    counts = json.load(open(args.counts))

    rules = {}
    for k, v in counts.get("tags", {}).items():
        if isinstance(v, dict):
            rules[k] = {"min": v.get("min", 0), "max": v.get("max")}
        else:
            rules[k] = {"min": v, "max": None}
    for k, v in counts.get("types", {}).items():
        if isinstance(v, dict):
            rules[k] = {"min": v.get("min", 0), "max": v.get("max")}
        else:
            rules[k] = {"min": v, "max": None}
    exclude_map = {k: list(v) for k, v in counts.get("exclude", {}).items()}

    rows = []
    imgs = []
    for card in cards:
        info = get_card_info(card)
        tags = get_tagger_tags(info["set"], info["collector_number"])
        types = set(info.get("type_line", "").lower().replace("—", "").split())
        row = {"Image": "", "Card": card}
        for t in t_tags:
            row[t] = t in tags
        for t in t_types:
            row[t] = t in types
        rows.append(row)
        imgs.append(fetch_image_bytes(info))
        time.sleep(args.delay)

    df = pd.DataFrame(rows)
    df.index = range(1, len(df) + 1)
    df.index.name = "Index"

    selected_idxs = build_deck_indices(df, rules, exclude_map)
    df["Selected"] = df.index.isin(selected_idxs)
    df["NoRelevant"] = ~df[[*t_tags, *t_types]].any(axis=1)

    output = args.output
    df.to_excel(output, sheet_name="Deck", index_label="Index")
    wb = load_workbook(output)
    ws = wb["Deck"]

    # Anchor images to 'Image' column
    img_col_idx = df.columns.get_loc("Image") + 2
    img_col_letter = get_column_letter(img_col_idx)
    ws.column_dimensions[img_col_letter].width = 20

    for row_idx, img_bytes in enumerate(imgs, start=2):
        if img_bytes:
            img = XLImage(img_bytes)
            img.width = 160
            img.height = 224
            anchor_cell = f"{img_col_letter}{row_idx}"
            img.anchor = anchor_cell
            ws.add_image(img)
            ws.row_dimensions[row_idx].height = 180

    green = PatternFill("solid", fgColor="C6EFCE")
    red = PatternFill("solid", fgColor="FFC7CE")
    bool_cols = t_tags + t_types + ["Selected", "NoRelevant"]
    for col in bool_cols:
        col_idx = df.columns.get_loc(col) + 2
        letter = get_column_letter(col_idx)
        rng = f"{letter}2:{letter}{len(df) + 1}"
        ws.conditional_formatting.add(rng, CellIsRule("equal", ["TRUE"], green))
        ws.conditional_formatting.add(rng, CellIsRule("equal", ["FALSE"], red))

    sel_col = get_column_letter(df.columns.get_loc("Selected") + 2)
    base_cols = len(df.columns)
    for i, tag in enumerate(t_tags):
        colp = base_cols + 2 + i
        ws.cell(row=1, column=colp, value=f"{tag}_cum")
        orig_letter = get_column_letter(df.columns.get_loc(tag) + 2)
        for r in range(2, len(df) + 2):
            ws.cell(
                row=r,
                column=colp,
                value=f"=COUNTIFS(${sel_col}$2:${sel_col}${r},TRUE,${orig_letter}$2:${orig_letter}${r},TRUE)",
            )

    # Create an actual Excel Table (with headers, filters, and banded rows)
    from openpyxl.worksheet.table import Table, TableStyleInfo

    # Total columns in workbook: df columns + index column + cumulative columns
    total_cols = df.shape[1] + 1 + len(t_tags)
    end_col = get_column_letter(total_cols)
    table_ref = f"A1:{end_col}{len(df)+1}"
    table = Table(displayName="DeckTable", ref=table_ref)
    tbl_style = TableStyleInfo(
        name="TableStyleMedium9",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    table.tableStyleInfo = tbl_style
    ws.add_table(table)
    # Save workbook with table
    wb.save(output)
    print(f"Excel with images written to {output}")
    db.close()


if __name__ == "__main__":
    main()
