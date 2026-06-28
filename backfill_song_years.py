#!/usr/bin/env python3
"""
Backfill Song Years - Standalone Script

Description:
    This script backfills release years for existing VALIDATED songs in the database
    that don't have a year set. It queries MusicBrainz for each song's
    recording information and extracts the first-release-date.

    ONLY modifies the year column - nothing else in the database is changed.

Usage:
    python backfill_song_years.py

Features:
    - Only processes VALIDATED songs (validation_status = 'valid')
    - Only processes songs without a year (year IS NULL)
    - Resumable - can be stopped and restarted
    - Respects MusicBrainz rate limits (1 request/second)
    - Progress tracking with statistics
    - ONLY updates year column - no other database changes

Requirements:
    - Radio Monitor database (radio_songs.db)
    - Internet connection for MusicBrainz API
    - requests library

Rate Limiting:
    - MusicBrainz allows 1 request per second
    - Script waits 1.5 seconds between requests to be safe

Author: Radio Monitor
Version: 1.0.0
"""

import sqlite3
import time
import requests
import sys
import json
from datetime import datetime
from pathlib import Path
from collections import Counter

# Configuration
DB_PATH = Path(__file__).parent / "radio_songs.db"
SETTINGS_PATH = Path(__file__).parent / "radio_monitor_settings.json"
MUSICBRAINZ_API_BASE = "https://musicbrainz.org/ws/2"
RATE_LIMIT_SECONDS = 1.5  # Wait time between requests (1.5s to be safe)


def load_settings():
    """Load settings from radio_monitor_settings.json

    Returns:
        Settings dict or None if file doesn't exist
    """
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load settings: {e}")
    return {}


