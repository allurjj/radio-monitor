#!/usr/bin/env python3
"""
Retry only the artists that were skipped during the initial migration due to MusicBrainz API errors.
This avoids re-querying all 1335 artists and only makes ~104 API calls.
"""

import sys
import time
import re
from difflib import SequenceMatcher
from radio_monitor.database import RadioDatabase

# Windows console encoding fix
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def get_skipped_artists(log_file='migration_rerun.txt'):
    """Extract artist names that were skipped due to API errors"""
    skipped_artists = []

    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        # Look for skipped entries
        if '[SKIP] Could not fetch from MusicBrainz' in line:
            # Get the previous line which should have the artist info
            if i > 0:
                prev_line = lines[i - 1]
                # Extract artist name using regex
                match = re.search(r'Checking: (.+) \([a-f0-9-]+\.\.\.', prev_line)
                if match:
                    artist_name = match.group(1)
                    skipped_artists.append(artist_name)

    return skipped_artists

def calculate_similarity(str1, str2):
    """Calculate string similarity ratio"""
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

def get_musicbrainz_canonical_name(mbid):
    """Fetch canonical name from MusicBrainz API"""
    import musicbrainzngs

    musicbrainzngs.set_useragent("RadioMonitor", "2.0")

    try:
        result = musicbrainzngs.get_artist_by_id(mbid, includes=["aliases"])
        canonical_name = result['artist']['name']
        return canonical_name
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None

def fix_skipped_artists():
    """Fix only the skipped artists"""
    db = RadioDatabase('radio_songs.db')
    db.connect()
    cursor = db.get_cursor()

    # Extract skipped artist names from migration log
    print("Extracting skipped artists from migration log...")
    skipped_artists = get_skipped_artists()

    print(f"\nFound {len(skipped_artists)} skipped artists to retry\n")
    print("=" * 80)
    print("RETRY MIGRATION: Skipped Artists Only")
    print("=" * 80)

    updated_count = 0
    skipped_count = 0
    not_found_count = 0

    for i, artist_name in enumerate(skipped_artists, 1):
        # Get MBID and current name from database using artist name
        cursor.execute("SELECT mbid, name FROM artists WHERE name = ?", (artist_name,))
        row = cursor.fetchone()
        if not row:
            print(f"[{i}/{len(skipped_artists)}] [ERROR] Artist '{artist_name}' not found in database")
            not_found_count += 1
            continue

        mbid, current_name = row

        print(f"[{i}/{len(skipped_artists)}] Checking: {artist_name} ({mbid[:8]}...)")

        # Fetch from MusicBrainz
        canonical_name = get_musicbrainz_canonical_name(mbid)

        if not canonical_name:
            print(f"  [SKIP] Could not fetch from MusicBrainz (again)")
            skipped_count += 1
            continue

        # Calculate similarity
        similarity = calculate_similarity(current_name, canonical_name)

        # Check if update needed
        if current_name.lower() == canonical_name.lower():
            print(f"  [OK] Already correct: {current_name}")
        elif similarity >= 0.95:
            print(f"  [OK] Close enough ({similarity:.1%}): {current_name} -> {canonical_name}")
        else:
            # Need to update
            print(f"  [UPDATE] \"{current_name}\" -> \"{canonical_name}\" ({similarity:.1%} match)")

            # Check how many songs affected
            cursor.execute("SELECT COUNT(*) FROM songs WHERE artist_mbid = ?", (mbid,))
            song_count = cursor.fetchone()[0]
            if song_count > 0:
                print(f"  [INFO] Affects {song_count} songs")

            # Update database
            cursor.execute("""
                UPDATE artists
                SET name = ?
                WHERE mbid = ?
            """, (canonical_name, mbid))
            db.conn.commit()
            print(f"  [DONE] Updated")
            updated_count += 1

        # Rate limiting (1 second between requests)
        if i < len(skipped_artists):
            time.sleep(1)

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total skipped artists: {len(skipped_artists)}")
    print(f"Successfully updated: {updated_count}")
    print(f"Still failed: {skipped_count}")
    print(f"Not found in database: {not_found_count}")
    print(f"Already correct: {len(skipped_artists) - updated_count - skipped_count - not_found_count}")
    print("=" * 80)

    cursor.close()
    db.close()

if __name__ == '__main__':
    fix_skipped_artists()
