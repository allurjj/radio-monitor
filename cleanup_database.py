"""Database cleanup script - Run with --dry-run first to preview changes"""
import sys
sys.path.insert(0, r'C:\Users\allurjj\Documents\Radio_Monitor')
import sqlite3
import argparse

DB_PATH = 'radio_songs.db'

def cleanup_database(dry_run=True):
    """Clean up various database issues"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    total_deleted = 0

    print("=" * 80)
    if dry_run:
        print("DRY RUN - No changes will be made")
    else:
        print("LIVE RUN - Changes will be committed")
    print("=" * 80)

    # 1. Delete PENDING artists
    print("\n1. PENDING Artists")
    print("-" * 40)
    cursor.execute('''
        SELECT mbid, name, COUNT(DISTINCT s.id) as song_count
        FROM artists a
        LEFT JOIN songs s ON a.mbid = s.artist_mbid
        WHERE a.mbid LIKE 'PENDING%'
        GROUP BY a.mbid
    ''')
    pending = cursor.fetchall()
    if pending:
        for mbid, name, count in pending:
            print(f"  {mbid[:50]} | {name[:40]} | {count} songs")
            if not dry_run:
                # Delete songs first (CASCADE should handle, but be explicit)
                cursor.execute('DELETE FROM songs WHERE artist_mbid = ?', (mbid,))
                # Then delete artist
                cursor.execute('DELETE FROM artists WHERE mbid = ?', (mbid,))
        total_deleted += len(pending)
        print(f"  -> Would delete {len(pending)} PENDING artists and their songs")
    else:
        print("  No PENDING artists found")

    # 2. Delete "Various Artists"
    print("\n2. Various Artists")
    print("-" * 40)
    cursor.execute('''
        SELECT mbid, name, COUNT(DISTINCT s.id) as song_count
        FROM artists a
        LEFT JOIN songs s ON a.mbid = s.artist_mbid
        WHERE LOWER(a.name) = 'various artists'
        GROUP BY a.mbid
    ''')
    various = cursor.fetchall()
    if various:
        for mbid, name, count in various:
            print(f"  {mbid[:50]} | {name[:40]} | {count} songs")
            if not dry_run:
                cursor.execute('DELETE FROM songs WHERE artist_mbid = ?', (mbid,))
                cursor.execute('DELETE FROM artists WHERE mbid = ?', (mbid,))
        total_deleted += len(various)
        print(f"  -> Would delete {len(various)} 'Various Artists' entries")
    else:
        print("  No 'Various Artists' found")

    # 3. Delete suspicious short names (likely corruption)
    print("\n3. Suspicious Short Names (< 3 chars)")
    print("-" * 40)
    cursor.execute('''
        SELECT mbid, name, COUNT(DISTINCT s.id) as song_count
        FROM artists a
        LEFT JOIN songs s ON a.mbid = s.artist_mbid
        WHERE LENGTH(a.name) < 3
          AND a.name NOT IN ('P!NK', 'U2', 'ABBA', 'A-HA', 'KISS', 'R.E.M', 'Jay-Z', 'Z')
          AND a.mbid NOT LIKE 'PENDING%'
        GROUP BY a.mbid
    ''')
    short_names = cursor.fetchall()
    if short_names:
        for mbid, name, count in short_names:
            print(f"  {mbid[:50]} | {name[:40]} | {count} songs")
            if not dry_run:
                cursor.execute('DELETE FROM songs WHERE artist_mbid = ?', (mbid,))
                cursor.execute('DELETE FROM artists WHERE mbid = ?', (mbid,))
        total_deleted += len(short_names)
        print(f"  -> Would delete {len(short_names)} suspicious short-name artists")
    else:
        print("  No suspicious short names found")

    # 4. Check for empty/null names
    print("\n4. Empty/Null Names")
    print("-" * 40)
    cursor.execute('''
        SELECT mbid, name, COUNT(DISTINCT s.id) as song_count
        FROM artists a
        LEFT JOIN songs s ON a.mbid = s.artist_mbid
        WHERE a.name IS NULL OR a.name = ''
        GROUP BY a.mbid
    ''')
    empty_names = cursor.fetchall()
    if empty_names:
        for mbid, name, count in empty_names:
            print(f"  {mbid[:50]} | {name if name else '(null)'} | {count} songs")
            if not dry_run:
                cursor.execute('DELETE FROM songs WHERE artist_mbid = ?', (mbid,))
                cursor.execute('DELETE FROM artists WHERE mbid = ?', (mbid,))
        total_deleted += len(empty_names)
        print(f"  -> Would delete {len(empty_names)} empty-name artists")
    else:
        print("  No empty/null names found")

    # Summary
    print("\n" + "=" * 80)
    print(f"SUMMARY: Would delete {total_deleted} artists and their associated songs")
    print("=" * 80)

    if not dry_run:
        conn.commit()
        print("Changes committed to database")
    else:
        print("DRY RUN complete - no changes made")
        print("\nTo apply changes, run: python cleanup_database.py --live")

    conn.close()
    return total_deleted

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Clean up database issues')
    parser.add_argument('--live', action='store_true', help='Actually make changes (default is dry-run)')
    args = parser.parse_args()

    cleanup_database(dry_run=not args.live)
