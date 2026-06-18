"""Delete invalid songs that have valid versions with same title (artist name format differs)"""
import sys
sys.path.insert(0, r'C:\Users\allurjj\Documents\Radio_Monitor')
import sqlite3

DB_PATH = 'radio_songs.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print('=== Finding invalid songs with valid versions (same title) ===')

# Find songs where:
# - Same song_title
# - One is invalid, one is valid
# - Keep the valid one, delete the invalid
cursor.execute('''
    SELECT s1.id, s1.song_title, s1.artist_name, s1.play_count,
           s2.id as valid_id, s2.artist_name as valid_artist, s2.play_count as valid_plays
    FROM songs s1
    JOIN songs s2 ON s1.song_title = s2.song_title
    WHERE s1.validation_status = 'invalid'
    AND s2.validation_status = 'valid'
    AND s1.id < s2.id
''')
duplicates = cursor.fetchall()

print(f'Found {len(duplicates)} invalid songs with valid versions')
print()

if duplicates:
    print('Sample (first 15):')
    for row in duplicates[:15]:
        inv_id, title, inv_artist, inv_plays, valid_id, valid_artist, valid_plays = row
        print(f'  ID {inv_id} -> {valid_id}: {title[:30]} | {inv_artist[:20]} -> {valid_artist[:20]}')

    # Delete invalid versions
    print(f'\\nDeleting {len(duplicates)} invalid songs...')

    # Get list of IDs to delete
    invalid_ids = [str(row[0]) for row in duplicates]

    # Delete in batches
    batch_size = 100
    for i in range(0, len(invalid_ids), batch_size):
        batch = invalid_ids[i:i+batch_size]
        placeholders = ','.join(['?'] * len(batch))
        cursor.execute(f'DELETE FROM songs WHERE id IN ({placeholders})', batch)
        print(f'  Deleted batch {i//batch_size + 1}: {cursor.rowcount} songs')

    conn.commit()
    print(f'Total deleted: {len(invalid_ids)} songs')

# Verify
cursor.execute('SELECT COUNT(*) FROM songs WHERE validation_status = "invalid"')
remaining = cursor.fetchone()[0]
print(f'\\nRemaining invalid songs: {remaining}')

cursor.execute('SELECT COUNT(*) FROM songs')
total = cursor.fetchone()[0]
print(f'Total songs: {total}')

conn.close()
