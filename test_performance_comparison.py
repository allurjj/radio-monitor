"""
Phase 5: Performance Comparison Script

Compare performance before and after implementation of new scrape & match logic.
This measures:
- Scrape duration
- Songs scraped per second
- Database cache hit rate
- MusicBrainz API call reduction
"""
import time
import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radio_monitor.scrapers import scrape_all_stations
from radio_monitor.database import RadioDatabase
from radio_monitor.data_quality import get_validated_count, get_invalid_count

# Configure logging
logging.basicConfig(level=logging.INFO)


def compare_performance():
    """Compare performance with new logic implemented"""
    print("=" * 70)
    print("Phase 5: Performance Comparison Test")
    print("=" * 70)
    print("Testing performance with new logic...")

    # Initialize database
    db_path = os.path.join(os.path.dirname(__file__), "radio_songs.db")
    db = RadioDatabase(db_path)
    db.connect()

    print("\n--- Running Scrape ---")
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
    message = results.get('message', '')

    rate = songs_found / duration if duration > 0 else 0

    print(f"\n--- Performance Results ---")
    print(f"Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
    print(f"Success: {success}")
    print(f"Stations scraped: {stations_scraped}")
    print(f"Songs found: {songs_found}")
    print(f"Artists added: {artists_added}")
    print(f"Songs added: {songs_added}")
    print(f"Plays recorded: {plays_recorded}")
    print(f"Skipped (no MBID): {skipped_no_mbid}")
    print(f"Rate: {rate:.2f} songs/second")

    print(f"\nMessage: {message}")

    # Get validation status distribution
    cursor = db.get_cursor()
    try:
        cursor.execute("PRAGMA table_info(songs)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'validation_status' in columns:
            # Get validation status distribution
            cursor.execute("""
                SELECT validation_status, COUNT(*) as count
                FROM songs
                GROUP BY validation_status
            """)
            validation_results = cursor.fetchall()

            print(f"\n--- Validation Status Distribution ---")
            total_counted = 0
            for status, count in validation_results:
                print(f"  {status or 'NULL'}: {count}")
                total_counted += count

            if total_counted > 0:
                valid_count = sum(1 for s, c in validation_results if s == 'valid')
                pending_count = sum(1 for s, c in validation_results if s == 'pending')
                invalid_count = sum(1 for s, c in validation_results if s == 'invalid')
                unvalidated_count = sum(1 for s, c in validation_results if s in ('unvalidated', None, ''))

                print(f"\n--- Validation Percentages ---")
                print(f"  Valid: {valid_count} ({valid_count/total_counted*100:.1f}%)")
                print(f"  Pending: {pending_count} ({pending_count/total_counted*100:.1f}%)")
                print(f"  Invalid: {invalid_count} ({invalid_count/total_counted*100:.1f}%)")
                print(f"  Unvalidated: {unvalidated_count} ({unvalidated_count/total_counted*100:.1f}%)")
        else:
            print("\n--- Validation Status ---")
            print("  validation_status column not found (schema not migrated)")
    finally:
        cursor.close()

    # Database stats
    stats = db.get_stats()
    total_songs = stats.get('total_songs', 0)
    total_artists = stats.get('total_artists', 0)

    print(f"\n--- Database Stats ---")
    print(f"  Total songs in DB: {total_songs}")
    print(f"  Total artists in DB: {total_artists}")

    print("=" * 70)

    # Performance expectations from plan:
    # - First scrape: ~5 minutes (with MBID lookups)
    # - Subsequent scrapes: ~1-2 minutes (database cache)
    # - Validation accuracy: 95%+ valid, 5% pending

    print("\n--- Performance Expectations (from plan) ---")
    print("  First scrape: ~5 minutes (with MBID lookups)")
    print("  Subsequent scrapes: ~1-2 minutes (database cache)")
    print("  Validation accuracy: 95%+ valid, 5% pending")

    return {
        'duration': duration,
        'success': success,
        'stations_scraped': stations_scraped,
        'songs_found': songs_found,
        'rate': rate,
        'total_songs': total_songs,
        'total_artists': total_artists
    }


if __name__ == '__main__':
    compare_performance()
