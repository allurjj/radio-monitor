#!/usr/bin/env python3
"""Debug comparison logic"""

import sys
sys.path.insert(0, 'C:/Users/allurjj/Documents/Radio_Monitor')

import urllib.request
import urllib.parse
import json
import ssl
import unicodedata
import re

# Failed songs
test_cases = [
    ('Chris Janson', 'Me & A Beer', '0fed966c-27ce-4866-a122-06d4133d8207'),
    ('Taking Back Sunday', 'Liar (It Takes One To Know One)', '350bce49-c21b-4137-b50a-0766ded07e4d'),
    ('Shaboozey', 'A Bar Song (Tipsy)', '0b427dad-1ee5-48f1-aa4b-026680a3338e'),
]

for artist_name, song_title, artist_mbid in test_cases:
    print('=' * 60)
    print(f'Testing: {artist_name} - {song_title}')
    print()

    # Query MusicBrainz
    query = f'arid:{artist_mbid} AND recording:"{song_title}"'
    encoded_query = urllib.parse.quote(query, safe='')
    url = f'https://musicbrainz.org/ws/2/recording/?query={encoded_query}&fmt=json&limit=5'

    headers = {'User-Agent': 'RadioMonitor/1.0.0 (https://github.com/allurjj/radio-monitor)'}

    req = urllib.request.Request(url, headers=headers)
    ssl_context = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
        data = json.loads(response.read().decode('utf-8'))
        recordings = data.get('recordings', [])

        print(f'Found {len(recordings)} recordings')

        if recordings:
            r = recordings[0]
            mb_title = r.get('title', '')

            print(f'\nOur title: "{song_title}"')
            print(f'MB title:  "{mb_title}"')
            print()

            # Check character by character
            print('Character comparison:')
            for i, (c1, c2) in enumerate(zip(mb_title, song_title)):
                match = 'OK' if c1 == c2 else 'X'
                print(f'  {i:2d}: MB="{c1}" (U+{ord(c1):04X}) vs Us="{c2}" (U+{ord(c2):04X}) {match}')
                if c1 != c2:
                    print(f'      ^ MISMATCH at position {i}')

            # Test our normalization
            print()
            print('After our normalization:')

            # Original MB title
            original_mb = mb_title

            # Step 1: NFKC normalization
            normalized = unicodedata.normalize('NFKC', original_mb)

            # Step 2: Replace apostrophe variations
            normalized = re.sub(r"[''`‛❜❛❝❞]", "'", normalized)

            # Step 3: Replace control characters
            normalized = re.sub(r'[\x00-\x1F\x7F-\x9F]', "'", normalized)

            print(f'  Original MB:  "{original_mb}"')
            print(f'  Normalized MB: "{normalized}"')
            print(f'  Our title:    "{song_title}"')
            print()

            # Lowercase comparison
            print(f'  Lowercase MB:  "{normalized.lower()}"')
            print(f'  Lowercase Us:  "{song_title.lower()}"')
            print(f'  Match: {normalized.lower() == song_title.lower()}')

    print()

conn.close()
