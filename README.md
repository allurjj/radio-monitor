# Radio Monitor

**Version:** 1.2.8.1
**License:** GNU General Public License v3.0

---

## What's New

**v1.2.8.1 (2026-04-08) - Hotfix - MBID Editing**
- Fixed MBID editing validation to allow artist merges
- Duplicate MBID now shows as warning instead of blocking error
- Users can now merge artists like "Brooks Dunn" into "Brooks & Dunn"

**v1.2.8 (2026-04-07) - MBID Editing Improvements**
- Fixed MBID editing to use direct MBID lookup instead of name-based fuzzy matching
- Manual MBID edits now automatically save to overrides table for future scrapes
- Eliminated 150+ lines of complex fuzzy matching code
- Improved reliability: MBID editing now works 100% of the time
- Set-it-and-forget-it: Fix an artist once, and future scrapes will use the correct MBID automatically

**v1.2.7 (2026-04-07) - Bug Fixes**
- Fixed Plex Overrides page not loading (template inheritance)
- Fixed manual match error in Plex Failures (Plex connection check)

**v1.2.6 (2026-04-07) - Bug Fixes**
- Fixed crashes from NULL artist MBIDs during scraping
- Fixed Internal Server Error when clicking artist links from song pages
- Fixed orphaned artists (0 songs) unable to be deleted
- Added database migration to automatically fix existing NULL values
- Cleaned up orphaned artists from multi-artist collaborations

---

## About

Radio Monitor is a web application that automatically discovers music from radio stations and integrates with your personal media library.

### What It Does

- **Monitors Radio Stations** - Automatically scrapes 28 radio stations to identify songs playing in real-time
- **Discovers New Music** - Identifies artists and songs using the MusicBrainz database
- **Integrates with Lidarr** - One-click import of discovered artists to your Lidarr library
- **Creates Plex Playlists** - Automatically generate playlists in Plex based on radio play data
- **Manual Playlist Builder** - Create custom playlists by manually selecting songs from your catalog
- **AI-Powered Playlists** - Generate playlists using natural language instructions (experimental)
- **Blocklist Management** - Block specific artists or songs from appearing in auto-generated playlists
- **Web-Based Interface** - Modern browser-based GUI with real-time analytics and charts
- **Automated Scheduling** - Set up automatic scraping, importing, and playlist creation

---

## Getting Started

### Option 1: Docker (Recommended)

```bash
# Pull and run the latest image
docker run -d -p 5000:5000 -v $(pwd)/data:/app/data ghcr.io/allurjj/radio-monitor:latest

# Or use Docker Compose
git clone https://github.com/allurjj/radio-monitor.git
cd radio-monitor/docker
docker-compose up -d
```

### Option 2: Windows EXE

