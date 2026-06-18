#!/usr/bin/env python3
"""Investigate pending artists via MusicBrainz API."""

import requests
import json

# User agent required by MusicBrainz
USER_AGENT = "RadioMonitor/1.0 (https://github.com/allurjj/radio-monitor)"

pending_artists = [
    ("Ne-Yo", "PENDING-322f1db4b7d0cf09ccde8516f5d34eb0"),
    ("K-Ci", "PENDING-988eb3507b8c5d2b552e891545e6349e"),
]

print("Investigating pending artists via MusicBrainz API:\n")

for name, pending_mbid in pending_artists:
    print(f"=== {name} ===")
    print(f"Pending MBID: {pending_mbid}")

    # Query MusicBrainz
    url = f"https://musicbrainz.org/ws/2/artist/?query=artist:{name}&fmt=json&limit=5"
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            artists = data.get("artists", [])

            if artists:
                print(f"Found {len(artists)} result(s):")
                for artist in artists[:3]:
                    mbid = artist.get("id")
                    a_name = artist.get("name")
                    score = artist.get("score", 0)
                    print(f"  - MBID: {mbid}")
                    print(f"    Name: {a_name}")
                    print(f"    Score: {score}")

                    # Check for aliases or type info
                    if "aliases" in artist and artist["aliases"]:
                        print(f"    Aliases: {[a.get('name') for a in artist['aliases'][:3]]}")
            else:
                print("  No results found from MusicBrainz")
        else:
            print(f"  API Error: HTTP {response.status_code}")
    except Exception as e:
        print(f"  Error: {e}")

    print()
