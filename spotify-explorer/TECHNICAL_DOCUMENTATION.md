# Spotify Explorer - Technical Documentation

## Overview

Spotify Explorer is a command-line tool that queries **global Spotify catalog data** using the Spotify Web API. It allows users to discover popular artists and tracks within specific music genres without requiring any personal user data or authentication.

## Architecture

### Components

```
┌─────────────────┐
│   main.py       │  Interactive CLI - Menu-driven user interface
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│spotify_client.py│  API Client - Handles all Spotify API interactions
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Spotify API    │  Web API - Global music catalog data
└─────────────────┘
         │
         ▼
┌─────────────────┐
│  cache/         │  Local JSON files - 24-hour cached results
└─────────────────┘
```

## Authentication

### Client Credentials Flow

The application uses **Spotify's Client Credentials Flow**, which:
- Does NOT require user login or authorization
- Does NOT access personal playlists, listening history, or user data
- Only accesses **publicly available catalog information**
- Requires only a Client ID and Client Secret from the Spotify Developer Dashboard

**What this means:**
- No OAuth redirect flows
- No access tokens tied to specific users
- Simple, app-level authentication
- Read-only access to public data

### Credentials Required

```env
SPOTIFY_CLIENT_ID=<your_app_client_id>
SPOTIFY_CLIENT_SECRET=<your_app_secret>
```

These are obtained by creating an app at https://developer.spotify.com/dashboard

## What the API Actually Fetches

### 1. Artist Search (`search_artists_by_genre`)

**API Endpoint Used:** `GET /v1/search?type=artist`

**What it does:**
1. Searches Spotify's catalog for artists matching the genre query
2. Uses multiple search strategies:
   - `genre:"drum and bass"` - Formal genre query
   - `drum and bass` - General text search
   - `drum and bass music` - Broader text search
3. Fetches multiple pages (offset 0 and 50) for comprehensive results
4. Returns up to 50 results per search term per page

**Data Retrieved for Each Artist:**
```json
{
  "id": "spotify_artist_id",
  "name": "Artist Name",
  "followers": {
    "total": 1234567  // Number of Spotify followers
  },
  "popularity": 85,  // Spotify popularity score (0-100)
  "genres": ["drum-and-bass", "electronic", "jungle"],
  "external_urls": {
    "spotify": "https://open.spotify.com/artist/..."
  },
  "images": [...]  // Album artwork URLs
}
```

**What "popularity" means:**
- A value between 0-100 calculated by Spotify's algorithm
- Based on **total number of plays** and **how recent those plays are**
- Updated in real-time by Spotify
- More recent plays count more than older plays
- This is **NOT** personal data - it's a global metric

**What "followers" means:**
- Total number of Spotify users who follow this artist
- Global count across all Spotify users
- Public information available to everyone

**Filtering Applied:**
- Only includes artists whose genre tags contain the search term
- Deduplicates by artist ID
- Sorts by: popularity → followers → name (for consistency)

### 2. Track Search (`search_tracks_by_genre`)

**API Endpoint Used:** `GET /v1/search?type=track` and `GET /v1/artists/{id}`

**What it does:**
1. Searches for tracks with genre-related queries
2. For each track found, fetches the artist's information
3. Verifies the artist actually has the matching genre
4. This two-step process ensures accurate genre matching

**Data Retrieved for Each Track:**
```json
{
  "id": "spotify_track_id",
  "name": "Track Name",
  "artists": [{
    "id": "artist_id",
    "name": "Artist Name"
  }],
  "album": {
    "name": "Album Name"
  },
  "popularity": 78,  // Track popularity (0-100)
  "external_urls": {
    "spotify": "https://open.spotify.com/track/..."
  }
}
```

**Track Popularity:**
- Similar to artist popularity but for individual tracks
- Based on play counts and recency
- Tracks from albums released recently get a boost
- Independent of artist popularity

**Why we fetch artist data too:**
- Tracks don't have genre tags themselves
- We need to check if the track's artist matches the genre
- Ensures results are actually from the requested genre

### 3. Genre Discovery (`get_available_genres`)

**API Endpoint Used:** `GET /v1/search?type=artist`

