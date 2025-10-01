# Spotify Explorer

Query global Spotify statistics using natural language! Ask questions like "second most listened artist in the drum and bass genre" and get instant answers.

## Features

- 🎵 Query global Spotify data (not personal listening history)
- 🔍 Natural language query processing
- 📊 Search by genre, popularity, and followers
- 💾 Smart caching to reduce API calls
- 🎨 Beautiful table formatting in the terminal

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

## Project Structure

```
spotify-explorer/
├── main.py              # Interactive CLI interface
├── query_engine.py      # Natural language query parser
├── spotify_client.py    # Spotify API client wrapper
├── requirements.txt     # Python dependencies
├── .env                 # API credentials (create this)
├── .gitignore          # Git ignore file
└── cache/              # Cached query results (auto-created)
```

## Tips

- Be specific with genre names (e.g., "drum and bass" not just "dnb")
- You can use ordinal numbers (first, second, third) or "top N" format
- The app uses Spotify's public data, so results reflect global popularity
- Cache is automatically cleared after 24 hours
- Use the `clear` command to manually refresh data

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
