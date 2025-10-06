#!/usr/bin/env python3
"""
Spotify Explorer - Interactive CLI for querying global Spotify statistics.

Usage:
    python main.py
"""
import sys

import pandas as pd
from tabulate import tabulate

from spotify_client import SpotifyExplorer


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
  3. Get top songs from top artists (playlist builder)
  4. Browse/search available genres
  5. Clear cache
  6. Quit
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


def export_tracks_to_file(df: pd.DataFrame, genre: str):
    """Export tracks to a playlist file."""
    import datetime
    from pathlib import Path

    # Create exports directory if it doesn't exist
    export_dir = Path(__file__).parent / "exports"
    export_dir.mkdir(exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    genre_clean = genre.replace(" ", "_").replace("/", "_")
    filename = f"{genre_clean}_{timestamp}.txt"
    filepath = export_dir / filename

    try:
        with open(filepath, "w") as f:
            # Write header
            f.write(f"# Spotify Playlist: Top {len(df)} {genre} tracks\n")
            f.write(
                f"# Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            f.write("#\n")
            f.write("# HOW TO USE:\n")
            f.write("# 1. Copy all spotify:track: lines below\n")
            f.write("# 2. In Spotify Desktop app, create a new playlist\n")
            f.write("# 3. Press Ctrl+V (Cmd+V on Mac) to paste\n")
            f.write("# 4. All tracks will be added automatically!\n")
            f.write("#\n\n")

            # Write track URIs (one per line)
            for _, track in df.iterrows():
                # Extract track ID from external_url
                track_id = track["id"]
                f.write(f"spotify:track:{track_id}\n")

            f.write("\n# Track List:\n")
            for _, track in df.iterrows():
                # Format follower count with commas
                followers_str = f"{track.get('artist_followers', 0):,}"
                popularity = track.get('popularity', 0)
                f.write(
                    f"# {track['rank']}. {track['name']} - {track['artist']} "
                    f"(Followers: {followers_str}, Popularity: {popularity})\n"
                )

        print(f"\n✅ Exported {len(df)} tracks to: {filepath}")
        print(f"📁 Location: {filepath.absolute()}")
        print("\n💡 To import to Spotify:")
        print("   1. Open Spotify Desktop app")
        print("   2. Create a new playlist")
        print("   3. Open the exported file and copy all spotify:track: lines")
        print("   4. Click in the playlist and paste (Ctrl+V / Cmd+V)")
        print("   5. All tracks will be added!\n")

    except Exception as e:
        print(f"❌ Error exporting: {e}\n")


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
        # Fetch comprehensive artist list (ignore limit parameter in API call)
        artists = explorer.search_artists_by_genre(genre, limit=100)

        if not artists:
            print(f"❌ No artists found for genre '{genre}'")
            print("💡 Try a more common genre name")
            return

        # Convert to DataFrame and sort by user's choice
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
        # Fetch comprehensive track list
        tracks = explorer.search_tracks_by_genre(genre, limit=100)

        if not tracks:
            print(f"❌ No tracks found for genre '{genre}'")
            print("💡 Try a more common genre name")
            return

        # Convert to DataFrame and apply user's limit
        df = pd.DataFrame(tracks)
        df = df.sort_values(by="popularity", ascending=False).head(limit)
        df["rank"] = range(1, len(df) + 1)

        # Select display columns
        display_cols = ["rank", "name", "artist", "popularity", "album"]
        df_display = df[display_cols]

        print(format_results(df_display))
        print(f"\n✓ Found {len(df_display)} track(s) in '{genre}'\n")

        # Ask if user wants to export to file
        export = input("Export to playlist file? (y/n): ").strip().lower()
        if export == "y":
            export_tracks_to_file(df, genre)

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


def top_songs_from_top_artists_menu(explorer: SpotifyExplorer):
    """Interactive menu for getting top songs from top artists."""
    print("\n" + "=" * 60)
    print("Top Songs from Top Artists - Playlist Builder")
    print("=" * 60)
    
    genre = input("\nEnter genre (e.g., 'drum and bass', 'techno'): ").strip()
    if not genre:
        print("❌ Genre is required")
        return
    
    num_artists = get_number_input(
        "How many top artists? (1-50, default 50): ", 1, 50
    )
    if num_artists == 10:  # User pressed Enter (default from get_number_input)
        num_artists = 50
    
    tracks_per_artist = get_number_input(
        "Tracks per artist? (1-10, default 5): ", 1, 10
    )
    if tracks_per_artist == 10:  # Check if it's the default
        tracks_per_artist = 5
    
    total_tracks = num_artists * tracks_per_artist
    print(f"\n💡 Will collect ~{total_tracks} tracks total")
    print("⏳ This may take a minute...\n")
    
    try:
        # Fetch tracks
        tracks = explorer.get_top_tracks_from_top_artists(
            genre, num_artists, tracks_per_artist
        )
        
        if not tracks:
            print(f"❌ No tracks found for genre '{genre}'")
            print("💡 Try a more common genre name")
            return
        
        # Convert to DataFrame for display
        df = pd.DataFrame(tracks)
        
        # Add rank column to the main DataFrame
        df["rank"] = range(1, len(df) + 1)
        
        # Show preview
        print(f"\n📊 Preview of results ({len(df)} tracks):")
        preview_df = df[["rank", "name", "artist", "popularity"]].head(10)
        print(format_results(preview_df))
        
        if len(df) > 10:
            print(f"... and {len(df) - 10} more tracks")
        
        print(f"\n✓ Found {len(df)} track(s) from top {num_artists} artists\n")
        
        # Ask if user wants to export
        export = input("Export to playlist file? (y/n): ").strip().lower()
        if export == "y":
            export_tracks_to_file(df, genre)
    
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
        choice = input("\nSelect option (1-6): ").strip()

        if choice == "1":
            search_artists_menu(explorer)
        elif choice == "2":
            search_tracks_menu(explorer)
        elif choice == "3":
            top_songs_from_top_artists_menu(explorer)
        elif choice == "4":
            browse_genres_menu(explorer)
        elif choice == "5":
            explorer.clear_cache()
            print("\n✓ Cache cleared!\n")
        elif choice == "6":
            print("\nThanks for using Spotify Explorer! 👋\n")
            break
        else:
            print("\n❌ Invalid choice. Please select 1-6.\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
