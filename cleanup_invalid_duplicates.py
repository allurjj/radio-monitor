"""Remove invalid duplicate songs - LIVE RUN"""
import sys
sys.path.insert(0, r'C:\Users\allurjj\Documents\Radio_Monitor')
import sqlite3

DB_PATH = 'radio_songs.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print('=== LIVE CLEANUP: Remove invalid duplicate songs ===')
print()

total_deleted = 0

# 1. Delete exact duplicates (keep highest ID)
print('1. Deleting exact duplicates (keeping newest)...')
cursor.execute('''
    DELETE FROM songs
    WHERE id IN (
        SELECT s1.id
        FROM songs s1
        WHERE EXISTS (
            SELECT 1 FROM songs s2
            WHERE s2.song_title = s1.song_title
            AND s2.artist_name = s1.artist_name
            AND s2.id > s1.id
        )
    )
''')
deleted = cursor.rowcount
total_deleted += deleted
print(f'   Deleted {deleted} exact duplicates')

# 2. Delete corrupted multi-artist songs (old bug patterns)
print('\\n2. Deleting corrupted multi-artist songs...')
cursor.execute('''
    DELETE FROM songs
    WHERE validation_status = 'invalid'
    AND (
        artist_name LIKE '%Pitbull Afrojack%'
        OR artist_name LIKE '%Gotye Kimbra%'
        OR artist_name LIKE '%Chesneyuncle%'
        OR artist_name LIKE '%NeYo%'
        OR artist_name LIKE '%Jessie J Ariana%'
    )
''')
deleted = cursor.rowcount
total_deleted += deleted
print(f'   Deleted {deleted} corrupted songs')

# 3. Delete songs with no spaces in artist (old URL slug bug)
print('\\n3. Deleting songs with corrupted artist names (no spaces)...')
cursor.execute('''
    DELETE FROM songs
    WHERE validation_status = 'invalid'
    AND artist_name NOT LIKE '% %'
    AND LENGTH(artist_name) > 5
''')
deleted = cursor.rowcount
total_deleted += deleted
print(f'   Deleted {deleted} corrupted artist names')

conn.commit()

print('\\n' + '=' * 60)
print(f'Total deleted: {total_deleted} songs')
print('=' * 60)

# Verify
cursor.execute('SELECT COUNT(*) FROM songs WHERE validation_status = "invalid"')
remaining_invalid = cursor.fetchone()[0]
print(f'Remaining invalid songs: {remaining_invalid}')

cursor.execute('SELECT COUNT(*) FROM songs')
total_songs = cursor.fetchone()[0]
print(f'Total songs: {total_songs}')

conn.close()
