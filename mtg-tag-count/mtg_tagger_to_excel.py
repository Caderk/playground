#!/usr/bin/env python3
"""
MTG Tag, Type & Deck Export → Single Excel File with Selection & Excel-Based Cumulative Counts

This script takes lists of MTG card names, target tags, target types,
and a JSON file specifying minimum and optional maximum counts for tags and types (with optional exclusions).
It fetches each card's taggings via Scryfall Tagger's GraphQL endpoint (with ancestors)
and its type line via the Scryfall API, using a local cache to avoid refetching.
Then it:
  1. Evaluates every card, marking whether it's Selected (meets deck rules) and flags cards with NoRelevantTags.
  2. Writes a single Excel file containing all cards, with TRUE values in target-tag/type columns colored green, FALSE red.
     It adds dynamic Excel COUNTIFS formulas to compute cumulative counts for each tag column, only for selected cards.

Usage:
    python mtg_tagger_to_excel.py \
      --cards cards.txt --tags tags.txt --types types.txt \
      --counts counts.json --output deck.xlsx [--delay 0.1]

Requirements:
    pip install requests beautifulsoup4 pandas openpyxl
"""
import argparse
import time
import json
import requests
from bs4 import BeautifulSoup
import pandas as pd
import shelve

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

# GraphQL query for tags
GRAPHQL_QUERY = """
query FetchCard($set: String!, $number: String!) {
  card: cardBySet(set: $set, number: $number) {
    set
    collectorNumber
    taggings(moderatorView: false) {
      tag {
        name
        status
        ancestorTags { name status }
      }
    }
  }
}
"""


def get_card_info(card_name):
    """Fetch card data from Scryfall API, with caching."""
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
    """Fetch GOOD_STANDING tags (including ancestors) via GraphQL, with caching."""
    key = f"tags:{set_code.lower()}:{collector_number}"
    if key in db:
        return set(db[key])
    # fetch CSRF token
    resp = session.get(
        f"https://tagger.scryfall.com/card/{set_code}/{collector_number}"
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    token_meta = soup.find("meta", {"name": "csrf-token"})
    if not token_meta:
        raise RuntimeError("CSRF token not found")
    csrf = token_meta["content"]
    headers = {"X-CSRF-Token": csrf, "Content-Type": "application/json"}
    payload = {
        "query": GRAPHQL_QUERY,
        "variables": {"set": set_code, "number": collector_number},
    }
    r = session.post(GRAPHQL_URL, json=payload, headers=headers)
    r.raise_for_status()
    data = r.json().get("data", {}).get("card", {}) or {}
    tags = set()
    for t in data.get("taggings", []):
        tag = t.get("tag", {})
        if tag.get("status") != "GOOD_STANDING":
            continue
        name = tag.get("name", "").lower().strip()
        if name:
            tags.add(name)
        for anc in tag.get("ancestorTags", []):
            if anc.get("status") == "GOOD_STANDING":
                anc_name = anc.get("name", "").lower().strip()
                if anc_name:
                    tags.add(anc_name)
    db[key] = list(tags)
    return tags


def build_deck_indices(df, rules, exclude_map):
    """
    Determine which cards to select based on min/max rules, returning indices.
    """
    tally = {k: 0 for k in rules}
    selected = []
    print("Building deck indices with rules:")
    for k, v in rules.items():
        print(f"  {k}: min={v['min']} max={v.get('max')}")
    for idx, row in df.iterrows():
        # skip if no relevant tags/types
        if not any(row.get(k, False) for k in rules):
            continue
        # skip if any max would be exceeded
        if any(
            rules[k].get("max") is not None
            and row.get(k, False)
            and tally[k] >= rules[k]["max"]
            for k in rules
        ):
            continue
        # find needed contributions
        primary = [
            k
            for k in rules
            if tally[k] < rules[k]["min"]
            and row.get(k, False)
            and not any(row.get(ex, False) for ex in exclude_map.get(k, []))
        ]
        if not primary:
            continue
        # select card
        selected.append(idx)
        # tally primary
        for k in primary:
            tally[k] += 1
        # tally extras up to max
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
        # check completion
        if all(tally[k] >= rules[k]["min"] for k in rules):
            break
    print("Final tally:", tally)
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

    # Read inputs
    with open(args.cards) as f:
        cards = [l.strip() for l in f if l.strip()]
    with open(args.tags) as f:
        target_tags = [l.strip().lower() for l in f if l.strip()]
    with open(args.types) as f:
        target_types = [l.strip().lower() for l in f if l.strip()]
    counts = json.load(open(args.counts))

    # Build rules and exclude_map
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
    exclude_map = {k: [e for e in v] for k, v in counts.get("exclude", {}).items()}

    # Fetch card data
    rows = []
    for card in cards:
        info_key = f"info:{card.lower()}"
        cached_info = info_key in db
        info = get_card_info(card)
        set_code = info["set"]
        num = info["collector_number"]
        tags_key = f"tags:{set_code.lower()}:{num}"
        cached_tags = tags_key in db
        tags = get_tagger_tags(set_code, num)
        types = set(info.get("type_line", "").lower().replace("—", "").split())
        row = {"card": card}
        for t in target_tags:
            row[t] = t in tags
        for t in target_types:
            row[t] = t in types
        rows.append(row)
        if not (cached_info and cached_tags):
            time.sleep(args.delay)

    df = pd.DataFrame(rows)
    df.index = range(1, len(df) + 1)
    df.index.name = "Index"

    # Mark selections
    selected_idxs = build_deck_indices(df, rules, exclude_map)
    df["Selected"] = df.index.isin(selected_idxs)
    df["NoRelevant"] = ~df[[*target_tags, *target_types]].any(axis=1)

    # Write Excel
    with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Deck", index_label="Index")
        ws = writer.sheets["Deck"]
        # coloring
        green = PatternFill(fill_type="solid", fgColor="C6EFCE")
        red = PatternFill(fill_type="solid", fgColor="FFC7CE")
        bool_cols = target_tags + target_types + ["Selected", "NoRelevant"]
        for col in bool_cols:
            idx = df.columns.get_loc(col) + 2
            let = get_column_letter(idx)
            rng = f"{let}2:{let}{len(df)+1}"
            ws.conditional_formatting.add(
                rng, CellIsRule(operator="equal", formula=["TRUE"], fill=green)
            )
            ws.conditional_formatting.add(
                rng, CellIsRule(operator="equal", formula=["FALSE"], fill=red)
            )
        # dynamic COUNTIFS formulas for selected only
        sel_col = get_column_letter(df.columns.get_loc("Selected") + 2)
        for i, tag in enumerate(target_tags):
            colp = len(df.columns) + 2 + i
            letp = get_column_letter(colp)
            ws.cell(row=1, column=colp, value=f"{tag}_cum")
            orig = get_column_letter(df.columns.get_loc(tag) + 2)
            for r in range(2, len(df) + 2):
                ws.cell(
                    row=r,
                    column=colp,
                    value=f"=COUNTIFS(${sel_col}$2:${sel_col}${r},TRUE,${orig}$2:${orig}${r},TRUE)",
                )

    print(f"Excel written to {args.output}")
    db.close()


if __name__ == "__main__":
    main()