**What it does:**
1. Searches for popular artists across 28 broad music categories
2. Collects all unique genre tags from those artists
3. Builds a comprehensive list of available genres
4. Caches results for 7 days

**Categories Searched:**
```python
'rock', 'pop', 'hip hop', 'jazz', 'electronic', 'classical',
'metal', 'country', 'folk', 'blues', 'reggae', 'soul',
'funk', 'disco', 'house', 'techno', 'trance', 'dubstep',
'indie', 'alternative', 'punk', 'r&b', 'latin', 'world',
'ambient', 'experimental', 'acoustic', 'dance'
```

**Result:**
- A list of 200-500 unique genre strings
- These are the actual genre tags Spotify uses in their catalog
- Examples: `"drum-and-bass"`, `"deep-house"`, `"indie-rock"`

**Why we do this:**
- Spotify's official genre seed endpoint was deprecated
- This approach discovers genres that actually exist in current catalog
- More accurate than a hardcoded list

## Caching System

### Purpose
- Reduce API calls (Spotify has rate limits)
- Ensure consistent results (same query = same results)
- Improve response time (instant results after first search)

### Cache Structure

```
cache/
├── artists_drum_and_bass.json    # Artist search results
├── artists_techno.json
├── tracks_drum_and_bass.json     # Track search results
├── tracks_techno.json
└── all_genres.json               # Available genres list
```

### Cache Lifetime

| Data Type | Cache Duration | Reason |
|-----------|----------------|--------|
| Artist search | 24 hours | Popularity changes daily |
| Track search | 24 hours | Popularity changes daily |
| Genre list | 7 days | Genres don't change often |

### Cache Validation

```python
cache_age = current_time - file_modification_time
if cache_age < expiration_time:
    return cached_data  # Use cache
else:
    fetch_fresh_data()  # Re-fetch from API
```

## Data Flow Example

### Searching for "second most popular drum and bass artist"

```
1. User Input
   ├─> Menu option: 1 (Search artists)
   ├─> Genre: "drum and bass"
   ├─> Limit: 10
   └─> Sort by: Popularity

2. Check Cache
   ├─> File: cache/artists_drum_and_bass.json
   └─> If exists & < 24 hours old → Use cached data ✓
       Else → Fetch from API ↓

3. API Request #1
   ├─> Search: genre:"drum and bass"
   ├─> Type: artist
   ├─> Limit: 50, Offset: 0
   └─> Returns: ~50 artists

4. API Request #2
   ├─> Search: genre:"drum and bass"
   ├─> Limit: 50, Offset: 50
   └─> Returns: ~50 more artists

5. API Request #3-4
   └─> Repeat with different search terms
       ("drum and bass", "drum and bass music")

6. Filter Results
   ├─> Keep only artists with "drum and bass" in genres
   ├─> Deduplicate by artist ID
   └─> Total collected: ~100-150 unique artists

7. Sort Results
   ├─> Primary: popularity (descending)
   ├─> Secondary: followers (descending)
   └─> Tertiary: name (alphabetically)

8. Cache Results
   └─> Save to cache/artists_drum_and_bass.json

9. Display Results
   ├─> Rank #1: Artist with highest popularity
   ├─> Rank #2: Second highest popularity  ← User's request
   ├─> Rank #3-10: Continue...
   └─> Format as table with followers, popularity, genres

10. User Drilldown (Optional)
    └─> View detailed info for rank #2
        ├─> Followers: 1,234,567
        ├─> Popularity: 85/100
        ├─> Genres: drum-and-bass, electronic, jungle
        └─> Spotify link
```

## API Rate Limits

### Spotify's Limits
- **Standard free tier:** ~180 requests per minute
- **Per-user:** Rate limits apply per client credentials
- **Retries:** Spotify returns 429 status if exceeded

### How We Handle It
1. **Caching:** Dramatically reduces API calls
2. **Batching:** Fetch 50 results per call (maximum allowed)
3. **Error handling:** Gracefully continue if a search fails
4. **User control:** "Clear cache" option to manually refresh

### Typical Usage

