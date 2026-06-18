from radio_monitor.database import RadioDatabase
from radio_monitor.gui import load_settings
from radio_monitor.recording_validation import validate_recording_with_fallback
from radio_monitor.data_quality import mark_song_validated

# Song IDs to re-validate
song_ids = [35, 92, 192, 224]

settings = load_settings()
db = RadioDatabase(settings.get('database_path', 'radio_songs.db'))
db.connect()

print("Re-validating previously invalid songs:")
print("=" * 80)

for song_id in song_ids:
    cursor = db.get_cursor()
    cursor.execute("SELECT id, artist_mbid, artist_name, song_title FROM songs WHERE id = ?", (song_id,))
    result = cursor.fetchone()
    cursor.close()

    if result:
        song_id, artist_mbid, artist_name, song_title = result
        print(f"\nSong ID: {song_id}")
        print(f"Artist: {artist_name}")
        print(f"Song: {song_title}")

        try:
            found, method = validate_recording_with_fallback(
                artist_name=artist_name,
                song_title=song_title,
                artist_mbid=artist_mbid
            )

            print(f"Result: found={found}, method={method}")

            # Mark as validated
            mark_song_validated(db, song_id, success=found, method=method)

            if found:
                print(f"[VALID] Song marked as VALID")
            else:
                print(f"[INVALID] Song marked as INVALID (not found in MusicBrainz)")

        except Exception as e:
            print(f"Error: {e}")

print("\n" + "=" * 80)
print("Re-validation complete!")

db.close()
