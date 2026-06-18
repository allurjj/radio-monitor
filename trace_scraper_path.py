"""Check which code path the scraper takes for collaborations"""
import sys
sys.path.insert(0, r'C:\Users\allurjj\Documents\Radio_Monitor')

import re

# Simulate what the scraper does with URL slugs
test_slugs = [
    'gotye-kimbra-12345',
    'pitbull-afrojack-ne-yo-67890',
    'kenny-chesney-uncle-kracker-11111',
    'brad-paisley-alison-krauss-22222',
]

special_cases = {
    'acdc': 'AC/DC',
    'a-ha': 'a-ha',
    'ne-yo': 'Ne-Yo',
    'tpau': "T'Pau",
    'kflay': 'K.Flay',
}

print('URL Slug to Artist Name Conversion:')
print('=' * 80)

for slug in test_slugs:
    # Strip trailing numeric ID
    artist_slug = re.sub(r"-\d+$", "", slug)

    print(f'URL Slug: "{slug}"')
    print(f'After stripping ID: "{artist_slug}"')

    # Check special cases
    if artist_slug.lower() in special_cases:
        artist_name = special_cases[artist_slug.lower()]
        print(f'Special case: "{artist_name}"')
    else:
        # Default: convert all dashes to spaces
        artist_name = artist_slug.replace("-", " ").title()
        print(f'Default conversion: "{artist_name}"')
    print()

print('=' * 80)
print('Expected vs Actual:')
print('=' * 80)

expected = [
    ('gotye-kimbra', 'Gotye & Kimbra'),  # What iHeartRadio has
    ('pitbull-afrojack-ne-yo', 'Pitbull, Afrojack & Ne-Yo'),  # What iHeartRadio has
    ('kenny-chesney-uncle-kracker', 'Kenny Chesney;Uncle Kracker'),  # What iHeartRadio has
]

for slug, expected_artist in expected:
    artist_slug = re.sub(r"-\d+$", "", slug)
    artist_name = artist_slug.replace("-", " ").title()
    print(f'Slug: "{slug}"')
    print(f'  Expected (from iHeartRadio): "{expected_artist}"')
    print(f'  Actual (from URL conversion): "{artist_name}"')
    print(f'  Match: {expected_artist == artist_name}')
    print()
