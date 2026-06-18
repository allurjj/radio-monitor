"""
Baseline Performance Test

Measure current scrape performance before implementation.
Run this to establish baseline metrics.
"""
import time
import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radio_monitor.scrapers import scrape_all_stations
from radio_monitor.database import RadioDatabase

# Configure logging
logging.basicConfig(level=logging.INFO)


def test_baseline():
    """Test current scrape performance"""
    print("=" * 60)
    print("Baseline Performance Test")
    print("=" * 60)
    print("Starting scrape...")

    # Initialize database
    db_path = os.path.join(os.path.dirname(__file__), "radio_songs.db")
    db = RadioDatabase(db_path)
    db.connect()

    start = time.time()
    results = scrape_all_stations(db)
    end = time.time()

    duration = end - start

    # Parse results dict
    success = results.get('success', False)
    stations_scraped = results.get('stations_scraped', 0)
    songs_found = results.get('songs_found', 0)
    artists_added = results.get('artists_added', 0)
    songs_added = results.get('songs_added', 0)
    plays_recorded = results.get('plays_recorded', 0)
    skipped_no_mbid = results.get('skipped_no_mbid', 0)
    failed_stations = results.get('failed_stations', [])
    message = results.get('message', '')

    rate = songs_found / duration if duration > 0 else 0

    print(f"\nBaseline Performance:")
    print(f"  Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
    print(f"  Success: {success}")
    print(f"  Stations scraped: {stations_scraped}")
    print(f"  Songs found: {songs_found}")
    print(f"  Artists added: {artists_added}")
    print(f"  Songs added: {songs_added}")
    print(f"  Plays recorded: {plays_recorded}")
    print(f"  Skipped (no MBID): {skipped_no_mbid}")
    print(f"  Rate: {rate:.2f} songs/second")

    if failed_stations:
        print(f"  Failed stations: {', '.join(failed_stations)}")

    print(f"\n  Message: {message}")
    print("=" * 60)

    return {
        'duration': duration,
        'success': success,
        'stations_scraped': stations_scraped,
        'songs_found': songs_found,
        'artists_added': artists_added,
        'songs_added': songs_added,
        'plays_recorded': plays_recorded,
        'skipped_no_mbid': skipped_no_mbid,
        'failed_stations': failed_stations,
        'rate': rate
    }


if __name__ == '__main__':
    test_baseline()
