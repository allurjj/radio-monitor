"""Temporary script to check collaboration songs in database"""
import sqlite3
import json

conn = sqlite3.connect('radio_songs.db')
cursor = conn.cursor()

# Get a sample of songs with multi-word artist names that might be collaborations
# Looking for artist names with 3+ words, no "feat." or "&" separators
cursor.execute("""
    SELECT id, artist_name, song_title, artist_mbid, validation_status
    FROM songs
    WHERE length(artist_name) - length(replace(artist_name, ' ', '')) >= 2
    AND artist_mbid LIKE 'PENDING-%'
    ORDER BY play_count DESC
    LIMIT 20
""")

rows = cursor.fetchall()

print("Collaboration candidates (multi-word artists with PENDING MBID):")
print("-" * 80)
for row in rows:
    song_id, artist, song, mbid, status = row
    print(f"ID: {song_id}")
    print(f"  Artist: {artist}")
    print(f"  Song: {song}")
    print(f"  MBID: {mbid}")
    print(f"  Status: {status}")
    print()

# Specific examples from user
examples = [
    'Pitbull Afrojack',
    'Dht',
    'Eurythmics Annie Lennox',
    'Gotye Kimbra',
    'Kenny Chesneyuncle',
    'Magic - Rude',
    'Dj Sammy Yanou',
    'Nsync - Bye',
    'Beyonce - Irreplaceable',
    'Brad Paisleyalison'
]

print("\n" + "=" * 80)
print("Specific user examples:")
print("=" * 80)
for q in examples:
    cursor.execute("""
        SELECT id, artist_name, song_title, artist_mbid, validation_status
        FROM songs
        WHERE artist_name LIKE ?
        LIMIT 1
    """, ('%' + q + '%',))
    row = cursor.fetchone()
    if row:
        song_id, artist, song, mbid, status = row
        print(f"\nQuery: {q}")
        print(f"  Artist: {artist}")
        print(f"  Song: {song}")
        print(f"  MBID: {mbid}")
        print(f"  Status: {status}")

conn.close()
