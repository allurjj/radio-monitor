"""Delete artists with 0 songs (relics from old scraping)"""
import sys
sys.path.insert(0, r'C:\Users\allurjj\Documents\Radio_Monitor')
import sqlite3

DB_PATH = 'radio_songs.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print('=== Artists with 0 songs ===')
cursor.execute('''
    SELECT a.mbid, a.name,
           (SELECT COUNT(*) FROM songs s WHERE s.artist_mbid = a.mbid) as song_count
    FROM artists a
    WHERE mbid NOT IN (SELECT DISTINCT artist_mbid FROM songs WHERE artist_mbid IS NOT NULL)
    ORDER BY a.name
''')
results = cursor.fetchall()

print(f'Found {len(results)} artists with 0 songs')
print('\\nSample:')
for row in results[:20]:
    mbid, name, song_count = row
    print(f'  {name[:40]:40} | {mbid[:30] if mbid else "NULL":30}')

# Delete them
print(f'\\nDeleting {len(results)} artists...')
cursor.execute('''
    DELETE FROM artists
    WHERE mbid NOT IN (SELECT DISTINCT artist_mbid FROM songs WHERE artist_mbid IS NOT NULL)
''')
deleted = cursor.rowcount
conn.commit()

print(f'Deleted {deleted} artists')

# Verify
cursor.execute('SELECT COUNT(*) FROM artists')
total = cursor.fetchone()[0]
print(f'Remaining artists: {total}')

conn.close()
