"""Check validation issues"""
import sqlite3

conn = sqlite3.connect('radio_songs.db')
cursor = conn.cursor()

# Check invalid song
cursor.execute('''
    SELECT id, song_title, artist_name, artist_mbid, validation_status
    FROM songs
    WHERE validation_status = 'invalid'
''')
print('Invalid song:')
for row in cursor.fetchall():
    song_id, title, artist, mbid, status = row
    print(f'  ID {song_id}: {title[:35]:35} | {artist[:25]:25} | {mbid[:30] if mbid else "NULL":30}')

# Check NULL MBID songs
cursor.execute('''
    SELECT id, song_title, artist_name, artist_mbid
    FROM songs
    WHERE artist_mbid IS NULL
    LIMIT 10
''')
print('\nSongs with NULL MBID:')
for row in cursor.fetchall():
    song_id, title, artist, mbid = row
    print(f'  ID {song_id}: {title[:35]:35} | {artist[:25]:25}')

# Check unvalidated songs
cursor.execute('''
    SELECT id, song_title, artist_name, validation_status
    FROM songs
    WHERE validation_status = 'unvalidated'
    LIMIT 10
''')
print('\nUnvalidated songs:')
for row in cursor.fetchall():
    song_id, title, artist, status = row
    print(f'  ID {song_id}: {title[:35]:35} | {artist[:25]:25}')

# Check for the truncated artist name
cursor.execute('''
    SELECT id, song_title, artist_name, artist_mbid
    FROM songs
    WHERE artist_name LIKE '%(feat.%'
    LIMIT 10
''')
print('\nSongs with (feat. in artist name:')
for row in cursor.fetchall():
    song_id, title, artist, mbid = row
    print(f'  ID {song_id}: {title[:35]:35} | {artist[:40]:40} | {mbid[:30] if mbid else "NULL":30}')

conn.close()
