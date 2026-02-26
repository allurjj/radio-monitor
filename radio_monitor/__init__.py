"""
Radio Monitor 1.0 - Package Architecture

This package provides a modular radio station monitoring system with the following
architecture:

Package Structure:
------------------
radio_monitor/
├── __init__.py           # Package initialization (this file)
├── database.py           # Database schema, queries, migrations
├── scrapers.py           # Station scraping iHeartRadio)
├── mbid.py              # MusicBrainz API lookups
├── lidarr.py            # Lidarr import (lookup-first approach)
├── plex.py              # Plex playlist creation (multi-strategy fuzzy matching)
├── cli.py               # Command-line interface
├── service.py           # Service installation (Linux/Windows) - Phase 6
├── backup.py            # Database backup/restore - Phase 9
├── scheduler.py         # APScheduler wrapper - Phase 8
└── tests/               # Unit tests
    ├── test_mbid.py
    ├── test_database.py
    └── test_plex_matching.py

Architecture Principles:
-----------------------
1. MBID is primary key - Only artists with MBIDs are stored in database
2. Database is shared state - GUI reads, scheduler writes
3. Single integrated app - Flask + APScheduler in one process
4. Graceful shutdown - Finish current scrape, then stop
5. Error handling - Continue on failure, log everything

Data Flow:
---------
┌─────────────────────────────────────────────────────────────┐
│  Single Application Process                                 │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │ Flask GUI    │    │ APScheduler  │    │  Database    │ │
│  │ (Port 5000)  │◄───┤ Background   │◄───┤  (SQLite)    │ │
│  │              │    │ Scraping     │    │              │ │
│  └──────────────┘    │ Loop         │    └──────────────┘ │
│                      │ (10 min)     │                      │
│                      └──────────────┘                      │
│                                                             │
│  User accesses http://localhost:5000                       │
│  Browser → Flask API → Database                             │
└─────────────────────────────────────────────────────────────┘

Database Schema:
--------------
- stations: Station metadata and health tracking
- artists: Artist MBIDs (primary key)
- songs: Song titles with play counts
- song_plays_daily: Hourly play tracking
- schema_version: Migration tracking

Key Design Decisions:
-------------------
- No song MBIDs needed - Plex matches by artist+title, Lidarr only cares about artists
- Keep daily play detail forever (~29 MB/year growth)
- On-the-fly MBID lookups with caching
- Lookup-first Lidarr import (no scoring needed - radio artists are already radio-friendly)
- Multi-strategy Plex fuzzy matching (exact → normalized → fuzzy → partial)

Usage:
------
# CLI mode
python -m radio_monitor.cli --station us99 --loop --interval 10

# GUI mode (default)
python -m radio_monitor.cli

# Import artists to Lidarr
python -m radio_monitor.cli --import-lidarr --min-plays 5

# Create Plex playlist
python -m radio_monitor.cli --plex-playlist "Radio Hits" --days 7 --limit 50

Version: 1.1.9
"""

__version__ = "1.1.9"
__author__ = "Radio Monitor Team"
__github_url__ = "https://github.com/allurjj/radio-monitor"

def get_version():
    """Get the actual running version from VERSION.py if it exists, else use package version

    This ensures that built executables show their actual build version,
    not the latest version in the source code.

    Returns:
        str: The version number
    """
    try:
        # Try to import VERSION.py (created during build)
        import VERSION
        return VERSION.__version__
    except ImportError:
        # Fallback to package version (development mode)
        return __version__

def get_github_url():
    """Get the GitHub URL from VERSION.py if it exists, else use package default

    Returns:
        str: The GitHub URL
    """
    try:
        import VERSION
        return VERSION.__github_url__
    except ImportError:
        return __github_url__

# Import key classes for convenient access
from .database import RadioDatabase
from . import auth

__all__ = [
    "RadioDatabase",
    "auth",
    "__version__",
]
