from radio_monitor.database import RadioDatabase
from radio_monitor.gui import load_settings

settings = load_settings()
db = RadioDatabase(settings.get('database_path', 'radio_songs.db'))
db.connect()
cursor = db.get_cursor()

# Find songs that failed validation (INVALID status or not VERIFIED after validation attempts)
cursor.execute("""
    SELECT id, artist_mbid, artist_name, song_title, verification_status
    FROM songs
    WHERE verification_status = 'INVALID'
    ORDER BY id
    LIMIT 20
""")
invalid_results = cursor.fetchall()

print(f"Found {len(invalid_results)} INVALID songs:")
for r in invalid_results:
    print(f"ID: {r[0]}, MBID: {r[1]}, Artist: {r[2]}, Song: {r[3]}, Status: {r[4]}")

# Also check for songs with validation attempts that failed
cursor.execute("""
    SELECT id, artist_mbid, artist_name, song_title, verification_status
    FROM songs
    WHERE verification_status != 'VERIFIED' AND verification_status != 'UNVERIFIED'
    ORDER BY id
    LIMIT 20
""")
other_results = cursor.fetchall()

print(f"\nFound {len(other_results)} songs with non-standard verification status:")
for r in other_results:
    print(f"ID: {r[0]}, MBID: {r[1]}, Artist: {r[2]}, Song: {r[3]}, Status: {r[4]}")

cursor.close()
db.close()