def get_user_agent():
    """Get User-Agent from settings or use default

    MusicBrainz requires User-Agent to include contact information.
    Uses the same logic as the main program.
    """
    settings = load_settings()
    user_agent = settings.get('musicbrainz', {}).get('user_agent')
    return user_agent or 'RadioMonitor/1.0.0 (https://github.com/allurjj/radio-monitor)'

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header():
    """Print script header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}  Song Year Backfill Script{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")
    print(f"{Colors.YELLOW}Database:{Colors.RESET} {DB_PATH}")
    print(f"{Colors.YELLOW}Rate Limit:{Colors.RESET} {RATE_LIMIT_SECONDS}s per request")
    print(f"{Colors.YELLOW}Target:{Colors.RESET} VALIDATED songs (validation_status='valid') without years")
    print(f"{Colors.YELLOW}Only modifies:{Colors.RESET} year column (nothing else)")

    # Show User-Agent being used
    user_agent = get_user_agent()
    print(f"{Colors.YELLOW}User-Agent:{Colors.RESET} {user_agent}")

    # Warn if using default
    if user_agent.startswith('RadioMonitor/1.0.0'):
        print(f"  {Colors.YELLOW}(Using default - configure in radio_monitor_settings.json){Colors.RESET}")
    print()


def get_songs_without_year(cursor):
    """Get VERIFIED songs that don't have a year set

    Only gets validated songs with real MBIDs that are missing a year.
    A validated song has validation_status = 'valid'.

    Returns:
        List of tuples: (song_id, artist_mbid, artist_name, song_title)
    """
    cursor.execute("""
        SELECT
            id,
            artist_mbid,
            artist_name,
            song_title
        FROM songs
        WHERE year IS NULL
            AND artist_mbid IS NOT NULL
            AND artist_mbid NOT LIKE 'PENDING-%'
            AND validation_status = 'valid'
        ORDER BY id ASC
    """)

    return cursor.fetchall()


def get_song_year_from_musicbrainz(artist_mbid, song_title):
    """Query MusicBrainz for song's first-release-date

    Gets multiple recordings and uses CLUSTER_MODE algorithm:
    - Find the oldest year
    - Look at all years within 5 years of the oldest
    - Pick the most common year in that cluster

    This eliminates single-occurrence bad data while still preferring
    original releases.

    Args:
        artist_mbid: Artist's MusicBrainz ID
        song_title: Song title

    Returns:
        Year as integer (cluster mode result), or None if not found
    """
    try:
        # Clean song title for query (remove suffixes like "Remix", "Live", etc.)
        # This matches what the main program does
        cleaned_title = song_title.split(' - ')[0].split(' (')[0].strip()
        # Remove common suffixes
        for suffix in [' - Remastered', ' - Remaster', ' (Remaster)', ' - Remix', ' (Remix)', ' - Live', ' (Live)']:
            if suffix in cleaned_title:
                cleaned_title = cleaned_title.replace(suffix, '')

        # Build query using artist MBID (more precise than artist name)
        # Use higher limit to get more recordings, then find the oldest
        # Some artists have huge catalogs (AC/DC, Aerosmith, etc.)
        params = {
            'query': f'arid:{artist_mbid} AND recording:"{cleaned_title}"',
            'limit': 100,
            'fmt': 'json'
        }

        headers = {
            'User-Agent': get_user_agent()
        }

        response = requests.get(
            f"{MUSICBRAINZ_API_BASE}/recording",
            params=params,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            recordings = data.get('recordings', [])

            if recordings and len(recordings) > 0:
                # CLUSTER_MODE: Find the most common year within 5 years of the oldest
                # This eliminates single-occurrence bad data while still preferring original releases

                # Collect all valid years
                years = []
                for recording in recordings:
                    first_release_date = recording.get('first-release-date')
                    if first_release_date:
                        # Extract year from date (formats: "2012", "2012-05-15", "2012-05")
                        year_str = first_release_date.split('-')[0]
                        if year_str.isdigit() and len(year_str) == 4:
                            year = int(year_str)
                            # Sanity check: year should be reasonable
                            if 1900 <= year <= datetime.now().year + 1:
                                years.append(year)

                if years:
                    # Find the oldest year
                    min_year = min(years)

                    # Get all years within 5 years of the oldest
                    cluster_years = [y for y in years if y <= min_year + 5]

                    # Find the most common year in the cluster
                    if cluster_years:
                        year_counts = Counter(cluster_years)
                        cluster_mode_year = year_counts.most_common(1)[0][0]
                        return cluster_mode_year
                    else:
                        # Fallback: use oldest year
                        return min_year

                return None

        return None

    except requests.exceptions.Timeout:
        print(f"  {Colors.YELLOW}Timeout{Colors.RESET}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  {Colors.RED}Request error: {e}{Colors.RESET}")
        return None
    except Exception as e:
        print(f"  {Colors.RED}Error: {e}{Colors.RESET}")
        return None


def update_song_year(cursor, conn, song_id, year):
    """Update song's year in database

    Args:
        cursor: Database cursor
        conn: Database connection
        song_id: Song ID
        year: Year to set

    Returns:
        True if successful, False otherwise
    """
    try:
        cursor.execute("""
            UPDATE songs
            SET year = ?
            WHERE id = ?
        """, (year, song_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"  {Colors.RED}Failed to update: {e}{Colors.RESET}")
        return False


def print_progress(current, total, success_count, error_count, skip_count):
    """Print progress statistics

    Args:
        current: Current song number being processed
        total: Total songs to process
        success_count: Number of successful updates
        error_count: Number of errors
        skip_count: Number of songs skipped (not found)
    """
    percentage = (current / total * 100) if total > 0 else 0
    print(f"\n{Colors.BOLD}Progress:{Colors.RESET} {current}/{total} ({percentage:.1f}%)")
    print(f"  {Colors.GREEN}✓ Updated:{Colors.RESET} {success_count}")
    print(f"  {Colors.YELLOW}⊘ Not Found:{Colors.RESET} {skip_count}")
    print(f"  {Colors.RED}✗ Errors:{Colors.RESET} {error_count}")


def main():
    """Main execution function"""
    print_header()

    # Check if database exists
    if not DB_PATH.exists():
        print(f"{Colors.RED}Error: Database not found at {DB_PATH}{Colors.RESET}")
        print("Make sure you're running this script from the Radio Monitor directory.")
        sys.exit(1)

    # Connect to database
    print(f"{Colors.BLUE}Connecting to database...{Colors.RESET}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Get songs without year
        songs = get_songs_without_year(cursor)
        total_songs = len(songs)

        if total_songs == 0:
            print(f"{Colors.GREEN}No songs need year updates!{Colors.RESET}")
            print("All verified songs already have years set.")
            sys.exit(0)

        print(f"{Colors.GREEN}Found {total_songs} songs to process{Colors.RESET}\n")

        # Confirm before proceeding
        print(f"{Colors.YELLOW}This will make {total_songs} requests to MusicBrainz.{Colors.RESET}")
        print(f"{Colors.YELLOW}Estimated time: {total_songs * RATE_LIMIT_SECONDS / 60:.1f} minutes{Colors.RESET}")
        response = input("\nProceed? (y/N): ").strip().lower()

        if response != 'y':
            print("Aborted.")
            sys.exit(0)

        print()
        success_count = 0
        error_count = 0
        skip_count = 0

        # Process each song
        for i, (song_id, artist_mbid, artist_name, song_title) in enumerate(songs, 1):
            print(f"[{i}/{total_songs}] {Colors.BLUE}{artist_name}{Colors.RESET} - {Colors.BLUE}{song_title}{Colors.RESET}", end=' ')

            # Query MusicBrainz
            year = get_song_year_from_musicbrainz(artist_mbid, song_title)

            if year:
                print(f"→ {Colors.GREEN}{year}{Colors.RESET}", end=' ')
                if update_song_year(cursor, conn, song_id, year):
                    print(f"{Colors.GREEN}✓{Colors.RESET}")
                    success_count += 1
                else:
                    error_count += 1
            else:
                skip_count += 1

            # Print progress every 10 songs
            if i % 10 == 0 or i == total_songs:
                print_progress(i, total_songs, success_count, error_count, skip_count)

            # Rate limiting
            if i < total_songs:
                time.sleep(RATE_LIMIT_SECONDS)

        # Final summary
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}  Complete!{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")
        print(f"{Colors.GREEN}Successfully updated:{Colors.RESET} {success_count} songs")
        print(f"{Colors.YELLOW}Not found on MusicBrainz:{Colors.RESET} {skip_count} songs")
        print(f"{Colors.RED}Errors:{Colors.RESET} {error_count} songs")
        print(f"\n{Colors.BLUE}Remaining songs without years:{Colors.RESET} {total_songs - success_count}")
        print(f"\n{Colors.YELLOW}Tip: Run this script again to retry skipped songs.{Colors.RESET}")

    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Interrupted by user{Colors.RESET}")
        print(f"{Colors.GREEN}Progress saved. Run again to continue.{Colors.RESET}")
        sys.exit(0)

    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {e}{Colors.RESET}")
        sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
