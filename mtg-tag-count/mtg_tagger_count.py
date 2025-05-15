#!/usr/bin/env python3
"""
MTG Tag Counter (GraphQL)

This script takes a list of Magic: The Gathering card names and a list of target tags,
fetches each card's taggings via Scryfall Tagger's GraphQL endpoint (including ancestor tags),
and tallies how many cards have each target tag.

Usage:
    python mtg_tagger_count.py --cards cards.txt --tags tags.txt

Requirements:
    pip install requests beautifulsoup4

If you need modifications or questions, feel free to ask!
"""
import argparse
import time
import requests
from bs4 import BeautifulSoup

# User-Agent per Scryfall API guidelines
USER_AGENT = 'MTGTagCounter/1.0 (carlos.radtke.a@gmail.com)'
GRAPHQL_URL = 'https://tagger.scryfall.com/graphql'

session = requests.Session()
session.headers.update({'User-Agent': USER_AGENT})

GRAPHQL_QUERY = '''
query FetchCard($set:String!, $number:String!) {
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
'''

def get_tagger_tags(set_code, collector_number):
    """
    Fetch taggings for a given set code and collector number via GraphQL,
    returning both direct tags and their ancestor tags (only GOOD_STANDING).
    """
    # Fetch CSRF and cookies
    page_url = f'https://tagger.scryfall.com/card/{set_code}/{collector_number}'
    resp = session.get(page_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    token_meta = soup.find('meta', {'name': 'csrf-token'})
    if not token_meta:
        raise RuntimeError('CSRF token not found on tagger page')
    csrf_token = token_meta['content']

    headers = {
        'X-CSRF-Token': csrf_token,
        'Content-Type': 'application/json',
    }
    payload = {
        'query': GRAPHQL_QUERY,
        'variables': {'set': set_code, 'number': collector_number}
    }
    graphql_resp = session.post(GRAPHQL_URL, json=payload, headers=headers)
    graphql_resp.raise_for_status()
    data = graphql_resp.json()

    taggings = data.get('data', {}).get('card', {}).get('taggings', []) or []
    tags = []
    for t in taggings:
        tag = t.get('tag', {})
        if tag.get('status') != 'GOOD_STANDING':
            continue
        # direct tag
        name = tag.get('name', '').strip().lower()
        if name:
            tags.append(name)
        # include ancestor tags
        for anc in tag.get('ancestorTags', []):
            if anc.get('status') == 'GOOD_STANDING':
                anc_name = anc.get('name', '').strip().lower()
                if anc_name:
                    tags.append(anc_name)
    # dedupe
    return list(set(tags))


def get_card_info(card_name):
    """Fetch card data from Scryfall API by exact name."""
    url = 'https://api.scryfall.com/cards/named'
    resp = session.get(url, params={'exact': card_name})
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description='Count MTG tags for cards (GraphQL).')
    parser.add_argument('--cards', required=True, help='File with card names (one per line)')
    parser.add_argument('--tags', required=True, help='File with target tags (one per line)')
    parser.add_argument('--delay', type=float, default=0.1, help='Seconds delay between requests')
    args = parser.parse_args()

    with open(args.cards, encoding='utf-8') as f:
        cards = [l.strip() for l in f if l.strip()]
    with open(args.tags, encoding='utf-8') as f:
        target_tags = [l.strip().lower() for l in f if l.strip()]

    counts = {tag: 0 for tag in target_tags}

    for card in cards:
        try:
            data = get_card_info(card)
            set_code = data['set']
            collector_number = data['collector_number']
            found = get_tagger_tags(set_code, collector_number)
            print(f"{card} -> tags found: {found}")
            for tag in target_tags:
                if tag in found:
                    counts[tag] += 1
        except Exception as e:
            print(f"Error processing '{card}': {e}")
        time.sleep(args.delay)

    print("\nTag tally:")
    for tag, cnt in counts.items():
        print(f"{tag}: {cnt}")

if __name__ == '__main__':
    main()
