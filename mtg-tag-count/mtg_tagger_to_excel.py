#!/usr/bin/env python3
"""
MTG Tag & Type Export → Excel

This script takes lists of MTG card names, target tags, and target types,
fetches each card's taggings via Scryfall Tagger's GraphQL endpoint (with ancestors),
and its type line via the Scryfall API,
and writes an Excel file where each target tag and target type is a column of boolean values per card,
with an incremental index starting from 1.

Usage:
    python mtg_tagger_to_excel.py --cards cards.txt --tags tags.txt --types types.txt --output report.xlsx

Requirements:
    pip install requests beautifulsoup4 pandas openpyxl

"""
import argparse
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd

USER_AGENT = 'MTGTagCounter/1.0 (your_email@example.com)'
GRAPHQL_URL = 'https://tagger.scryfall.com/graphql'

session = requests.Session()
session.headers.update({'User-Agent': USER_AGENT})

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

def get_tagger_tags(set_code, collector_number):
    """Return set of GOOD_STANDING tag names and their ancestor names."""
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
    return tags


def get_card_info(card_name):
    """Fetch card info (including type_line) from Scryfall API by exact name."""
    url = 'https://api.scryfall.com/cards/named'
    r = session.get(url, params={'exact': card_name})
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser(description='Export MTG tags & types to Excel')
    parser.add_argument('--cards', required=True, help='File with card names')
    parser.add_argument('--tags', required=True, help='File with target tags')
    parser.add_argument('--types', required=True, help='File with target types (e.g. Creature, Artifact)')
    parser.add_argument('--output', default='report.xlsx', help='Excel output path')
    parser.add_argument('--delay', type=float, default=0.1, help='Seconds between requests')
    args = parser.parse_args()

    # Load lists
    with open(args.cards, encoding='utf-8') as f:
        cards = [l.strip() for l in f if l.strip()]
    with open(args.tags, encoding='utf-8') as f:
        target_tags = [l.strip().lower() for l in f if l.strip()]
    with open(args.types, encoding='utf-8') as f:
        target_types = [l.strip().lower() for l in f if l.strip()]

    rows = []
    for card in cards:
        try:
            info = get_card_info(card)
            set_code = info['set']
            number = info['collector_number']
            # fetch tags
            tags = get_tagger_tags(set_code, number)
            # parse types
            type_line = info.get('type_line', '').lower()
            types = set(t.strip() for t in type_line.replace('—', '').split())

            row = {'card': card}
            # boolean flags for tags
            for tag in target_tags:
                row[tag] = tag in tags
            # boolean flags for types
            for ttype in target_types:
                row[ttype] = ttype in types

            rows.append(row)
            print(f"Processed {card}")
        except Exception as e:
            print(f"Error {card}: {e}")
        time.sleep(args.delay)

    # Build DataFrame and add incremental index
    df = pd.DataFrame(rows)
    df.index = range(1, len(df) + 1)
    df.index.name = 'Index'

    # Export to Excel
    df.to_excel(args.output)
    print(f"Excel report written to {args.output}")

if __name__ == '__main__':
    main()
