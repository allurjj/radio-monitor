"""Check why Gotye Kimbra validation failed"""
import sqlite3

conn = sqlite3.connect('radio_songs.db')
cursor = conn.cursor()

# Get detailed validation info for Gotye Kimbra
cursor.execute("""
    SELECT id, artist_name, song_title, artist_mbid, validation_status,
           validated_at, validation_method
    FROM songs
    WHERE artist_name LIKE '%Gotye Kimbra%'
""")

row = cursor.fetchone()
if row:
    song_id, artist, song, mbid, status, validated_at, method = row
    error = None
    print(f"Gotye Kimbra - Somebody That I Used To Know:")
    print(f"  Artist: {artist}")
    print(f"  Song: {song}")
    print(f"  MBID: {mbid}")
    print(f"  Status: {status}")
    print(f"  Validated At: {validated_at}")
    print(f"  Method: {method}")
    print(f"  Error: {error}")

# Also check what the correct MBID should be
print("\n" + "=" * 80)
print("MusicBrainz query results for 'Gotye Kimbra':")

# We can't query MusicBrainz without the API, but let's check if there are other Gotye songs
cursor.execute("""
    SELECT id, artist_name, song_title, artist_mbid, validation_status
    FROM songs
    WHERE artist_name LIKE '%Gotye%'
    ORDER BY play_count DESC
""")

print("\nAll Gotye songs in database:")
for row in cursor.fetchall():
    song_id, artist, song, mbid, status = row
    print(f"  {artist} - {song} ({mbid}) - {status}")

conn.close()
