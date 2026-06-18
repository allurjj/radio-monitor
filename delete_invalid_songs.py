"""Delete all invalid songs from database"""
import sys
sys.path.insert(0, r'C:\Users\allurjj\Documents\Radio_Monitor')
import sqlite3

DB_PATH = 'radio_songs.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print('=== Deleting Invalid Songs ===')
print()

# Count invalid songs
cursor.execute('SELECT COUNT(*) FROM songs WHERE validation_status = "invalid"')
count = cursor.fetchone()[0]
print(f'Found {count} invalid songs')

if count > 0:
    # Show sample
    cursor.execute('''
        SELECT id, song_title, artist_name, play_count
        FROM songs
        WHERE validation_status = 'invalid'
        ORDER BY play_count DESC
        LIMIT 10
    ''')
    print('\\nSample (highest play counts):')
    for row in cursor.fetchall():
        song_id, title, artist, plays = row
        print(f'  ID {song_id}: {title[:35]:35} | {artist[:25]:25} | plays: {plays}')

    # Delete them
    print(f'\\nDeleting {count} invalid songs...')
    cursor.execute('DELETE FROM songs WHERE validation_status = "invalid"')
    deleted = cursor.rowcount
    conn.commit()

    print(f'Deleted {deleted} songs')

    # Verify
    cursor.execute('SELECT COUNT(*) FROM songs WHERE validation_status = "invalid"')
    remaining = cursor.fetchone()[0]
    print(f'Remaining invalid songs: {remaining}')

    cursor.execute('SELECT COUNT(*) FROM songs')
    total = cursor.fetchone()[0]
    print(f'Total songs: {total}')
else:
    print('No invalid songs found')

conn.close()
