"""Check existing Amen songs"""
import sqlite3

conn = sqlite3.connect('radio_songs.db')
cursor = conn.cursor()

# Check if 'Amen' by 'Shaboozey (feat. Jelly Roll)' already existed before today
cursor.execute('''
    SELECT id, song_title, artist_name, artist_mbid, first_seen_at
    FROM songs
    WHERE song_title = 'Amen'
    AND artist_name LIKE '%Shaboozey%'
    ORDER BY first_seen_at
''')
print('All Amen by Shaboozey songs:')
for row in cursor.fetchall():
    song_id, title, artist, mbid, first_seen = row
    mbid_str = mbid[:30] if mbid else 'NULL'
    print(f'  ID {song_id}: {title[:35]:35} | {artist[:40]:40} | MBID: {mbid_str:30} | seen: {first_seen}')

# Check if there's an existing song with just 'Shaboozey'
cursor.execute('''
    SELECT id, song_title, artist_name, artist_mbid, first_seen_at
    FROM songs
    WHERE song_title = 'Amen'
    AND artist_name = 'Shaboozey'
''')
print('\nAmen by Shaboozey (without feat):')
for row in cursor.fetchall():
    song_id, title, artist, mbid, first_seen = row
    mbid_str = mbid[:30] if mbid else 'NULL'
    print(f'  ID {song_id}: {title[:35]:35} | {artist[:40]:40} | MBID: {mbid_str:30} | seen: {first_seen}')

conn.close()
