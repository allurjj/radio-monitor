#!/usr/bin/env python3
"""Investigate failed validation songs"""

import sys
sys.path.insert(0, 'C:/Users/allurjj/Documents/Radio_Monitor')

import sqlite3
import urllib.request
import urllib.parse
import json
import ssl
from radio_monitor.recording_validation import validate_recording_with_fallback

conn = sqlite3.connect('C:/Users/allurjj/Documents/Radio_Monitor/radio_songs.db')
c = conn.cursor()

# Failed songs from re-validation
failed_songs = [
    ('Morgan Wallen', 'Thinkin Bout Me'),
    ('Chris Janson', 'Me & A Beer'),
    ('Taking Back Sunday', 'Liar (It Takes One To Know One)'),
    ('Shaboozey', 'A Bar Song (Tipsy)')
]

for artist_name, song_title in failed_songs:
    print('=' * 60)
    print(f'Artist: {artist_name}')
    print(f'Song: {song_title}')
    print()

    # Get song details from database
    c.execute('''
        SELECT id, artist_name, song_title, artist_mbid, validation_status, validation_method
        FROM songs
        WHERE artist_name = ? AND song_title = ?
    ''', (artist_name, song_title))

    result = c.fetchone()
    if result:
        song_id, db_artist, db_title, artist_mbid, val_status, val_method = result
        print(f'DB ID: {song_id}')
        print(f'Artist MBID: {artist_mbid}')
        print(f'Current Validation: {val_status} ({val_method})')
        print()

        # Test validation with our fix
        print('Testing with v1.4.18 fix:')
        try:
            found, method = validate_recording_with_fallback(
                artist_name=db_artist,
                song_title=db_title,
                artist_mbid=artist_mbid
            )
            print(f'  Result: found={found}, method={method}')
        except Exception as e:
            print(f'  Error: {e}')

        # Test MusicBrainz query directly
        print()
        print('MusicBrainz query test:')

        # Try MBID query
        if artist_mbid and not artist_mbid.startswith('PENDING-'):
            query = f'arid:{artist_mbid} AND recording:"{db_title}"'
            encoded_query = urllib.parse.quote(query, safe='')
            url = f'https://musicbrainz.org/ws/2/recording/?query={encoded_query}&fmt=json&limit=5'

            headers = {'User-Agent': 'RadioMonitor/1.0.0 (https://github.com/allurjj/radio-monitor)'}

            try:
                req = urllib.request.Request(url, headers=headers)
                ssl_context = ssl._create_unverified_context()
                with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    recordings = data.get('recordings', [])
                    print(f'  MBID query found {len(recordings)} recordings:')
                    for r in recordings[:3]:
                        mb_title = r.get('title', '')
                        print(f'    - "{mb_title}"')
            except Exception as e:
                print(f'  MBID query error: {e}')

        # Try text query
        query = f'recording of:"{db_title}" by:"{db_artist}"'
        encoded_query = urllib.parse.quote(query, safe='')
        url = f'https://musicbrainz.org/ws/2/recording/?query={encoded_query}&fmt=json&limit=5'

        try:
            req = urllib.request.Request(url, headers=headers)
            ssl_context = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                data = json.loads(response.read().decode('utf-8'))
                recordings = data.get('recordings', [])
                print(f'  Text query found {len(recordings)} recordings:')
                for r in recordings[:3]:
                    mb_title = r.get('title', '')
                    print(f'    - "{mb_title}"')
        except Exception as e:
            print(f'  Text query error: {e}')

    print()

conn.close()
