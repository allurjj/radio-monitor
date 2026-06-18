from radio_monitor.database import RadioDatabase
from radio_monitor.gui import load_settings

settings = load_settings()
db = RadioDatabase(settings.get('database_path', 'radio_songs.db'))
db.connect()
cursor = db.get_cursor()

# Find unverified songs
cursor.execute("""
    SELECT id, artist_mbid, artist_name, song_title, verification_status
    FROM songs
    WHERE verification_status != 'VERIFIED' OR verification_status IS NULL
    LIMIT 20
""")
results = cursor.fetchall()

print(f"Found {len(results)} unverified songs:")
print()
for r in results:
    print(f"ID: {r[0]}, MBID: {r[1]}, Artist: {r[2]}, Song: {r[3]}, Status: {r[4]}")

cursor.close()
db.close()
