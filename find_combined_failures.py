"""
Identify the 2 cases where combined lookup failed but artist-only succeeded
"""

import sqlite3
import urllib.request
import urllib.parse
import json
import ssl
import time
from radio_monitor.normalization import normalize_artist_name, clean_song_title_for_query

def query_recordings_by_artist_and_song(artist_name: str, song_title: str) -> dict:
    """Query MusicBrainz recordings API with BOTH artist and song"""
    normalized_artist = normalize_artist_name(artist_name)
    cleaned_title = clean_song_title_for_query(song_title)

    encoded_title = urllib.parse.quote(f'"{cleaned_title}"', safe='')
    encoded_artist = urllib.parse.quote(f'"{normalized_artist}"', safe='')

    url = f'https://musicbrainz.org/ws/2/recording/?query=recording:{encoded_title}%20AND%20artist:{encoded_artist}&fmt=json&limit=20'

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'RadioMonitor/1.0.0 (https://github.com/allurjj/radio-monitor)'})
        ssl_context = ssl._create_unverified_context()

        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error: {e}")

    return {'recordings': []}

# Get a sample of songs from database
conn = sqlite3.connect('radio_songs.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT DISTINCT a.name, a.mbid, s.song_title
    FROM artists a
    JOIN songs s ON a.mbid = s.artist_mbid
    WHERE a.mbid NOT LIKE 'PENDING%'
    LIMIT 100
""")

songs = cursor.fetchall()
conn.close()

print("Testing combined lookup on 100 songs to find failures...\n")

combined_failures = []

for i, (artist_name, mbid, song_title) in enumerate(songs, 1):
    # Try combined lookup
    results = query_recordings_by_artist_and_song(artist_name, song_title)

    if not results.get('recordings'):
        combined_failures.append((artist_name, mbid, song_title))
        print(f"{i}. COMBINED LOOKUP FAILED: {artist_name} - {song_title}")
        print(f"   Current MBID: {mbid}")

    # Rate limiting
    time.sleep(1.2)

print(f"\n\nTotal combined lookup failures: {len(combined_failures)}")

if combined_failures:
    print("\nFailure details:")
    for artist, mbid, song in combined_failures:
        print(f"  {artist} - {song}")
        print(f"    MBID: {mbid}")