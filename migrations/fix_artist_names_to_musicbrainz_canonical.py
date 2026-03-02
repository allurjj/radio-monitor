#!/usr/bin/env python3
"""
Migration Script: Fix Artist Names to MusicBrainz Canonical Names

=============================================================================
ISSUE: Artist Name Corruption
=============================================================================

Problem Description:
-------------------
When scraping songs, radio stations sometimes return incorrect or corrupted
artist names (e.g., "Dolly Parton Kenny Rogers" instead of "Dolly Parton",
or "Mumford" instead of "Mumford & Sons").

The scraper would:
1. Scrape artist name from station
2. Lookup MBID from MusicBrainz (fuzzy match)
3. Store the SCRAPED artist name in artists table with MusicBrainz's MBID
4. This caused corruption: artists table stored wrong names with valid MBIDs

Example Corruption:
------------------
MusicBrainz MBID: 1d543e07-d0d2-4834-a8db-d65c50c2a856
  - Canonical name: "Dolly Parton"
  - Our database:   "Dolly Parton Kenny Rogers" ❌

Why This Matters:
----------------
- artists.name is used for display (Artists page, stats, etc.)
- songs.artist_name preserves scraped data (for Plex matching)
- Everything links via MBID, not name
- Having wrong names in artists table is confusing for users

Fix Strategy:
------------
1. Query MusicBrainz for each artist MBID in our database
2. Compare MusicBrainz canonical name with our stored name
3. Update our artists table to match MusicBrainz's canonical name
4. Preserve songs.artist_name (historical scraped data)

Architecture:
------------
artists table:
  - MBID: Links to MusicBrainz (canonical source)
  - name: Should match MusicBrainz canonical name
  - Used for: Display, statistics, Lidarr import

songs table:
  - artist_name: Scraped from station (may be incorrect/incomplete)
  - artist_mbid: Links to artists table via MBID
  - Used for: Plex matching (with fuzzy variations), historical accuracy

Safety:
------
- Everything links by MBID, not name → changing names won't break relationships
- songs.artist_name preserves scraped data → Plex matching unaffected
- UNIQUE constraint on (MBID) → no duplicate artists
- Update is atomic per MBID → safe to re-run if interrupted

=============================================================================
"""

import sys
import time
import logging
import urllib.request
import json
import io
from difflib import SequenceMatcher

# Handle Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add parent directory to path
sys.path.insert(0, '.')
from radio_monitor.database import RadioDatabase

logger = logging.getLogger(__name__)

# MusicBrainz requires a User-Agent
USER_AGENT = 'RadioMonitor/1.0.0 (https://github.com/allurjj/radio-monitor)'

def get_musicbrainz_canonical_name(mbid):
    """Get canonical artist name from MusicBrainz for a given MBID

    Args:
        mbid: MusicBrainz artist ID

    Returns:
        Canonical artist name from MusicBrainz, or None if error
    """
    url = f'https://musicbrainz.org/ws/2/artist/{mbid}?fmt=json'

    try:
        headers = {'User-Agent': USER_AGENT}
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                return data.get('name')
            else:
                logger.error(f"MusicBrainz API error for {mbid}: HTTP {response.status}")
                return None

    except Exception as e:
        logger.error(f"Error fetching MusicBrainz data for {mbid}: {e}")
        return None

def calculate_similarity(str1, str2):
    """Calculate string similarity using SequenceMatcher"""
    str1_norm = str1.lower().strip()
    str2_norm = str2.lower().strip()
    return SequenceMatcher(None, str1_norm, str2_norm).ratio()

def fix_artist_names():
    """Fix artist names to match MusicBrainz canonical names"""
    db = RadioDatabase('radio_songs.db')
    db.connect()
    cursor = db.get_cursor()

    print("=" * 80)
    print("MIGRATION: Fix Artist Names to MusicBrainz Canonical Names")
    print("=" * 80)
    print()

    # Get all artists with MBIDs (exclude PENDING)
    cursor.execute("""
        SELECT mbid, name
        FROM artists
        WHERE mbid NOT LIKE 'PENDING-%'
        ORDER BY name
    """)

    artists = cursor.fetchall()
    print(f"Found {len(artists)} artists with valid MBIDs\n")

    fixed_count = 0
    already_correct = 0
    errors = 0
    skipped = 0

    for i, (mbid, current_name) in enumerate(artists, 1):
        print(f"[{i}/{len(artists)}] Checking: {current_name} ({mbid[:8]}...)")

        # Get canonical name from MusicBrainz
        canonical_name = get_musicbrainz_canonical_name(mbid)

        if not canonical_name:
            print(f"  [SKIP] Could not fetch from MusicBrainz\n")
            errors += 1
            time.sleep(1)  # Rate limiting
            continue

        # Compare names
        similarity = calculate_similarity(current_name, canonical_name)

        if current_name.lower() == canonical_name.lower():
            # Already correct
            print(f"  [OK] Already correct: {canonical_name}")
            already_correct += 1
        elif similarity >= 0.95:
            # Very similar, minor difference (punctuation, etc.)
            print(f"  [OK] Close enough ({similarity:.1%}): {current_name} -> {canonical_name}")
            already_correct += 1
        else:
            # Different - needs fixing
            print(f"  [UPDATE] \"{current_name}\" -> \"{canonical_name}\" ({similarity:.1%} match)")

            # Check how many songs would be affected
            cursor.execute("SELECT COUNT(*) FROM songs WHERE artist_mbid = ?", (mbid,))
            song_count = cursor.fetchone()[0]

            print(f"  [INFO] Affects {song_count} songs")

            # Update the artist name
            cursor.execute("""
                UPDATE artists
                SET name = ?
                WHERE mbid = ?
            """, (canonical_name, mbid))

            db.conn.commit()
            fixed_count += 1
            print(f"  [DONE] Updated")

        # Rate limiting (MusicBrainz allows 1 req/sec)
        if i < len(artists):
            time.sleep(1)

        print()

    cursor.close()
    db.close()

    print("=" * 80)
    print("MIGRATION COMPLETE")
    print("=" * 80)
    print(f"Total artists processed: {len(artists)}")
    print(f"Fixed: {fixed_count}")
    print(f"Already correct: {already_correct}")
    print(f"Errors (skipped): {errors}")
    print()
    print("[SUCCESS] Migration completed successfully!")

if __name__ == '__main__':
    try:
        fix_artist_names()
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Migration interrupted by user")
        print("Changes already committed are safe. Re-run to continue.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Migration failed: {e}")
        sys.exit(1)
