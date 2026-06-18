"""Analyze database after scrape"""
import sqlite3

conn = sqlite3.connect('radio_songs.db')
cursor = conn.cursor()

# Check database stats
cursor.execute('SELECT COUNT(*) FROM artists')
print(f'Artists: {cursor.fetchone()[0]}')

cursor.execute('SELECT COUNT(*) FROM songs')
print(f'Songs: {cursor.fetchone()[0]}')

# Check recent songs
cursor.execute('''
    SELECT s.song_title, s.artist_name, s.play_count
    FROM songs s
    ORDER BY s.id DESC
    LIMIT 15
''')
print('\nRecent songs:')
for row in cursor.fetchall():
    print(f'  {row[0][:35]:35} | {row[1][:25]:25} | plays: {row[2]}')

# Check for any PENDING MBIDs
cursor.execute('SELECT COUNT(*) FROM artists WHERE mbid LIKE "PENDING%"')
pending_count = cursor.fetchone()[0]
print(f'\nPending MBIDs: {pending_count}')

# Show some PENDING artists
cursor.execute('''
    SELECT mbid, name
    FROM artists
    WHERE mbid LIKE "PENDING%"
    LIMIT 10
''')
print('\nSample PENDING artists:')
for row in cursor.fetchall():
    print(f'  {row[1][:40]:40} | {row[0][:30]}')

# Check for multi-artist collaborations (spaces without separators)
cursor.execute('''
    SELECT name, mbid
    FROM artists
    WHERE name LIKE "% %"
    AND name NOT GLOB "*[;&+]*"
    AND name NOT LIKE "% feat%"
    AND name NOT LIKE "% ft.%"
    AND name NOT LIKE "% featuring%"
    AND mbid LIKE "PENDING%"
    LIMIT 15
''')
print('\nMulti-artist PENDING (no separators):')
for row in cursor.fetchall():
    print(f'  {row[0][:50]:50}')

conn.close()
