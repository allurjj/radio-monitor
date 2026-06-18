#!/usr/bin/env python3
"""Debug MusicBrainz API responses for K-Ci and Ne-Yo."""

import urllib.request
import urllib.parse
import urllib.error
import json
import ssl
import sys

# Fix Unicode output to Windows console
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# User agent required by MusicBrainz
USER_AGENT = "RadioMonitor/1.0 (https://github.com/allurjj/radio-monitor)"

def query_musicbrainz(artist_name):
    """Query MusicBrainz API for an artist."""
    url = f"https://musicbrainz.org/ws/2/artist/?query=artist:{urllib.parse.quote(artist_name)}&fmt=json&limit=10"

    context = ssl._create_unverified_context()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=10, context=context) as response:
            data = json.loads(response.read().decode())
            return data.get("artists", [])
    except Exception as e:
        print(f"  Error: {e}")
        return []

# Test both artists
for artist in ["K-Ci", "Ne-Yo"]:
    print(f"\n=== Querying MusicBrainz for '{artist}' ===")
    results = query_musicbrainz(artist)

    if results:
        print(f"Found {len(results)} result(s):")
        for i, result in enumerate(results[:5]):
            mbid = result.get("id")
            name = result.get("name")
            score = result.get("score", 0)
            print(f"\n  [{i+1}] MBID: {mbid}")
            print(f"      Name: '{name}'")
            print(f"      Score: {score}")

            # Check for exact match
            from radio_monitor.normalization import normalize_artist_name
            normalized_input = normalize_artist_name(artist).lower().strip()
            normalized_result = normalize_artist_name(name).lower().strip()
            print(f"      Input normalized: '{normalized_input}'")
            print(f"      Result normalized: '{normalized_result}'")
            print(f"      Exact match: {normalized_input == normalized_result}")

            # Show character-by-character comparison
            print(f"      Input chars: {[c for c in artist.lower()]}")
            print(f"      Result chars: {[c for c in name.lower()]}")
    else:
        print("  No results found")
