#!/usr/bin/env python3
"""
MTG Tag, Type & Deck Export → Excel with Caching & Debug

This script takes lists of MTG card names, target tags, target types,
and a JSON file specifying minimum counts for tags and types (with optional exclusions).
It fetches each card's taggings via Scryfall Tagger's GraphQL endpoint (with ancestors)
and its type line via the Scryfall API, using a local cache to avoid refetching.
Then it:
  1. Writes an Excel report where each target tag and type is a boolean column per card,
     with an incremental index starting from 1.
  2. Builds a "deck" satisfying minimum counts, respecting excludes,
     printing debug info about why cards are skipped, and writes this to a second Excel file.

Usage:
    python mtg_tagger_to_excel.py \
      --cards cards.txt --tags tags.txt --types types.txt \
      --min-counts min_counts.json \
      --output report.xlsx --deck-output deck.xlsx

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

# Constants
USER_AGENT = 'MTGTagCounter/1.0 (your_email@example.com)'
GRAPHQL_URL = 'https://tagger.scryfall.com/graphql'
CACHE_PATH = 'mtg_cache.db'

# Initialize HTTP session and cache
session = requests.Session()
session.headers.update({'User-Agent': USER_AGENT})
cache = shelve.open(CACHE_PATH)

# GraphQL query for tags
GRAPHQL_QUERY = '''
query FetchCard($set:String!, $number:String!) {
  card: cardBySet(set: $set, number: $number) {
    set
    collectorNumber
    taggings(moderatorView: false) {
      tag { name status ancestorTags { name status } }
    }
  }
}
'''

def get_card_info(card_name):
    """Fetch card data from Scryfall API, with caching."""
    key = f"info:{card_name.lower()}"
    if key in cache:
        return cache[key]
    url = 'https://api.scryfall.com/cards/named'
    resp = session.get(url, params={'exact': card_name})
    resp.raise_for_status()
    info = resp.json()
    cache[key] = info
    return info


def get_tagger_tags(set_code, collector_number):
    """Fetch GOOD_STANDING tags (including ancestors) via GraphQL, with caching."""
    key = f"tags:{set_code.lower()}:{collector_number}"
    if key in cache:
        return set(cache[key])

    # Retrieve CSRF token and cookies
    page_url = f'https://tagger.scryfall.com/card/{set_code}/{collector_number}'
    resp = session.get(page_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    token_meta = soup.find('meta', {'name': 'csrf-token'})
    if not token_meta:
        raise RuntimeError('CSRF token not found')
    csrf = token_meta['content']

    headers = {'X-CSRF-Token': csrf, 'Content-Type': 'application/json'}
    payload = {'query': GRAPHQL_QUERY, 'variables': {'set': set_code, 'number': collector_number}}
    r = session.post(GRAPHQL_URL, json=payload, headers=headers)
    r.raise_for_status()
    data = r.json().get('data', {}).get('card', {}) or {}

    tags = set()
    for t in data.get('taggings', []):
        tag = t.get('tag', {})
        if tag.get('status') != 'GOOD_STANDING':
            continue
        name = tag.get('name', '').lower().strip()
        if name:
            tags.add(name)
        for anc in tag.get('ancestorTags', []):
            if anc.get('status') == 'GOOD_STANDING':
                anc_name = anc.get('name', '').lower().strip()
                if anc_name:
                    tags.add(anc_name)

    cache[key] = list(tags)
    return tags


def build_deck(df, min_counts, exclude_map):
    """Select cards to satisfy min_counts, skipping cards that add nothing new, with debug logs."""
    remaining = {**min_counts.get('tags', {}), **min_counts.get('types', {})}
    deck_indices = []

    print("Building deck; initial requirements:", remaining)
    for idx, row in df.iterrows():
        card_name = row['card']
        contrib = []
        reasons = []
        # Check each requirement
        for key, needed in remaining.items():
            if needed <= 0:
                reasons.append(f"{key} already satisfied")
                continue
            if not row.get(key, False):
                reasons.append(f"{key} not present")
                continue
            # Exclusion logic
            excludes = exclude_map.get(key, [])
            if any(row.get(ex, False) for ex in excludes):
                reasons.append(f"excluded by {excludes}")
                continue
            contrib.append(key)
        if not contrib:
            print(f"Skipping '{card_name}' (Index {idx}): {'; '.join(reasons)}")
            continue
        # Select card
        print(f"Selecting '{card_name}' (Index {idx}) contributes: {contrib}")
        deck_indices.append(idx)
        for key in contrib:
            remaining[key] = max(0, remaining[key] - 1)
        print("Remaining after selection:", remaining)
        # Stop if done
        if all(v == 0 for v in remaining.values()):
            print("All requirements satisfied; stopping deck build.")
            break

    return df.loc[deck_indices]


def main():
    parser = argparse.ArgumentParser(description='Export MTG tags & types to Excel with deck building and debug')
    parser.add_argument('--cards', required=True)
    parser.add_argument('--tags', required=True)
    parser.add_argument('--types', required=True)
    parser.add_argument('--min-counts', required=True)
    parser.add_argument('--output', default='report.xlsx')
    parser.add_argument('--deck-output', default='deck.xlsx')
    parser.add_argument('--delay', type=float, default=0.1)
    args = parser.parse_args()

    # Load lists
    with open(args.cards, encoding='utf-8') as f:
        cards = [l.strip() for l in f if l.strip()]
    with open(args.tags, encoding='utf-8') as f:
        target_tags = [l.strip().lower() for l in f if l.strip()]
    with open(args.types, encoding='utf-8') as f:
        target_types = [l.strip().lower() for l in f if l.strip()]
    min_counts = json.load(open(args.min_counts))
    raw_excl = min_counts.get('exclude', {})
    exclude_map = {k.lower(): [e.lower() for e in v] for k, v in raw_excl.items()}

    # Gather data
    rows = []
    for card in cards:
        try:
            info = get_card_info(card)
            tags = get_tagger_tags(info['set'], info['collector_number'])
            types = set(info.get('type_line', '').lower().replace('—', '').split())
            row = {'card': card}
            for tag in target_tags:
                row[tag] = tag in tags
            for ttype in target_types:
                row[ttype] = ttype in types
            rows.append(row)
            print(f"Processed {card}")
        except Exception as e:
            print(f"Error {card}: {e}")
        time.sleep(args.delay)

    # Build report DataFrame
    df = pd.DataFrame(rows)
    df.index = range(1, len(df) + 1)
    df.index.name = 'Index'

    # Write full report
    df.to_excel(args.output)
    print(f"Report written to {args.output}")

    # Build and write deck
    deck_df = build_deck(df, min_counts, exclude_map)
    deck_df.to_excel(args.deck_output)
    print(f"Deck written to {args.deck_output}")

    cache.close()

if __name__ == '__main__':
    main()