| Action | API Calls | Notes |
|--------|-----------|-------|
| First artist search | 4-8 | Multiple search terms × pages |
| Repeated artist search | 0 | Uses cache |
| First track search | 50-100 | Also fetches artist info per track |
| Repeated track search | 0 | Uses cache |
| Browse genres (first time) | 30-50 | Samples many categories |
| Browse genres (cached) | 0 | 7-day cache |

## Data Accuracy & Limitations

### What's Accurate
✅ **Artist follower counts** - Real-time Spotify data
✅ **Popularity scores** - Updated frequently by Spotify
✅ **Genre tags** - How artists tag themselves on Spotify
✅ **Artist/track names** - Official Spotify catalog data

### What's NOT Available
❌ **Exact play counts** - Spotify doesn't expose this via API
❌ **Personal listening data** - We use Client Credentials (no user access)
❌ **Historical trends** - Only current snapshot data
❌ **Geographical data** - Can't filter by country/region

### Limitations

1. **Genre Matching**
   - Depends on how artists tag their music
   - Some artists might not tag genres accurately
   - Multi-genre artists may not appear in narrow genre searches

2. **Popularity Algorithm**
   - Spotify's proprietary algorithm
   - Heavily weighs recent plays over older ones
   - May not reflect "all-time" popularity

3. **Search Completeness**
   - API returns top matches, not exhaustive lists
   - Niche artists might not appear
   - Limited to what Spotify's search algorithm returns

4. **Real-time vs Cached**
   - Cached data is up to 24 hours old
   - Popularity/followers may have changed since caching
   - Use "Clear cache" for freshest data

## Privacy & Data Usage

### What Data We Store Locally
- Artist names, IDs, popularity, followers, genres
- Track names, IDs, popularity, album names
- Genre lists
- All stored in plain JSON files in `cache/` directory

### What Data We DON'T Store
- No user information
- No listening history
- No personal preferences
- No authentication tokens (regenerated per session)

### GDPR Compliance
- All data is publicly available from Spotify's catalog
- No personal data processing
- No user tracking
- Cache can be deleted anytime (just delete `cache/` folder)

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| 401 Unauthorized | Invalid credentials | Check .env file |
| 404 Not Found | Invalid endpoint | Update spotipy library |
| 429 Too Many Requests | Rate limit exceeded | Wait & use cached data |
| Empty results | Genre not found | Try different genre name |

### Graceful Degradation

1. If a search term fails → Continue with other terms
2. If cache is corrupted → Re-fetch from API
3. If genre endpoint fails → Use fallback genre list
4. If artist fetch fails → Skip that artist, continue

## Performance

### First Search (No Cache)
- **Artists:** 3-5 seconds (multiple API calls)
- **Tracks:** 10-30 seconds (verifies each track's artist)
- **Genres:** 10-20 seconds first time only

### Subsequent Searches (Cached)
- **Artists:** < 0.1 seconds (instant)
- **Tracks:** < 0.1 seconds (instant)
- **Genres:** < 0.1 seconds (instant)

### Optimization Strategies
1. Multi-page fetching reduces total API calls
2. Genre verification done in batch where possible
3. Dictionary-based deduplication is O(1)
4. Sorting is O(n log n) but on limited dataset

## Future Improvements

### Potential Enhancements
1. **Add country filtering** - Use market parameter in API
2. **Time range queries** - "Top artists this month"
3. **Related artists** - Discover similar artists
4. **Audio features** - Query by tempo, energy, danceability
5. **Export results** - Save to CSV/JSON
6. **Visualization** - Charts and graphs
7. **Comparison mode** - Compare two genres

### API Limitations to Consider
- Can't get exact streaming numbers
- Can't get historical data (past popularity)
- Can't access user-specific data with Client Credentials
- Rate limits prevent massive data collection

## Conclusion

Spotify Explorer works by:
1. **Authenticating** with app-level credentials (no user login)
2. **Searching** Spotify's public catalog using their Web API
3. **Filtering** results by genre matching
4. **Caching** results locally for speed and consistency
5. **Presenting** data in an easy-to-read format

All data comes from **Spotify's global public catalog** - the same data you see when browsing Spotify without logging in. The "popularity" and "followers" metrics reflect **global user behavior**, not any individual's listening habits.
