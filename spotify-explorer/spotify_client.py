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
        # Normalize genre for consistent caching and searching
        genre_normalized = genre.lower().strip()
        cache_key = genre_normalized.replace(" ", "_")
        cache_file = self.cache_dir / f"artists_{cache_key}.json"

        # Check cache (valid for 24 hours)
        if cache_file.exists():
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age < 86400:  # 24 hours
                with open(cache_file, "r") as f:
                    return json.load(f)

        artists_dict = {}  # Use dict to avoid duplicates by ID

        # Search for artists using multiple strategies
        # Use normalized genre for consistent results
        search_terms = [
            f'genre:"{genre_normalized}"',
            genre_normalized,
            f"{genre_normalized} music",
        ]

        for term in search_terms:
            try:
                # Get multiple pages of results for more comprehensive data
                for offset in [0, 50]:
                    results = self.sp.search(
                        q=term, type="artist", limit=50, offset=offset
                    )

                    for artist in results["artists"]["items"]:
                        artist_id = artist["id"]

                        # Skip if already processed
                        if artist_id in artists_dict:
                            continue

                        # Filter by genre match
                        artist_genres = [g.lower() for g in artist.get("genres", [])]

                        # Check if genre matches (exact or partial match)
                        if any(genre_normalized in g for g in artist_genres):
                            artists_dict[artist_id] = {
                                "id": artist_id,
                                "name": artist["name"],
                                "followers": artist["followers"]["total"],
                                "popularity": artist["popularity"],
                                "genres": artist["genres"],
                                "external_url": artist["external_urls"]["spotify"],
                                "images": artist["images"],
                            }

            except Exception as e:
                # Silently continue if a search fails
                continue

        # Convert to list and sort deterministically for consistent ordering
        # Sort by popularity, then followers, then name
        # This ensures the same artists appear in the same order
        artists = sorted(
            artists_dict.values(),
            key=lambda x: (x["popularity"], x["followers"], x["name"]),
            reverse=True,
        )

        # Cache ALL results (don't limit here)
        # Limiting will be done in main.py based on user preference
        with open(cache_file, "w") as f:
            json.dump(artists, f, indent=2)

        # Return all artists (main.py will handle limiting)
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
                "id": track["id"],
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
        # Normalize genre for consistent caching and searching
        genre_normalized = genre.lower().strip()
        cache_key = genre_normalized.replace(" ", "_")
        cache_file = self.cache_dir / f"tracks_{cache_key}.json"

        # Check cache
        if cache_file.exists():
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age < 86400:  # 24 hours
                with open(cache_file, "r") as f:
                    return json.load(f)

        tracks_dict = {}  # Use dict to avoid duplicates by ID

        # Search with multiple strategies for comprehensive results
        search_terms = [
            f'genre:"{genre_normalized}"',
            f"{genre_normalized} music",
        ]

        for term in search_terms:
            try:
                # Get multiple pages of results
                for offset in [0, 50]:
                    results = self.sp.search(
                        q=term, type="track", limit=50, offset=offset
                    )

                    for track in results["tracks"]["items"]:
                        track_id = track["id"]

                        # Skip if already processed
                        if track_id in tracks_dict:
                            continue

                        # Verify track artist has matching genre
                        artist = self.sp.artist(track["artists"][0]["id"])
                        artist_genres = [g.lower() for g in artist.get("genres", [])]

                        if any(genre_normalized in g for g in artist_genres):
                            tracks_dict[track_id] = {
                                "id": track_id,
                                "name": track["name"],
                                "artist": track["artists"][0]["name"],
                                "artist_id": track["artists"][0]["id"],
                                "popularity": track["popularity"],
                                "album": track["album"]["name"],
                                "external_url": track["external_urls"]["spotify"],
                            }

            except Exception:
                # Silently continue if a search fails
                continue

        # Convert to list and sort deterministically
        # Sort by popularity, then name for consistency
        tracks = sorted(
            tracks_dict.values(),
            key=lambda x: (x["popularity"], x["name"]),
            reverse=True,
        )

        # Cache ALL results (don't limit here)
        with open(cache_file, "w") as f:
            json.dump(tracks, f, indent=2)

        # Return all tracks (main.py will handle limiting)
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

    def get_top_tracks_from_top_artists(
        self, genre: str, num_artists: int = 50, tracks_per_artist: int = 5
    ) -> List[Dict]:
        """
        Get top tracks from the most followed artists in a genre.

        Args:
            genre: Genre name
            num_artists: Number of top artists to include (default: 50)
            tracks_per_artist: Number of top tracks per artist (default: 5, max: 10)

        Returns:
            List of track dictionaries with artist info
        """
        # Normalize genre for consistent caching
        genre_normalized = genre.lower().strip()
        cache_key = genre_normalized.replace(" ", "_")
        cache_file = self.cache_dir / f"top_tracks_top_artists_{cache_key}.json"

        # Check cache (valid for 24 hours)
        if cache_file.exists():
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age < 86400:  # 24 hours
                with open(cache_file, "r") as f:
                    return json.load(f)

        print(f"Fetching top {num_artists} artists in '{genre}'...")
        
        # Get artists sorted by followers
        artists = self.search_artists_by_genre(genre, limit=100)
        
        if not artists:
            return []
        
        # Sort by followers (most followed first) and take top N
        artists_sorted_desc = sorted(
            artists, key=lambda x: x["followers"], reverse=True
        )[:num_artists]
        
        print(f"Found {len(artists_sorted_desc)} artists. Fetching top tracks...")
        
        tracks_per_artist = min(tracks_per_artist, 10)  # Spotify limit is 10
        
        # Store artist tracks: artist_id -> list of track dicts
        artist_track_lists = {}
        
        # Maps track_id -> {"artist_id": str, "followers": int}
        track_assignments = {}
        
        # First pass: get all top tracks for all artists (in desc order)
        for i, artist in enumerate(artists_sorted_desc, 1):
            try:
                print(f"  [{i}/{len(artists_sorted_desc)}] {artist['name']}")
                top_tracks = self.get_artist_top_tracks(artist["id"])
                artist_track_lists[artist["id"]] = {
                    "artist": artist,
                    "top_tracks": top_tracks,
                    "assigned_tracks": []
                }
            except Exception as e:
                print(f"    ⚠️  Error: {artist['name']}: {e}")
                continue
        
        # Sort artists in ASCENDING order (least followed first)
        # This ensures least followed artists get first pick of shared tracks
        artists_sorted_asc = sorted(
            artists_sorted_desc, key=lambda x: x["followers"]
        )
        
        # Second pass: assign tracks, avoiding duplicates
        # Process in ascending order so least followed picks first
        for artist in artists_sorted_asc:
            artist_id = artist["id"]
            
            if artist_id not in artist_track_lists:
                continue
            
            artist_data = artist_track_lists[artist_id]
            top_tracks = artist_data["top_tracks"]
            assigned_tracks = artist_data["assigned_tracks"]
            
            track_idx = 0
            while (len(assigned_tracks) < tracks_per_artist and
                   track_idx < len(top_tracks)):
                track = top_tracks[track_idx]
                track_id = track["id"]
                track_idx += 1
                
                # Check if already assigned
                if track_id in track_assignments:
                    assigned_to = track_assignments[track_id]
                    
                    # If current artist has FEWER followers, steal it
                    if artist["followers"] < assigned_to["followers"]:
                        # Remove from previous artist
                        prev_artist_data = artist_track_lists[assigned_to["id"]]
                        prev_artist_data["assigned_tracks"] = [
                            t for t in prev_artist_data["assigned_tracks"]
                            if t["id"] != track_id
                        ]
                        
                        # Assign to current artist
                        track_assignments[track_id] = {
                            "id": artist_id,
                            "followers": artist["followers"]
                        }
                        
                        assigned_tracks.append({
                            "id": track_id,
                            "name": track["name"],
                            "artist": artist["name"],
                            "artist_id": artist_id,
                            "artist_followers": artist["followers"],
                            "popularity": track["popularity"],
                            "album": track["album"],
                            "external_url": track["external_url"],
                        })
                    # else: skip, keep looking
                else:
                    # New track, assign it
                    track_assignments[track_id] = {
                        "id": artist_id,
                        "followers": artist["followers"]
                    }
                    
                    assigned_tracks.append({
                        "id": track_id,
                        "name": track["name"],
                        "artist": artist["name"],
                        "artist_id": artist_id,
                        "artist_followers": artist["followers"],
                        "popularity": track["popularity"],
                        "album": track["album"],
                        "external_url": track["external_url"],
                    })
        
        # Third pass: backfill artists who lost tracks
        # Process in ascending order again for consistency
        for artist in artists_sorted_asc:
            artist_id = artist["id"]
            
            if artist_id not in artist_track_lists:
                continue
            
            artist_data = artist_track_lists[artist_id]
            top_tracks = artist_data["top_tracks"]
            assigned_tracks = artist_data["assigned_tracks"]
            
            # If this artist needs more tracks
            if len(assigned_tracks) < tracks_per_artist:
                # Look through remaining tracks
                for track in top_tracks:
                    if len(assigned_tracks) >= tracks_per_artist:
                        break
                    
                    track_id = track["id"]
                    
                    # Skip if already in this artist's list
                    if any(t["id"] == track_id for t in assigned_tracks):
                        continue
                    
                    # Skip if assigned to someone else
                    if track_id in track_assignments:
                        continue
                    
                    # Add this track
                    track_assignments[track_id] = {
                        "id": artist_id,
                        "followers": artist["followers"]
                    }
                    
                    assigned_tracks.append({
                        "id": track_id,
                        "name": track["name"],
                        "artist": artist["name"],
                        "artist_id": artist_id,
                        "artist_followers": artist["followers"],
                        "popularity": track["popularity"],
                        "album": track["album"],
                        "external_url": track["external_url"],
                    })
        
        # Collect all tracks
        all_tracks = []
        for artist_data in artist_track_lists.values():
            all_tracks.extend(artist_data["assigned_tracks"])
        
        # Cache the results
        with open(cache_file, "w") as f:
            json.dump(all_tracks, f, indent=2)
        
        num_artists = len(artists_sorted_desc)
        print(f"✓ Collected {len(all_tracks)} tracks from {num_artists} artists")
        
        return all_tracks

    def search_artist_by_name(self, artist_name: str) -> List[Dict]:
        """
        Search for artists by name and return their details with genres.

        Args:
            artist_name: Artist name to search for

        Returns:
            List of matching artist dictionaries with details
        """
        try:
            results = self.sp.search(q=f'artist:{artist_name}', type='artist', limit=10)
            
            artists = []
            for artist in results['artists']['items']:
                artists.append({
                    'id': artist['id'],
                    'name': artist['name'],
                    'followers': artist['followers']['total'],
                    'popularity': artist['popularity'],
                    'genres': artist['genres'],
                    'external_url': artist['external_urls']['spotify'],
                    'images': artist['images']
                })
            
            return artists
        except Exception as e:
            print(f"Error searching for artist: {e}")
            return []

    def clear_cache(self):
        """Clear all cached data."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
        print("Cache cleared!")
