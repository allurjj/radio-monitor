"""Delete corrupted Shaboozey entries"""
import sqlite3

conn = sqlite3.connect('radio_songs.db')
cursor = conn.cursor()

# Delete the corrupted songs with NULL MBID and full collaboration name
cursor.execute('''
    DELETE FROM songs
    WHERE artist_name = 'Shaboozey (feat. Jelly Roll)'
    AND artist_mbid IS NULL
''')
deleted = cursor.rowcount
conn.commit()

print(f'Deleted {deleted} corrupted songs')

# Verify
cursor.execute('''
    SELECT COUNT(*)
    FROM songs
    WHERE artist_name = 'Shaboozey (feat. Jelly Roll)'
''')
remaining = cursor.fetchone()[0]
print(f'Remaining: {remaining}')

conn.close()
