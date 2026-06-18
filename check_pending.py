#!/usr/bin/env python3
"""Check pending artists in database."""

from radio_monitor.database import RadioDatabase

db = RadioDatabase('radio_songs.db')
db.connect()
cursor = db.get_cursor()

# Get pending artists
cursor.execute('SELECT mbid, name FROM artists WHERE mbid LIKE "PENDING-%"')
pending_artists = cursor.fetchall()

print(f"Found {len(pending_artists)} pending artist(s):")
for mbid, name in pending_artists:
    print(f"\n  Name: {name}")
    print(f"  MBID: {mbid}")

    # Check songs associated with this artist
    cursor.execute('''
        SELECT song_title, first_seen_at, play_count
        FROM songs
        WHERE artist_mbid = ?
        ORDER BY first_seen_at DESC
    ''', (mbid,))
    songs = cursor.fetchall()
    print(f"  Songs ({len(songs)}):")
    for song_title, first_seen, play_count in songs:
        print(f"    - {song_title} (first seen: {first_seen}, play_count: {play_count})")

cursor.close()
