"""Test collaboration detection with iHeartRadio formats"""
import sys
sys.path.insert(0, 'C:\\Users\\allurjj\\Documents\\Radio_Monitor')

from radio_monitor.normalization import detect_collaboration, split_collaboration_artists, handle_collaboration

# Test cases from iHeartRadio
test_cases = [
    "Gotye & Kimbra",
    "Kenny Chesney;Uncle Kracker",
    "Pitbull, Afrojack & Ne-Yo feat. Nayer",
    "DHT",
    "Dj Sammy Yanou",
    "Eurythmics Annie Lennox Dave Stewart",
    "Brad Paisleyalison Krauss",
    "The Weeknd Daft Punk",
]

print("Collaboration Detection Test:")
print("=" * 80)

for artist in test_cases:
    is_collab, split_artists = detect_collaboration(artist)
    print(f"\nArtist: '{artist}'")
    print(f"  Detected as collaboration: {is_collab}")
    print(f"  Split result: {split_artists}")

    # Also test handle_collaboration
    result = handle_collaboration(artist, "Test Song", None)
    if result:
        primary, song, mbid = result[0]
        print(f"  handle_collaboration -> Primary: '{primary}'")
    else:
        print(f"  handle_collaboration -> Empty result!")

print("\n" + "=" * 80)
print("Individual Test of detect_collaboration patterns:")
print("=" * 80)

# Check what patterns are being detected
artist_lower_test_cases = [
    ("Gotye & Kimbra", "&"),
    ("Kenny Chesney;Uncle Kracker", ";"),
    ("Pitbull, Afrojack & Ne-Yo feat. Nayer", ","),
    ("Pitbull feat. Nayer", " feat"),
]

for artist, expected_sep in artist_lower_test_cases:
    artist_lower = artist.lower().strip()
    collab_patterns = [
        ' feat', ' ft.', ' ft ', 'featuring', ' with ', ' & ', ' + ', ' x ', ' and '
    ]

    found = False
    for pattern in collab_patterns:
        if pattern in artist_lower:
            print(f"'{artist}': Found pattern '{pattern}' (expected '{expected_sep}')")
            found = True
            break

    if not found:
        print(f"'{artist}': NO PATTERN FOUND (expected '{expected_sep}')")
