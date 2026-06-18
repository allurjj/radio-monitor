"""
Extract and analyze the failure cases from the combined lookup test
"""

import sqlite3
import json

# Connect to database
conn = sqlite3.connect('radio_songs.db')
cursor = conn.cursor()

# Get all songs
cursor.execute("""
    SELECT DISTINCT a.name, a.mbid, s.song_title
    FROM artists a
    JOIN songs s ON a.mbid = s.artist_mbid
    WHERE a.mbid NOT LIKE 'PENDING%'
    LIMIT 200
""")

songs = cursor.fetchall()
conn.close()

# Known problem cases from test
problem_cases = [
    ("Hamilton", "e7ce3680-bd46-4b62-ba43-b9ca7d77cede", "Don't Pull Your Love Out"),
    ("Captain", "f23c23b2-dc4c-4112-ad70-c3df27b16174", "Love Will Keep Us Together"),
]

print("Known Problem Cases:")
for artist, mbid, song in problem_cases:
    print(f"  {artist} - {song}")
    print(f"    MBID: {mbid}")

# Find other potential problem cases (short artist names that might be abbreviations)
print("\nPotential Problem Cases (short artist names):")
for artist, mbid, song in songs:
    if len(artist) <= 8 and '&' not in artist and ',' not in artist:
        print(f"  {artist} - {song}")
        print(f"    MBID: {mbid}")
