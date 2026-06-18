#!/usr/bin/env python3
"""Direct retry of pending artists without prompt."""

from radio_monitor.database import RadioDatabase
from radio_monitor.mbid import retry_pending_artists

print("Retrying MBID lookup for PENDING artists...")
print("This may take a while (8 seconds per artist due to MusicBrainz rate limiting)\n")

db = RadioDatabase('radio_songs.db')
db.connect()

# Retry all pending artists (no limit)
results = retry_pending_artists(db, max_artists=None)

print(f"\nResults:")
print(f"  Total PENDING artists: {results['total']}")
print(f"  Resolved: {results['resolved']}")
print(f"  Still failed: {results['failed']}")

if results['results']:
    print("\nResolved artists:")
    for result in results['results']:
        status = "[OK]" if result.get('success') else "[FAILED]"
        old = result.get('old_mbid', 'N/A')
        new = result.get('new_mbid') if result.get('new_mbid') else '(None, None)'
        print(f"  {status} {result.get('name', 'Unknown')}: {old} -> {new}")

db.conn.close()
