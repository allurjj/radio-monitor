"""Test handle_collaboration with iHeartRadio formats"""
import sys
sys.path.insert(0, r'C:\Users\allurjj\Documents\Radio_Monitor')

from radio_monitor.normalization import handle_collaboration, detect_collaboration, normalize_with_edge_cases

# Test with what user says iHeartRadio has
test_cases = [
    ('Gotye & Kimbra', 'Somebody That I Used To Know'),
    ('Pitbull, Afrojack & Ne-Yo feat. Nayer', 'Give Me Everything'),
    ('Kenny Chesney;Uncle Kracker', 'When the Sun Goes Down'),
    ('Brad Paisley;Alison Krauss', 'Whiskey Lullaby'),
]

print('Testing handle_collaboration with iHeartRadio formats:')
print('=' * 80)

for artist, song in test_cases:
    result = handle_collaboration(artist, song, None)
    if result:
        primary_artist, processed_song, mbid = result[0]
        print(f'Input:  "{artist}"')
        print(f'Output: Primary artist = "{primary_artist}"')
        print(f'        Song = "{processed_song}"')
        print()
    else:
        print(f'Input:  "{artist}" -> NO RESULT')
        print()

print('=' * 80)
print('Testing what gets NORMALIZED:')
print('=' * 80)

for artist, song in test_cases:
    normalized = normalize_with_edge_cases(artist)
    print(f'Input:  "{artist}"')
    print(f'Normalized: "{normalized}"')
    print()

print('=' * 80)
print('Testing detect_collaboration:')
print('=' * 80)

for artist, song in test_cases:
    is_collab, split_artists = detect_collaboration(artist)
    print(f'Input:  "{artist}"')
    print(f'Detected: {is_collab}')
    print(f'Split:    {split_artists}')
    print()
