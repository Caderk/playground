#!/usr/bin/env python3
"""
MTG Tag & Type Counter (GraphQL) with Caching

This script takes a list of Magic: The Gathering card names, a list of target tags,
and a list of target types. It fetches each card's taggings via Scryfall Tagger's
GraphQL endpoint (including ancestor tags) and its type line via the Scryfall API.
It then tallies how many cards have each target tag and each target type.

It uses a local shelve cache to avoid redundant API calls, and skips the delay
when both card info and tags are retrieved from cache.

Usage:
    python mtg_tagger_count.py --cards cards.txt --tags tags.txt --types types.txt [--delay 0.1]

Requirements:
    pip install requests beautifulsoup4
"""
import argparse
import time
import requests
from bs4 import BeautifulSoup
import shelve

# User-Agent per Scryfall API guidelines and cache path
USER_AGENT = "MTGTagCounter/1.0 (carlos.radtke.a@gmail.com)"
GRAPHQL_URL = "https://tagger.scryfall.com/graphql"
CACHE_PATH = "mtg_tagger_cache.db"

# Initialize HTTP session and cache
session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})
cache = shelve.open(CACHE_PATH)

# GraphQL query for fetching tags
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
    """Fetch card data from Scryfall API by exact name, with caching."""
    key = f"info:{card_name.lower()}"
    if key in cache:
        return cache[key]
    url = "https://api.scryfall.com/cards/named"
    resp = session.get(url, params={"exact": card_name})
    resp.raise_for_status()
    info = resp.json()
    cache[key] = info
    return info


def get_tagger_tags(set_code, collector_number):
    """Fetch GOOD_STANDING tags (including ancestors) via GraphQL, with caching."""
    key = f"tags:{set_code.lower()}:{collector_number}"
    if key in cache:
        return set(cache[key])

    # Retrieve CSRF token from card page
    page_url = f"https://tagger.scryfall.com/card/{set_code}/{collector_number}"
    resp = session.get(page_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    token_meta = soup.find("meta", {"name": "csrf-token"})
    if not token_meta:
        raise RuntimeError("CSRF token not found on tagger page")
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

    cache[key] = list(tags)
    return tags


def main():
    parser = argparse.ArgumentParser(
        description="Count MTG tags and types for cards (GraphQL) with caching."
    )
    parser.add_argument(
        "--cards", default="cards.txt", help="File with card names (one per line)"
    )
    parser.add_argument(
        "--tags", default="tags.txt", help="File with target tags (one per line)"
    )
    parser.add_argument(
        "--types", default="types.txt", help="File with target types (one per line)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help="Seconds delay between network requests",
    )
    args = parser.parse_args()

    # Load card names, tags, and types
    with open(args.cards, encoding="utf-8") as f:
        cards = [l.strip() for l in f if l.strip()]
    with open(args.tags, encoding="utf-8") as f:
        target_tags = [l.strip().lower() for l in f if l.strip()]
    with open(args.types, encoding="utf-8") as f:
        target_types = [l.strip().lower() for l in f if l.strip()]

    # Initialize counts
    tag_counts = {tag: 0 for tag in target_tags}
    type_counts = {tt: 0 for tt in target_types}

    # Process each card
    for card in cards:
        # Determine cache hits
        info_key = f"info:{card.lower()}"
        info_cached = info_key in cache
        try:
            info = get_card_info(card)
            set_code = info["set"]
            collector_number = info["collector_number"]

            tags_key = f"tags:{set_code.lower()}:{collector_number}"
            tags_cached = tags_key in cache

            # Tags
            found_tags = get_tagger_tags(set_code, collector_number)
            print(f"{card} -> tags found: {sorted(found_tags)}")
            for tag in target_tags:
                if tag in found_tags:
                    tag_counts[tag] += 1

            # Types
            type_line = info.get("type_line", "").lower().replace("—", " ")
            found_types = set(type_line.split())
            print(f"{card} -> types found: {sorted(found_types)}")
            for tt in target_types:
                if tt in found_types:
                    type_counts[tt] += 1

        except Exception as e:
            print(f"Error processing '{card}': {e}")
        finally:
            # Only delay if any network fetch occurred
            if not (info_cached and tags_cached):
                time.sleep(args.delay)

    # Close cache
    cache.close()

    # Print results
    print("\nTag tally:")
    for tag, cnt in tag_counts.items():
        print(f"{tag}: {cnt}")

    print("\nType tally:")
    for tt, cnt in type_counts.items():
        print(f"{tt}: {cnt}")


if __name__ == "__main__":
    main()
