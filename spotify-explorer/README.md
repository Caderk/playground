# Spotify Explorer

Query global Spotify statistics using natural language! Ask questions like "second most listened artist in the drum and bass genre" and get instant answers.

## Features

- 🎵 Query global Spotify data (not personal listening history)
- 🔍 Search by genre, popularity, and followers
- 🎤 **Build playlists from top songs of the most followed artists**
- 📊 Browse available genres
- 💾 Smart caching to reduce API calls
- 🎨 Beautiful table formatting in the terminal
- 📝 **Export track results to importable playlist files**

## Setup

### 1. Get Spotify API Credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account
3. Click "Create an App"
4. Give it a name (e.g., "Spotify Explorer")
5. Copy your **Client ID** and **Client Secret**

### 2. Install Dependencies

```bash
# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

### 3. Configure Credentials

Create a `.env` file in the `spotify-explorer` directory:

```env
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
```

## Usage

Run the interactive CLI:

```bash
python main.py
```

### Example Queries

**Artists:**

```
🎵 Query: second most listened artist in the drum and bass genre
🎵 Query: top 5 artists in techno
🎵 Query: most popular artist in jazz
🎵 Query: third artist in hip hop
🎵 Query: top 10 artists in indie rock
🎵 Query: most followed artist in electronic
```

**Tracks:**

```
🎵 Query: most popular track in drum and bass
🎵 Query: top 5 songs in techno
🎵 Query: second most popular track in jazz
```

**Playlist Builder:**

```
🎵 Get top songs from the 50 most followed artists in a genre
🎵 Customize: number of artists (1-50) and tracks per artist (1-10)
🎵 Example: 50 artists × 5 tracks = 250 track playlist
🎵 Perfect for discovering the best tracks in any genre
```

**Commands:**

```
🎵 Query: help       # Show help and examples
🎵 Query: clear      # Clear cached data
🎵 Query: quit       # Exit the program
```

## How It Works

1. **Query Parsing**: Your natural language query is parsed to extract:

   - Genre (e.g., "drum and bass")
   - Rank (e.g., "second", "top 5")
   - Type (artist or track)
   - Metric (popularity or followers)

2. **Data Fetching**: The app searches Spotify's global catalog for artists/tracks matching your genre

3. **Ranking**: Results are sorted by the specified metric (popularity/followers)

4. **Caching**: Results are cached for 24 hours to speed up repeated queries

## Building Playlists from Top Artists

**New Feature!** Get the best tracks from the most followed artists in any genre:

1. Select option 3 (Get top songs from top artists)
2. Enter a genre (e.g., "techno", "drum and bass")
3. Choose number of top artists (default: 50)
4. Choose tracks per artist (default: 5)
5. Export to a playlist file
6. Import into Spotify!

**Example Workflow:**

```
Genre: techno
Top artists: 50 (most followed)
Tracks per artist: 5 (their top songs)
Total: ~250 tracks

Result: A comprehensive playlist of the best techno tracks
        from the genre's most popular artists!
```

## Exporting Playlists

When viewing track search results or playlist builder results, you can export them:

1. Search for tracks (option 2) or use playlist builder (option 3)
2. When prompted "Export to playlist file? (y/n)", type `y`
3. File will be saved to `exports/` folder with format: `genre_timestamp.txt`
4. Open the file and copy all `spotify:track:...` lines
5. In Spotify Desktop app, create a new playlist
6. Click in the playlist and paste (Ctrl+V / Cmd+V)
7. All tracks will be added automatically!

**Example:**

```
Genre: techno
Results: 250 tracks
Export: exports/techno_20251006_143022.txt
```

## Project Structure

```
spotify-explorer/
├── main.py              # Interactive CLI interface
├── spotify_client.py    # Spotify API client wrapper
├── requirements.txt     # Python dependencies
├── .env                 # API credentials (create this)
├── .gitignore          # Git ignore file
├── cache/              # Cached query results (auto-created)
└── exports/            # Exported playlist files (auto-created)
```

## Tips

- Be specific with genre names (e.g., "drum and bass" not just "dnb")
- Use option 3 to browse available genres before searching
- The app uses Spotify's public data, so results reflect global popularity
- Genre names are **case-insensitive** ("Hard Techno" = "hard techno")
- Results are **cached for 24 hours** for consistency and speed
- Use the `clear cache` command to get fresh data from Spotify
- The first search for a genre will take longer as it fetches comprehensive data
- Subsequent searches for the same genre will be instant (using cached data)

## Limitations

- Searches are limited by Spotify's public API capabilities
- Genre matching depends on how artists tag their music on Spotify
- Some niche genres may have limited results
- Results are based on Spotify's popularity algorithm, not streaming counts

## Troubleshooting

**"Missing Spotify credentials" error:**

- Make sure you created the `.env` file
- Check that your Client ID and Secret are correct
- Ensure the `.env` file is in the same directory as the Python files

**"No results found":**

- Try a more common genre name
- Check the spelling of your genre
- Try searching for "artists in [genre]" first to verify the genre exists

**API rate limiting:**

- Use the cached results (automatic)
- Wait a few minutes before trying again
- Use the `clear` command sparingly

## License

MIT License - Feel free to modify and use for your own projects!

## Contributing

Found a bug or want to add a feature? Feel free to open an issue or submit a pull request!
