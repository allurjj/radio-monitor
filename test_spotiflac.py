#!/usr/bin/env python
"""
Test SpotiFLAC integration with real Plex failure data from the database.

This script:
1. Gets sample Plex failures from the database
2. Tests Spotify search functionality
3. Tests download functionality (optional)
"""

import os
import sys
import sqlite3
import json
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from radio_monitor.gui import load_settings
from radio_monitor.integrations.spotiflac_service import SpotiFLACService


def get_sample_plex_failure(db_path, limit=5):
    """Get sample unresolved Plex failures from the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                f.id as failure_id,
                s.id as song_id,
                s.artist_name,
                s.song_title,
                s.year,
                f.failure_reason
            FROM plex_match_failures f
            LEFT JOIN songs s ON f.song_id = s.id
            WHERE f.resolved = 0
            ORDER BY f.failure_date DESC
            LIMIT ?
        """, (limit,))

        failures = []
        for row in cursor.fetchall():
            failures.append({
                'failure_id': row[0],
                'song_id': row[1],
                'artist_name': row[2],
                'song_title': row[3],
                'year': row[4],
                'failure_reason': row[5]
            })

        conn.close()
        return failures

    except Exception as e:
        print(f"ERROR: Failed to get Plex failures: {e}")
        return []


def test_spotify_search(service, failures):
    """Test Spotify search functionality."""
    print("\n" + "="*60)
    print("TESTING SPOTIFY SEARCH")
    print("="*60)

    for i, failure in enumerate(failures, 1):
        print(f"\n[{i}/{len(failures)}] Testing: {failure['artist_name']} - {failure['song_title']}")

        try:
            results = service.search_spotify(
                song_title=failure['song_title'],
                artist_name=failure['artist_name']
            )

            if results:
                print(f"  Found {len(results)} tracks on Spotify:")
                for j, track in enumerate(results[:3], 1):  # Show first 3 results
                    print(f"    {j}. {track['title']} - {track['artist']}")
                    print(f"       Album: {track['album']} ({track['year']})")
                    print(f"       URL: {track['url']}")
                    if j < 3 and len(results) > 3:
                        print(f"       ... and {len(results) - 3} more")

                # Store first result for potential download test
                failure['spotify_url'] = results[0]['url']
                failure['spotify_title'] = results[0]['title']
            else:
                print(f"  No results found on Spotify")
                failure['spotify_url'] = None

        except Exception as e:
            print(f"  ERROR: {e}")


def test_download(service, failure):
    """Test download functionality (optional - requires user confirmation)."""
    print("\n" + "="*60)
    print("OPTIONAL DOWNLOAD TEST")
    print("="*60)

    if not failure.get('spotify_url'):
        print("No Spotify URL available for download test")
        return

    print(f"\nWould you like to test downloading this track?")
    print(f"  Artist: {failure['artist_name']}")
    print(f"  Song: {failure['song_title']}")
    print(f"  Spotify Match: {failure.get('spotify_title', 'N/A')}")
    print(f"\nThis will download to the temp_downloads folder.")
    print(f"Using YouTube service (most reliable).")

    response = input("\nProceed with download? (y/n): ").strip().lower()

    if response != 'y':
        print("Download test skipped")
        return

    try:
        print(f"\nStarting download...")
        result = service.download_track(
            spotify_url=failure['spotify_url'],
            song_title=failure['song_title'],
            artist_name=failure['artist_name'],
            services=['youtube']  # Use YouTube as most reliable
        )

        print(f"\nDownload Result:")
        print(f"  Success: {result.get('success')}")
        print(f"  Job ID: {result.get('job_id')}")

        if result.get('success'):
            print(f"  File Path: {result.get('file_path')}")
            print(f"  Service Used: {result.get('service_used')}")
            print(f"  File Size: {result.get('file_size_mb', 0):.2f} MB")

            # Check if file exists
            if result.get('file_path') and os.path.exists(result['file_path']):
                size_mb = os.path.getsize(result['file_path']) / (1024 * 1024)
                print(f"  File exists on disk: {size_mb:.2f} MB")
            else:
                print(f"  WARNING: File not found on disk")
        else:
            print(f"  Error: {result.get('error')}")

    except Exception as e:
        print(f"ERROR during download: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("="*60)
    print("SPOTIFLAC INTEGRATION TEST")
    print("="*60)

    # Load settings
    settings = load_settings() or {}
    print(f"\nSettings loaded:")
    print(f"  Lidarr configured: {'Yes' if settings.get('lidarr', {}).get('url') else 'No'}")
    print(f"  Plex configured: {'Yes' if settings.get('plex', {}).get('url') else 'No'}")

    # Initialize service
    service = SpotiFLACService(settings)
    print(f"\nSpotiFLACService initialized:")
    print(f"  Temp download dir: {service.temp_download_dir}")
    print(f"  Auto-move enabled: {service.auto_move}")
    print(f"  Preferred quality: {service.preferred_quality}")

    # Get sample Plex failures
    db_path = os.path.join(os.path.dirname(__file__), 'radio_songs.db')
    print(f"\nLoading Plex failures from: {db_path}")

    failures = get_sample_plex_failure(db_path, limit=5)

    if not failures:
        print("\nNo unresolved Plex failures found in database")
        return

    print(f"\nFound {len(failures)} unresolved Plex failures:")
    for i, failure in enumerate(failures, 1):
        print(f"  {i}. {failure['artist_name']} - {failure['song_title']} ({failure['year']})")

    # Test Spotify search
    test_spotify_search(service, failures)

    # Optional download test (use first failure with Spotify URL)
    for failure in failures:
        if failure.get('spotify_url'):
            test_download(service, failure)
            break  # Only test one download

    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)


if __name__ == '__main__':
    main()
