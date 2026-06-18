"""Delete artists with NULL MBID (corrupted data)"""
import sys
sys.path.insert(0, r'C:\Users\allurjj\Documents\Radio_Monitor')
import sqlite3

DB_PATH = 'radio_songs.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Find artists with NULL MBID
cursor.execute('''
    SELECT rowid, mbid, name,
           (SELECT COUNT(*) FROM songs WHERE artist_mbid = a.mbid) as song_count
    FROM artists a
    WHERE mbid IS NULL
''')
null_mbid_artists = cursor.fetchall()

if not null_mbid_artists:
    print('No artists with NULL MBID found')
    conn.close()
    sys.exit(0)

print(f'Found {len(null_mbid_artists)} artists with NULL MBID:')
print('-' * 60)
for row in null_mbid_artists:
    rowid, mbid, name, song_count = row
    print(f'  rowid: {rowid}, name: "{name}", songs: {song_count}')

# Delete them (they have 0 songs anyway)
print(f'\\nDeleting {len(null_mbid_artists)} artists...')
cursor.execute('DELETE FROM artists WHERE mbid IS NULL')
deleted = cursor.rowcount

conn.commit()
print(f'Deleted {deleted} artists')

# Verify
cursor.execute('SELECT COUNT(*) FROM artists WHERE mbid IS NULL')
remaining = cursor.fetchone()[0]
print(f'Remaining NULL MBID artists: {remaining}')

conn.close()