1. Download the latest `Radio-Monitor-v1.2.1.zip` from [Releases](https://github.com/allurjj/radio-monitor/releases)
2. Extract the ZIP file to a folder
3. Double-click `Radio Monitor.exe`

### Option 3: From Source

```bash
# Clone the repository
git clone https://github.com/allurjj/radio-monitor.git
cd radio-monitor

# Install dependencies
pip install -r requirements.txt

# Start the application
python -m radio_monitor.cli --gui
```

---

## Accessing the Web Interface

Once running, open your web browser and navigate to:

- **Windows:** http://127.0.0.1:5000
- **Linux/Mac:** http://localhost:5000
- **Docker:** http://localhost:5000

**Default Credentials:**
- Username: `admin`
- Password: `admin` (change immediately after first login)

---

## Features

### Radio Monitoring
- Monitors 28 pre-configured radio stations (Chicago, national, and genre stations)
- Real-time song identification with duplicate detection
- Station health tracking with automatic disable on failures
- Add custom stations through the web interface

### Music Library Integration
- **Lidarr Integration** - Import discovered artists with quality profile and root folder selection
- **Plex Integration** - Create dynamic playlists with 7 different modes (merge, replace, append, create, snapshot, recent, random)
- **Multi-Strategy Matching** - 6-strategy fuzzy matching with normalization for accurate Plex song identification
- **Manual Overrides** - Manually specify Plex track matches for songs that fail automatic matching
- **Various Artists Fallback** - Opt-in scanning of compilation albums when standard matching fails

### Playlist Creation
- **Automated Playlists** - Generate playlists based on play counts, date ranges, and station filters
- **Manual Playlist Builder** - Browse and manually select songs to create custom playlists
- **AI-Powered Playlists** - Use natural language to generate playlists ("Upbeat party songs", "Chill evening vibes")
- **Blocklist** - Exclude specific artists or songs from any playlist type

### Analytics & Monitoring
- Real-time dashboard with charts and statistics
- Play counts for songs and artists
- Activity timeline with filtering
- Export data to CSV

### Automation
- Schedule automatic radio scraping
- Auto-import new artists to Lidarr
- Auto-create Plex playlists on a schedule
- 17 notification providers (Discord, Slack, Email, Telegram, etc.)

---

## Command Line Options

```bash
# Start the web GUI
python -m radio_monitor.cli --gui

# Run a single scrape cycle
python -m radio_monitor.cli --scrape-once

# Import discovered artists to Lidarr
python -m radio_monitor.cli --import-lidarr

# Create Plex playlists
python -m radio_monitor.cli --create-playlists

# Backup the database
python -m radio_monitor.cli --backup-db

# Retry failed MusicBrainz lookups
python -m radio_monitor.cli --retry-pending

# Resolve multi-artist collaborations
python -m radio_monitor.cli --resolve-multi-artist

# Run system tests
python -m radio_monitor.cli --test
```

---

## Configuration

The application uses a `radio_monitor_settings.json` file for configuration. Key settings include:

- **Lidarr Integration** - URL and API key
- **Plex Integration** - URL and token
- **GUI Settings** - Host, port, and debug mode
- **Scraping Schedule** - How often to scrape stations
- **Duplicate Detection** - Time window for detecting duplicate plays

Configure these through the web interface at **Settings** or by editing the JSON file directly.

---

## Plex Matching Debug Tools

Two test scripts are included to help debug Plex matching issues:

### `test_plex_matching_simple.py` - Library Analysis
**Best for:** Quick library analysis and catalog browsing

```bash
# List popular artists in your library
python test_plex_matching_simple.py --list-artists

# Analyze an artist's complete catalog
python test_plex_matching_simple.py --artist "Nirvana" --analyze-catalog

# Watch for problematic albums (bootlegs, compilations)
python test_plex_matching_simple.py --artist "Nirvana" --analyze-catalog --watch-album "Greatest Hits"
```

**Features:**
- Shows all albums sorted by year
- Identifies missing year metadata ("NO YEAR")
- Displays track counts and version types (studio/remix/live)
- Highlights specific albums that might interfere with matching

### `test_plex_matching_advanced.py` - Production Matching Test
**Best for:** Testing actual song matching (uses Radio Monitor's production algorithm)

```bash
# Test if a specific song will be found
python test_plex_matching_advanced.py --artist "Tim McGraw" --song "Don't Take the Girl"

# Test multiple songs
python test_plex_matching_advanced.py --artist "Nirvana" --songs "Smells Like Teen Spirit" "Come As You Are"

# Enable debug mode to see matching details
python test_plex_matching_advanced.py --artist "Tim McGraw" --song "Don't Take the Girl" --debug
```

**Features:**
- Uses **same matching logic as Radio Monitor production**
- Handles apostrophes and Unicode correctly
- Shows which album/version will be selected
- Bypasses Plex search limitations

**When to use:**
- **Simple script:** Browse library, find albums with missing metadata
- **Advanced script:** Test if songs will actually match in production

---

## Documentation

- **Installation Guide:** [INSTALL.md](INSTALL.md)
- **API Documentation:** [API.md](API.md)
- **Troubleshooting:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md)

---

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

---

**Version:** 1.2.5
**Python:** 3.10+
**Last Updated:** 2026-03-09
