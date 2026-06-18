from radio_monitor.database import RadioDatabase
from radio_monitor.gui import load_settings

settings = load_settings()
db = RadioDatabase(settings.get('database_path', 'radio_songs.db'))
db.connect()
cursor = db.get_cursor()

# Check if validation_status column exists
cursor.execute("PRAGMA table_info(songs)")
columns = [row[1] for row in cursor.fetchall()]

print(f"Columns in songs table: {columns}")
print()

# Check validation statuses if column exists
if 'validation_status' in columns:
    # Count each status
    cursor.execute("SELECT validation_status, COUNT(*) FROM songs GROUP BY validation_status ORDER BY validation_status")
    status_counts = cursor.fetchall()

    print("Validation status counts:")
    for status, count in status_counts:
        print(f"  {status}: {count}")
    print()

    # Get invalid songs
    cursor.execute("""
        SELECT id, artist_mbid, artist_name, song_title, validation_status, validation_method, validated_at
        FROM songs
        WHERE validation_status = 'invalid'
        ORDER BY id
    """)
    invalid_songs = cursor.fetchall()

    print(f"Found {len(invalid_songs)} INVALID songs:")
    for r in invalid_songs:
        print(f"ID: {r[0]}, MBID: {r[1]}, Artist: {r[2]}, Song: {r[3]}, Status: {r[4]}, Method: {r[5]}, Validated: {r[6]}")
else:
    print("validation_status column does not exist")

cursor.close()
db.close()
