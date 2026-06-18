from radio_monitor.recording_validation import validate_recording_with_fallback
from radio_monitor.normalization import clean_song_title_for_query

# Test each invalid song
invalid_songs = [
    {
        'id': 35,
        'mbid': 'be732ef2-9119-4626-ad87-69039cf902c4',
        'artist': 'OhGeesy',
        'song': 'GEEKALEEK (feat. Cash Kidd)'
    },
    {
        'id': 92,
        'mbid': '3b387def-cfed-4c35-a038-bc3e8d30e377',
        'artist': 'John Morgan',
        'song': 'Friends Like That (feat. Jason Aldean)'
    },
    {
        'id': 192,
        'mbid': '4464b4c9-a52a-47e8-a195-912b8a18d0bf',
        'artist': '7 Seals',
        'song': 'Summer Breeze'
    },
    {
        'id': 224,
        'mbid': '3ae306a3-b2a6-4969-b59f-89f0370549e5',
        'artist': 'Ingrid Andress',
        'song': 'Wishful Drinking (with Sam Hunt)'
    }
]

print("Testing recording validation for invalid songs:")
print("=" * 80)

for song in invalid_songs:
    print(f"\nSong ID: {song['id']}")
    print(f"Artist: {song['artist']} (MBID: {song['mbid']})")
    print(f"Song: {song['song']}")
    print("-" * 80)

    # Show cleaned title
    cleaned = clean_song_title_for_query(song['song'])
    print(f"Original title: {song['song']}")
    print(f"Cleaned title: {cleaned}")

    # Try validation
    try:
        found, method = validate_recording_with_fallback(
            artist_name=song['artist'],
            song_title=song['song'],
            artist_mbid=song['mbid']
        )
        print(f"Result: found={found}, method={method}")

        # Also try with cleaned title
        found_cleaned, method_cleaned = validate_recording_with_fallback(
            artist_name=song['artist'],
            song_title=cleaned,
            artist_mbid=song['mbid']
        )
        print(f"With cleaned title: found={found_cleaned}, method={method_cleaned}")
    except Exception as e:
        print(f"Error: {e}")
