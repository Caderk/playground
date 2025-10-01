#!/usr/bin/env python3
"""
Spotify Explorer - Interactive CLI for querying global Spotify statistics.

Usage:
    python main.py
"""
import sys

import pandas as pd
from spotify_client import SpotifyExplorer
from tabulate import tabulate


def print_banner():
    """Print welcome banner."""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║           Spotify Explorer - Global Music Statistics         ║
╠═══════════════════════════════════════════════════════════════╣
║  Query global Spotify data about artists, tracks, and genres ║
╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_menu():
    """Print main menu."""
    menu = """
Choose an option:
  1. Search artists by genre
  2. Search tracks by genre
  3. Browse/search available genres
  4. Clear cache
  5. Quit
    """
    print(menu)


def format_results(df: pd.DataFrame) -> str:
    """
    Format query results as a nice table.

    Args:
        df: DataFrame with results

    Returns:
        Formatted table string
    """
    if df.empty:
        return "No results found. Try a different genre."

    # Format large numbers with commas
    if "followers" in df.columns:
        df = df.copy()
        df["followers"] = df["followers"].apply(lambda x: f"{x:,}")

    # Truncate long genre lists
    if "genres" in df.columns:
        df = df.copy()
        df["genres"] = df["genres"].apply(
            lambda x: (
                ", ".join(x[:3]) + ("..." if len(x) > 3 else "")
                if isinstance(x, list)
                else x
            )
        )

    # Create table
    table = tabulate(df, headers="keys", tablefmt="fancy_grid", showindex=False)

    return table


def get_number_input(prompt: str, min_val: int = 1, max_val: int = 50) -> int:
    """Get a valid number from user."""
    while True:
        try:
            value = input(prompt).strip()
            if not value:
                return 10  # default
            num = int(value)
            if min_val <= num <= max_val:
                return num
            print(f"Please enter a number between {min_val} and {max_val}")
        except ValueError:
            print("Please enter a valid number")


def search_artists_menu(explorer: SpotifyExplorer):
    """Interactive menu for searching artists."""
    print("\n" + "=" * 60)
    print("Search Artists by Genre")
    print("=" * 60)

    genre = input("\nEnter genre (e.g., 'drum and bass', 'techno'): ").strip()
    if not genre:
        print("❌ Genre is required")
        return

    limit = get_number_input("How many results? (1-50, default 10): ", 1, 50)

    metric = input("Sort by: [1] Popularity (default) [2] Followers: ").strip()
    sort_by = "followers" if metric == "2" else "popularity"

    print("\n⏳ Searching Spotify...\n")

    try:
        artists = explorer.search_artists_by_genre(genre, limit=limit)

        if not artists:
            print(f"❌ No artists found for genre '{genre}'")
            print("💡 Try a more common genre name")
            return

        # Convert to DataFrame
        df = pd.DataFrame(artists)
        df = df.sort_values(by=sort_by, ascending=False).head(limit)
        df["rank"] = range(1, len(df) + 1)

        # Select display columns
        display_cols = ["rank", "name", "followers", "popularity", "genres"]
        df_display = df[display_cols]

        print(format_results(df_display))
        print(f"\n✓ Found {len(df_display)} artist(s) in '{genre}'\n")

        # Ask if user wants specific rank
        show_rank = input(
            "View specific rank? (e.g., '2' for 2nd, Enter to skip): "
        ).strip()
        if show_rank and show_rank.isdigit():
            rank_num = int(show_rank)
            if 1 <= rank_num <= len(df):
                artist = df[df["rank"] == rank_num].iloc[0]
                print(f"\n🎵 Rank #{rank_num}: {artist['name']}")
                print(f"   Followers: {artist['followers']:,}")
                print(f"   Popularity: {artist['popularity']}/100")
                print(f"   Genres: {', '.join(artist['genres'][:5])}")
                print(f"   Spotify: {artist['external_url']}\n")

    except Exception as e:
        print(f"❌ Error: {e}\n")


