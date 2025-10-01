"""
Spotify API client for accessing global music data.
Uses client credentials flow (no user authentication needed).
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials

# Load environment variables
load_dotenv()


class SpotifyExplorer:
    """Client for exploring global Spotify data."""

    def __init__(self):
        """Initialize Spotify client with credentials."""
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

        if not client_id or not client_secret:
            raise ValueError(
                "Missing Spotify credentials. Please set SPOTIFY_CLIENT_ID "
                "and SPOTIFY_CLIENT_SECRET in .env file"
            )

        auth_manager = SpotifyClientCredentials(
            client_id=client_id, client_secret=client_secret
        )
        self.sp = spotipy.Spotify(auth_manager=auth_manager)
        self.cache_dir = Path(__file__).parent / "cache"
        self.cache_dir.mkdir(exist_ok=True)

    def search_artists_by_genre(self, genre: str, limit: int = 50) -> List[Dict]:
        """
        Search for popular artists in a specific genre.

        Args:
            genre: Genre name (e.g., "drum and bass", "techno", "jazz")
            limit: Maximum number of artists to return

        Returns:
            List of artist dictionaries with name, followers, popularity, genres
        """
        cache_file = self.cache_dir / f"artists_{genre.replace(' ', '_')}.json"

        # Check cache (valid for 24 hours)
        if cache_file.exists():
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age < 86400:  # 24 hours
                with open(cache_file, "r") as f:
                    return json.load(f)

        artists = []

        # Search for artists using the genre as a query
        # We'll do multiple searches with different terms to get more results
        search_terms = [f'genre:"{genre}"', genre]

        seen_ids = set()

        for term in search_terms:
            try:
                results = self.sp.search(q=term, type="artist", limit=min(limit, 50))

                for artist in results["artists"]["items"]:
                    if artist["id"] not in seen_ids:
                        seen_ids.add(artist["id"])

                        # Filter by genre match
                        artist_genres = [g.lower() for g in artist.get("genres", [])]
                        genre_lower = genre.lower()

                        # Check if genre matches (exact or partial match)
                        if any(genre_lower in g for g in artist_genres):
                            artists.append(
                                {
                                    "id": artist["id"],
                                    "name": artist["name"],
                                    "followers": artist["followers"]["total"],
                                    "popularity": artist["popularity"],
                                    "genres": artist["genres"],
                                    "external_url": artist["external_urls"]["spotify"],
                                    "images": artist["images"],
                                }
                            )

                if len(artists) >= limit:
                    break

            except Exception as e:
                print(f"Error searching with term '{term}': {e}")
                continue

        # Sort by popularity and followers
        artists.sort(key=lambda x: (x["popularity"], x["followers"]), reverse=True)
        artists = artists[:limit]

        # Cache results
        with open(cache_file, "w") as f:
            json.dump(artists, f, indent=2)

        return artists

    def get_artist_details(self, artist_id: str) -> Dict:
        """
        Get detailed information about an artist.

        Args:
            artist_id: Spotify artist ID

        Returns:
            Dictionary with artist details
        """
        artist = self.sp.artist(artist_id)
        return {
            "id": artist["id"],
            "name": artist["name"],
            "followers": artist["followers"]["total"],
            "popularity": artist["popularity"],
            "genres": artist["genres"],
            "external_url": artist["external_urls"]["spotify"],
            "images": artist["images"],
        }

    def get_artist_top_tracks(self, artist_id: str, country: str = "US") -> List[Dict]:
        """
        Get top tracks for an artist.

        Args:
            artist_id: Spotify artist ID
            country: Country code (default: US)

        Returns:
            List of track dictionaries
        """
        tracks = self.sp.artist_top_tracks(artist_id, country=country)
        return [
            {
                "name": track["name"],
                "popularity": track["popularity"],
                "album": track["album"]["name"],
                "external_url": track["external_urls"]["spotify"],
            }
            for track in tracks["tracks"]
        ]

    def search_tracks_by_genre(self, genre: str, limit: int = 50) -> List[Dict]:
        """
        Search for popular tracks in a specific genre.

        Args:
            genre: Genre name
            limit: Maximum number of tracks to return

        Returns:
            List of track dictionaries
        """
        cache_file = self.cache_dir / f"tracks_{genre.replace(' ', '_')}.json"

        # Check cache
        if cache_file.exists():
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age < 86400:  # 24 hours
                with open(cache_file, "r") as f:
                    return json.load(f)

        tracks = []

        try:
            results = self.sp.search(
                q=f'genre:"{genre}"', type="track", limit=min(limit, 50)
            )

            for track in results["tracks"]["items"]:
                tracks.append(
                    {
                        "id": track["id"],
                        "name": track["name"],
                        "artist": track["artists"][0]["name"],
                        "artist_id": track["artists"][0]["id"],
                        "popularity": track["popularity"],
                        "album": track["album"]["name"],
                        "external_url": track["external_urls"]["spotify"],
                    }
                )

        except Exception as e:
            print(f"Error searching tracks: {e}")

        # Sort by popularity
        tracks.sort(key=lambda x: x["popularity"], reverse=True)

        # Cache results
        with open(cache_file, "w") as f:
            json.dump(tracks, f, indent=2)

        return tracks

    def get_available_genres(self) -> List[str]:
        """
        Get list of available genres by sampling popular artists.

        Since Spotify's genre seed endpoint is deprecated, we collect
        genres from popular artists across different categories.

        Returns:
            List of unique genre strings
        """
        cache_file = self.cache_dir / "all_genres.json"

        # Check cache (valid for 7 days)
        if cache_file.exists():
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age < 604800:  # 7 days
                with open(cache_file, "r") as f:
                    return json.load(f)

        print("Building genre list from popular artists (this may take a moment)...")

        genres_set = set()

        # Search across various broad categories to collect genres
        search_terms = [
            "rock",
            "pop",
            "hip hop",
            "jazz",
            "electronic",
            "classical",
            "metal",
            "country",
            "folk",
            "blues",
            "reggae",
            "soul",
            "funk",
            "disco",
            "house",
            "techno",
            "trance",
            "dubstep",
            "indie",
            "alternative",
            "punk",
            "r&b",
            "latin",
            "world",
            "ambient",
            "experimental",
            "acoustic",
            "dance",
        ]

        try:
            for term in search_terms:
                try:
                    results = self.sp.search(q=term, type="artist", limit=50)
                    for artist in results["artists"]["items"]:
                        for genre in artist.get("genres", []):
                            genres_set.add(genre)
                except Exception:
                    continue

            genres_list = sorted(list(genres_set))

            # Cache the results
            with open(cache_file, "w") as f:
                json.dump(genres_list, f, indent=2)

            return genres_list

        except Exception as e:
            print(f"Error fetching genres: {e}")
            # Return a basic fallback list
            return [
                "acoustic",
                "ambient",
                "alternative",
                "blues",
                "classical",
                "country",
                "dance",
                "disco",
                "drum and bass",
                "dubstep",
                "edm",
                "electronic",
                "folk",
                "funk",
                "hip hop",
                "house",
                "indie",
                "jazz",
                "latin",
                "metal",
                "pop",
                "punk",
                "r&b",
                "rap",
                "reggae",
                "rock",
                "soul",
                "techno",
                "trance",
            ]

    def search_genres(self, query: str) -> List[str]:
        """
        Search for genres matching a query string.

        Args:
            query: Search term (e.g., "bass", "rock", "electronic")

        Returns:
            List of matching genre strings
        """
        all_genres = self.get_available_genres()
        query_lower = query.lower()

        # Find genres containing the query string
        matching = [g for g in all_genres if query_lower in g.lower()]

        return matching

    def clear_cache(self):
        """Clear all cached data."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
        print("Cache cleared!")
