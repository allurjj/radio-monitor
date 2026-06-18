"""Detailed check of Gotye Kimbra in database"""
import sqlite3

conn = sqlite3.connect('radio_songs.db')
cursor = conn.cursor()

# Check the specific song with MBID
cursor.execute("""
    SELECT id, artist_name, song_title, artist_mbid, validation_status,
           validated_at, validation_method, first_seen_at, last_seen_at, play_count
    FROM songs
    WHERE artist_mbid = '6f6fd596-76e0-4b82-aa37-f558ac2d337b'
    AND song_title LIKE '%Somebody%'
""")

rows = cursor.fetchall()
print(f"Found {len(rows)} songs with Gotye MBID")
for row in rows:
    song_id, artist, song, mbid, status, validated_at, method, first_seen, last_seen, plays = row
    print(f"\nID: {song_id}")
    print(f"  Artist: {artist}")
    print(f"  Song: {song}")
    print(f"  MBID: {mbid}")
    print(f"  Validation Status: {status}")
    print(f"  Validated At: {validated_at}")
    print(f"  Validation Method: {method}")
    print(f"  First Seen: {first_seen}")
    print(f"  Last Seen: {last_seen}")
    print(f"  Play Count: {plays}")

# Check what artist this MBID belongs to
print("\n" + "=" * 80)
print("Artist table lookup:")
cursor.execute("""
    SELECT mbid, name FROM artists WHERE mbid = '6f6fd596-76e0-4b82-aa37-f558ac2d337b'
""")
row = cursor.fetchone()
if row:
    mbid, name = row
    print(f"MBID {mbid} belongs to artist: {name}")
else:
    print("MBID not found in artists table!")

# Check for Gotye Kimbra variations
print("\n" + "=" * 80)
print("All 'Gotye Kimbra' variations:")
cursor.execute("""
    SELECT id, artist_name, song_title, artist_mbid, validation_status, validation_method
    FROM songs
    WHERE artist_name LIKE '%Gotye%'
    ORDER BY id
""")
for row in cursor.fetchall():
    song_id, artist, song, mbid, status, method = row
    print(f"ID {song_id}: {artist} - {song} ({mbid}) - {status} ({method})")

conn.close()