def search_tracks_menu(explorer: SpotifyExplorer):
    """Interactive menu for searching tracks."""
    print("\n" + "=" * 60)
    print("Search Tracks by Genre")
    print("=" * 60)

    genre = input("\nEnter genre (e.g., 'drum and bass', 'techno'): ").strip()
    if not genre:
        print("❌ Genre is required")
        return

    limit = get_number_input("How many results? (1-50, default 10): ", 1, 50)

    print("\n⏳ Searching Spotify...\n")

    try:
        tracks = explorer.search_tracks_by_genre(genre, limit=limit)

        if not tracks:
            print(f"❌ No tracks found for genre '{genre}'")
            print("💡 Try a more common genre name")
            return

        # Convert to DataFrame
        df = pd.DataFrame(tracks)
        df = df.sort_values(by="popularity", ascending=False).head(limit)
        df["rank"] = range(1, len(df) + 1)

        # Select display columns
        display_cols = ["rank", "name", "artist", "popularity", "album"]
        df_display = df[display_cols]

        print(format_results(df_display))
        print(f"\n✓ Found {len(df_display)} track(s) in '{genre}'\n")

        # Ask if user wants specific rank
        show_rank = input(
            "View specific rank? (e.g., '2' for 2nd, Enter to skip): "
        ).strip()
        if show_rank and show_rank.isdigit():
            rank_num = int(show_rank)
            if 1 <= rank_num <= len(df):
                track = df[df["rank"] == rank_num].iloc[0]
                print(f"\n🎵 Rank #{rank_num}: {track['name']}")
                print(f"   Artist: {track['artist']}")
                print(f"   Album: {track['album']}")
                print(f"   Popularity: {track['popularity']}/100")
                print(f"   Spotify: {track['external_url']}\n")

    except Exception as e:
        print(f"❌ Error: {e}\n")


def browse_genres_menu(explorer: SpotifyExplorer):
    """Interactive menu for browsing and searching genres."""
    print("\n" + "=" * 60)
    print("Browse Available Genres")
    print("=" * 60)

    search_query = input("\nSearch genres (or press Enter to see all): ").strip()

    print("\n⏳ Fetching genres...\n")

    try:
        if search_query:
            genres = explorer.search_genres(search_query)
            if not genres:
                print(f"❌ No genres found matching '{search_query}'")
                print("💡 Try a different search term\n")
                return
            print(f"📋 Genres matching '{search_query}':")
        else:
            genres = explorer.get_available_genres()
            print(f"📋 All available genres ({len(genres)} total):")

        # Display genres in columns
        if genres:
            # Split into columns for better display
            cols = 3
            col_width = 25

            for i in range(0, len(genres), cols):
                row = genres[i : i + cols]
                print("  " + "".join(f"{g:<{col_width}}" for g in row))

            print(f"\n✓ Found {len(genres)} genre(s)\n")

            # Suggest using one
            use_genre = input(
                "Copy a genre name to use in search (Enter to skip): "
            ).strip()
            if use_genre and use_genre in genres:
                print(f"\n💡 Use this in option 1 or 2: '{use_genre}'\n")

    except Exception as e:
        print(f"❌ Error: {e}\n")


def main():
    """Main CLI loop."""
    print_banner()

    try:
        explorer = SpotifyExplorer()
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        print("\nPlease create a .env file with your Spotify credentials:")
        print("  SPOTIFY_CLIENT_ID=your_client_id")
        print("  SPOTIFY_CLIENT_SECRET=your_client_secret")
        print("\nGet credentials at: https://developer.spotify.com/dashboard")
        return 1

    print("✓ Connected to Spotify API\n")

    while True:
        print_menu()
        choice = input("\nSelect option (1-5): ").strip()

        if choice == "1":
            search_artists_menu(explorer)
        elif choice == "2":
            search_tracks_menu(explorer)
        elif choice == "3":
            browse_genres_menu(explorer)
        elif choice == "4":
            explorer.clear_cache()
            print("\n✓ Cache cleared!\n")
        elif choice == "5":
            print("\nThanks for using Spotify Explorer! 👋\n")
            break
        else:
            print("\n❌ Invalid choice. Please select 1-5.\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
