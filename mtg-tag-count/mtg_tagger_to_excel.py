#!/usr/bin/env python3
"""
MTG Tag, Type & Deck Export → Single Excel File with Formatting & Max Constraints

This script takes lists of MTG card names, target tags, target types,
and a JSON file specifying minimum and optional maximum counts for tags and types (with optional exclusions).
It fetches each card's taggings via Scryfall Tagger's GraphQL endpoint (with ancestors)
and its type line via the Scryfall API, using a local cache to avoid refetching.
Then it:
  1. Selects cards to satisfy minimum counts and not exceed maximum counts (building a deck), logging each skip or selection with clear reasons.
     It also tallies additional tag/type counts up to their max constraints for every selected card.
  2. Writes a single Excel file containing the selected cards,
     with TRUE values in target-tag/type columns colored green, FALSE colored red,
     and cumulative frequencies of each tag to the right.

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
USER_AGENT = "MTGTagCounter/1.0 (your_email@example.com)"
GRAPHQL_URL = "https://tagger.scryfall.com/graphql"
CACHE_PATH = "mtg_cache.db"

# Initialize HTTP session and cache
db = shelve.open(CACHE_PATH)
session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

# GraphQL query for tags
GRAPHQL_QUERY = """
query FetchCard($set:String!, $number:String!) {
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


def build_deck(df, rules, exclude_map):
    """
    Select cards to satisfy min_counts and respect max_counts.
    Logs each skip with precise reasons (missing, not needed, at max, excluded).
    Also tallies additional counts up to max for selected cards.
    rules: dict of {key: {'min':int,'max':int or None}}
    """
    tally = {k: 0 for k in rules}
    deck_indices = []

    print("Building deck with rules:")
    for k, v in rules.items():
        print(f"  {k}: min={v['min']} max={v.get('max')}")

    for idx, row in df.iterrows():
        card = row["card"]
        # Skip if any tag/type would exceed max
        skip_reasons = []
        for key, rule in rules.items():
            if (
                rule.get("max") is not None
                and row.get(key, False)
                and tally[key] >= rule["max"]
            ):
                skip_reasons.append(
                    f"has {key} but at max ({tally[key]}/{rule['max']})"
                )
        if skip_reasons:
            print(f"Skipping '{card}' (Index {idx}): {', '.join(skip_reasons)}")
            continue

        # Determine primary contributions (to satisfy mins)
        primary = []
        for key, rule in rules.items():
            if tally[key] < rule["min"] and row.get(key, False):
                if any(row.get(ex, False) for ex in exclude_map.get(key, [])):
                    pass
                else:
                    primary.append(key)

        if not primary:
            # Log why skipped
            reasons = []
            for key, rule in rules.items():
                has_tag = row.get(key, False)
                if not has_tag:
                    reasons.append(f"{key} missing")
                elif tally[key] >= rule["min"]:
                    reasons.append(f"{key} not needed ({tally[key]}/{rule['min']})")
            print(f"Skipping '{card}' (Index {idx}): {'; '.join(reasons)}")
            continue

        # Select this card
        # Also tally any extra tags/types (up to max)
        extras = []
        for key, rule in rules.items():
            if key in primary:
                continue
            if (
                row.get(key, False)
                and rule.get("max") is not None
                and tally[key] < rule["max"]
            ):
                extras.append(key)

        print(f"Selecting '{card}' (Index {idx}) primary={primary} extras={extras}")
        deck_indices.append(idx)

        # Update tallies
        for key in primary + extras:
            tally[key] += 1
        print(f"Tally now: {tally}")

        # Stop if all mins satisfied
        if all(tally[k] >= rules[k]["min"] for k in rules):
            print("All minimums satisfied; stopping deck build.")
            break

    print(f"Final tally: {tally}")
    return df.loc[deck_indices]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", default="cards.txt")
    parser.add_argument("--tags", default="tags.txt")
    parser.add_argument("--types", default="types.txt")
    parser.add_argument(
        "--counts",
        default="counts.json",
        help="JSON with per-tag/type min and optional max",
    )
    parser.add_argument("--output", default="deck.xlsx")
    parser.add_argument("--delay", type=float, default=0.1)
    args = parser.parse_args()

    with open(args.cards) as f:
        cards = [l.strip() for l in f if l.strip()]
    with open(args.tags) as f:
        target_tags = [l.strip().lower() for l in f if l.strip()]
    with open(args.types) as f:
        target_types = [l.strip().lower() for l in f if l.strip()]
    counts = json.load(open(args.counts))

    # Build rules
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

    exclude_map = {
        k.lower(): [e.lower() for e in v] for k, v in counts.get("exclude", {}).items()
    }

    # Fetch card data
    rows = []
    for card in cards:
        info_key = f"info:{card.lower()}"
        info_cached = info_key in db
        info = get_card_info(card)
        set_code = info["set"]
        collector = info["collector_number"]

        tags_key = f"tags:{set_code.lower()}:{collector}"
        tags_cached = tags_key in db
        tags = get_tagger_tags(set_code, collector)

        types = set(info.get("type_line", "").lower().replace("—", "").split())
        row = {"card": card}
        for tag in target_tags:
            row[tag] = tag in tags
        for ttype in target_types:
            row[ttype] = ttype in types
        rows.append(row)
        if not (info_cached and tags_cached):
            time.sleep(args.delay)

    df = pd.DataFrame(rows)
    df.index = range(1, len(df) + 1)
    df.index.name = "Index"

    # Build deck and output
    deck_df = build_deck(df, rules, exclude_map)
    cumul = deck_df[target_tags].cumsum().add_suffix("_cum")
    final_df = pd.concat([deck_df, cumul], axis=1)

    with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
        final_df.to_excel(writer, sheet_name="Deck", index_label="Index")
        ws = writer.sheets["Deck"]
        green = PatternFill(fill_type="solid", fgColor="C6EFCE")
        red = PatternFill(fill_type="solid", fgColor="FFC7CE")
        bool_count = len(target_tags) + len(target_types)
        for col_idx in range(2, 2 + bool_count):
            letter = get_column_letter(col_idx)
            rng = f"{letter}2:{letter}{len(final_df)+1}"
            ws.conditional_formatting.add(
                rng, CellIsRule(operator="equal", formula=["TRUE"], fill=green)
            )
            ws.conditional_formatting.add(
                rng, CellIsRule(operator="equal", formula=["FALSE"], fill=red)
            )

    print(f"Deck with min/max written to {args.output}")
    db.close()


if __name__ == "__main__":
    main()
