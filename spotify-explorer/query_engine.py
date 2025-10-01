"""
Query engine for exploring Spotify data with natural language queries.
"""

import re
from typing import Dict, List, Optional

import pandas as pd
from spotify_client import SpotifyExplorer


class QueryEngine:
    """Engine for processing natural language queries about Spotify data."""

    def __init__(self):
        """Initialize the query engine."""
        self.explorer = SpotifyExplorer()

    def parse_query(self, query: str) -> Dict:
        """
        Parse a natural language query into structured components.

        Args:
            query: Natural language query string

        Returns:
            Dictionary with query components (type, genre, rank, etc.)
        """
        query_lower = query.lower()

        # Extract rank (e.g., "second", "third", "top 5")
        rank_patterns = {
            r"\b(first|1st)\b": 1,
            r"\b(second|2nd)\b": 2,
            r"\b(third|3rd)\b": 3,
            r"\b(fourth|4th)\b": 4,
            r"\b(fifth|5th)\b": 5,
            r"\b(sixth|6th)\b": 6,
            r"\b(seventh|7th)\b": 7,
            r"\b(eighth|8th)\b": 8,
            r"\b(ninth|9th)\b": 9,
            r"\b(tenth|10th)\b": 10,
            r"top\s+(\d+)": None,  # Will extract number
        }

        rank = None
        top_n = None

        for pattern, value in rank_patterns.items():
            match = re.search(pattern, query_lower)
            if match:
                if value is None:
                    # It's a "top N" pattern
                    top_n = int(match.group(1))
                else:
                    rank = value
                break

        # Extract genre
        genre = None
        genre_indicators = ["in the", "in", "from", "of", "genre", "style"]

        for indicator in genre_indicators:
            if indicator in query_lower:
                # Try to extract genre after the indicator
                parts = query_lower.split(indicator)
                if len(parts) > 1:
                    potential_genre = parts[-1].strip()
                    # Clean up common words
                    potential_genre = re.sub(
                        r"\b(artist|track|song|genre|style)\b", "", potential_genre
                    ).strip()
                    if potential_genre:
                        genre = potential_genre
                        break

        # Determine query type (artist or track)
        query_type = "artist"
        if any(word in query_lower for word in ["track", "song"]):
            query_type = "track"

        # Determine metric (most listened, most popular, most followers)
        metric = "popularity"  # default
        if "follower" in query_lower:
            metric = "followers"
        elif "popular" in query_lower:
            metric = "popularity"
        elif "listened" in query_lower:
            metric = "popularity"  # Use popularity as proxy for listening

        return {
            "type": query_type,
            "genre": genre,
            "rank": rank,
            "top_n": top_n,
            "metric": metric,
        }

    def execute_query(self, query: str) -> pd.DataFrame:
        """
        Execute a natural language query and return results.

        Args:
            query: Natural language query string

        Returns:
            DataFrame with query results
        """
        parsed = self.parse_query(query)

        if not parsed["genre"]:
            raise ValueError(
                "Could not identify genre in query. "
                "Please specify a genre (e.g., 'drum and bass')"
            )

        print(f"Searching for {parsed['type']}s in genre: {parsed['genre']}")

        if parsed["type"] == "artist":
            data = self.explorer.search_artists_by_genre(parsed["genre"], limit=100)
            df = pd.DataFrame(data)

            if df.empty:
                return df

            # Sort by the specified metric
            sort_col = parsed["metric"]
            df = df.sort_values(by=sort_col, ascending=False)

            # Add rank column
            df["rank"] = range(1, len(df) + 1)

            # Filter to requested rank or top N
            if parsed["rank"]:
                df = df[df["rank"] == parsed["rank"]]
            elif parsed["top_n"]:
                df = df.head(parsed["top_n"])
            else:
                df = df.head(10)  # Default to top 10

            # Select relevant columns for display
            display_cols = ["rank", "name", "followers", "popularity", "genres"]
            return df[display_cols]

        else:  # tracks
            data = self.explorer.search_tracks_by_genre(parsed["genre"], limit=100)
            df = pd.DataFrame(data)

            if df.empty:
                return df

            # Sort by the specified metric
            sort_col = parsed["metric"]
            df = df.sort_values(by=sort_col, ascending=False)

            # Add rank column
            df["rank"] = range(1, len(df) + 1)

            # Filter to requested rank or top N
            if parsed["rank"]:
                df = df[df["rank"] == parsed["rank"]]
            elif parsed["top_n"]:
                df = df.head(parsed["top_n"])
            else:
                df = df.head(10)  # Default to top 10

            # Select relevant columns for display
            display_cols = ["rank", "name", "artist", "popularity", "album"]
            return df[display_cols]

    def get_artist_details(self, artist_name: str, genre: str) -> Dict:
        """
        Get detailed information about a specific artist.

        Args:
            artist_name: Name of the artist
            genre: Genre to search within

        Returns:
            Dictionary with artist details
        """
        artists = self.explorer.search_artists_by_genre(genre, limit=50)

        # Find artist by name (case-insensitive)
        artist_name_lower = artist_name.lower()
        for artist in artists:
            if artist["name"].lower() == artist_name_lower:
                # Get top tracks
                top_tracks = self.explorer.get_artist_top_tracks(artist["id"])
                artist["top_tracks"] = top_tracks
                return artist

        return None
