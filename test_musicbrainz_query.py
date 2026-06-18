"""Test MusicBrainz query for Gotye - Somebody That I Used To Know"""
import urllib.request
import urllib.parse
import json
import ssl

# Test 1: MBID query
mbid = "6f6fd596-76e0-4b82-aa37-f558ac2d337b"
song_title = "Somebody That I Used To Know"

query = f'arid:{mbid} AND recording:"{song_title}"'
encoded_query = urllib.parse.quote(query, safe='')
url = f'https://musicbrainz.org/ws/2/recording/?query={encoded_query}&fmt=json&limit=10'

headers = {'User-Agent': 'RadioMonitor/1.0.0 (https://github.com/allurjj/radio-monitor)'}

try:
    req = urllib.request.Request(url, headers=headers)
    ssl_context = ssl._create_unverified_context()

    with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
        if response.status == 200:
            data = json.loads(response.read().decode('utf-8'))
            recordings = data.get('recordings', [])

            print(f"MBID Query for Gotye - Somebody That I Used To Know")
            print(f"Query: {query}")
            print(f"Found {len(recordings)} recordings")

            for recording in recordings:
                print(f"\nRecording: {recording.get('title')}")
                print(f"ID: {recording.get('id')}")
                print(f"Length: {recording.get('length')} ms")

                # Check artist credits
                artist_credits = recording.get('artist-credit', [])
                print(f"Artist Credits:")
                for credit in artist_credits:
                    artist = credit.get('artist', {})
                    print(f"  - {artist.get('name')} (MBID: {artist.get('id')})")
                    if credit.get('joinphrase'):
                        print(f"    Join phrase: '{credit.get('joinphrase')}'")

        else:
            print(f"MusicBrainz returned status {response.status}")

except Exception as e:
    print(f"Error: {e}")

# Test 2: Text query
print("\n" + "=" * 80)
print("TEXT QUERY TEST")
print("=" * 80)

query2 = f'recording of:"{song_title}" by:"Gotye"'
encoded_query2 = urllib.parse.quote(query2, safe='')
url2 = f'https://musicbrainz.org/ws/2/recording/?query={encoded_query2}&fmt=json&limit=10'

try:
    req2 = urllib.request.Request(url2, headers=headers)

    with urllib.request.urlopen(req2, timeout=10, context=ssl_context) as response:
        if response.status == 200:
            data = json.loads(response.read().decode('utf-8'))
            recordings = data.get('recordings', [])

            print(f"Text Query for Gotye - Somebody That I Used To Know")
            print(f"Query: {query2}")
            print(f"Found {len(recordings)} recordings")

            for recording in recordings:
                print(f"\nRecording: {recording.get('title')}")
                print(f"ID: {recording.get('id')}")
                print(f"Length: {recording.get('length')} ms")

                artist_credits = recording.get('artist-credit', [])
                print(f"Artist Credits:")
                for credit in artist_credits:
                    artist = credit.get('artist', {})
                    print(f"  - {artist.get('name')} (MBID: {artist.get('id')})")
                    if credit.get('joinphrase'):
                        print(f"    Join phrase: '{credit.get('joinphrase')}'")

        else:
            print(f"MusicBrainz returned status {response.status}")

except Exception as e:
    print(f"Error: {e}")
