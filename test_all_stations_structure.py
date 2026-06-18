"""Test scrape all iHeartRadio stations to analyze HTML structure variations"""
import sys
sys.path.insert(0, r'C:\Users\allurjj\Documents\Radio_Monitor')

import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Comprehensive list of iHeartRadio stations with correct URL format
# Based on CLAUDE.md and iHeartRadio URL patterns
stations = [
    # Chicago Stations
    ('us99', 'US99', 'https://www.iheart.com/live/us-99-10819/'),
    ('wls', 'WLSfm', 'https://www.iheart.com/live/947-wls-5367/'),
    ('wlit', '93.9 Lite FM', 'https://www.iheart.com/live/939-lite-fm-853/'),
    ('kiss', '103.5 KISS FM', 'https://www.iheart.com/live/1035-kiss-fm-5922/'),
    ('b96', 'B96', 'https://www.iheart.com/live/b96-353/'),
    ('wgci', 'GCI 101.7', 'https://www.iheart.com/live/gci-1017-5810/'),

    # Rock/Alternative
    ('rock955', 'Rock 95.5', 'https://www.iheart.com/live/rock-955-857/'),
    ('q101', 'Q101', 'https://www.iheart.com/live/q101-6468/'),
    ('wiil', '95 WIIL Rock', 'https://www.iheart.com/live/95-wiil-rock-7716/'),
    ('the_zone', 'The Zone', 'https://www.iheart.com/live/the-zone-chicago-4270/'),
    ('the_loop', 'The Loop', 'https://www.iheart.com/live/97-9-the-loop-97/'),

    # More National/Genre Stations
    ('alt949', 'Alt 949', 'https://www.iheart.com/live/alt-949-4269/'),
    ('kiis', 'KIIS FM', 'https://www.iheart.com/live/kiis-fm-los-angeles-313/'),
    ('z100', 'Z100', 'https://www.iheart.com/live/z100-new-york-41/'),
    ('hot97', 'Hot 97', 'https://www.iheart.com/live/hot-97-nyc-103/'),
    ('power105', 'Power 105.1', 'https://www.iheart.com/live/power-1051-new-york-106/'),

    # Country
    ('country108', 'Country 108', 'https://www.iheart.com/live/country-108-1006/'),
    ('big99', 'Big 99', 'https://www.iheart.com/live/big-99-1007/'),

    # Hip Hop/R&B
    ('beat1027', 'The Beat', 'https://www.iheart.com/live/1027-the-beat-la-4982/'),
    ('hot923', 'Hot 92.3', 'https://www.iheart.com/live/hot-923-4259/'),
    ('power106', 'Power 106', 'https://www.iheart.com/live/power-106-4983/'),

    # Pop/Top 40
    ('star941', 'Star 94.1', 'https://www.iheart.com/live/star-941-atlanta-4264/'),
    ('mix1011', 'Mix 101.1', 'https://www.iheart.com/live/mix-1011-4265/'),

    # Adult Contemporary
    ('softrock', 'Soft Rock', 'https://www.iheart.com/live/soft-rock-4266/'),
    ('myfm', 'MYfm', 'https://www.iheart.com/live/my-fm-4267/'),

    # Classic Hits
    ('kool105', 'KOOL 105', 'https://www.iheart.com/live/kool-105-4268/'),
    ('cbsfm', 'CBS FM', 'https://www.iheart.com/live/1011-cbs-fm-4269/'),

    # More Regional Stations
    ('kisw', 'KISW Seattle', 'https://www.iheart.com/live/kisw-989-fm-seattle-4270/'),
    ('kroq', 'KROQ', 'https://www.iheart.com/live/kroq-4271/'),
    ('wfms', 'WFMS', 'https://www.iheart.com/live/wfms-4272/'),
    ('wqht', 'Hot 97', 'https://www.iheart.com/live/hot-97-4273/'),
]

print(f"Found {len(stations)} iHeartRadio stations to test")
print("=" * 80)

# Track structure variations
structure_stats = {
    'artist_in_parent': 0,
    'artist_in_grandparent': 0,
    'artist_in_great_grandparent': 0,
    'no_artist_link': 0,
    'url_slug_fallback': 0,
    'http_error': 0,
    'no_songs': 0,
}

results = []

for station_id, station_name, station_url in stations:
    print(f"\nTesting {station_id} ({station_name})...")
    print("-" * 80)

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.get(station_url, headers=headers, timeout=15, verify=False)
        response.encoding = 'utf-8'

        if response.status_code != 200:
            print(f"  ERROR: Status {response.status_code}")
            results.append({
                'station_id': station_id,
                'station_name': station_name,
                'status': 'http_error',
                'songs_found': 0
            })
            structure_stats['http_error'] += 1
            continue

        soup = BeautifulSoup(response.text, "html.parser")

        # Find all song links
        song_links = soup.find_all("a", href=lambda h: h and "/songs/" in h)

        if not song_links:
            print(f"  No song links found")
            results.append({
                'station_id': station_id,
                'station_name': station_name,
                'status': 'no_songs',
                'songs_found': 0
            })
            structure_stats['no_songs'] += 1
            continue

        # Analyze first 10 songs for better sample
        station_structure = {
            'parent': 0,
            'grandparent': 0,
            'great_grandparent': 0,
            'no_link': 0,
            'examples': []
        }

        sample_size = min(len(song_links), 10)
        for i, link in enumerate(song_links[:sample_size]):
            song_title = link.get_text(strip=True)
            href = link.get("href", "")

            # Try parent
            parent = link.parent
            artist_link = None
            artist_location = None

            if parent:
                artist_link = parent.find("a", href=lambda h: h and "/artist/" in h and "/songs/" not in h)
                if artist_link:
                    artist_location = 'parent'

            # Try grandparent
            if not artist_link and parent and parent.parent:
                artist_link = parent.parent.find("a", href=lambda h: h and "/artist/" in h and "/songs/" not in h)
                if artist_link:
                    artist_location = 'grandparent'

            # Try great-grandparent
            if not artist_link and parent and parent.parent and parent.parent.parent:
                artist_link = parent.parent.parent.find("a", href=lambda h: h and "/artist/" in h and "/songs/" not in h)
                if artist_link:
                    artist_location = 'great_grandparent'

            # Track structure
            if artist_link:
                artist_name = artist_link.get_text(strip=True)
                station_structure[artist_location] = station_structure.get(artist_location, 0) + 1

                # Save diverse examples (max 2 per location)
                examples_for_location = [ex for ex in station_structure['examples'] if ex['location'] == artist_location]
                if len(examples_for_location) < 2:
                    station_structure['examples'].append({
                        'song': song_title,
                        'artist': artist_name,
                        'location': artist_location
                    })
            else:
                station_structure['no_link'] = station_structure.get('no_link', 0) + 1

        # Determine dominant structure for this station
        max_count = 0
        dominant_structure = 'unknown'
        for key in ['parent', 'grandparent', 'great_grandparent', 'no_link']:
            count = station_structure.get(key, 0)
            if count > max_count:
                max_count = count
                dominant_structure = key

        print(f"  Songs analyzed: {sample_size}")
        print(f"  Structure: {dominant_structure.upper()}")
        print(f"  Examples:")
        for ex in station_structure['examples'][:4]:
            print(f"    - \"{ex['song']}\" by \"{ex['artist']}\" ({ex['location']})")

        results.append({
            'station_id': station_id,
            'station_name': station_name,
            'status': dominant_structure,
            'songs_found': len(song_links),
            'structure': station_structure
        })

        # Update global stats
        structure_stats[dominant_structure] = structure_stats.get(dominant_structure, 0) + 1

    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({
            'station_id': station_id,
            'station_name': station_name,
            'status': 'error',
            'songs_found': 0,
            'error': str(e)
        })
        structure_stats['http_error'] += 1

# Summary
print("\n" + "=" * 80)
print("SUMMARY: HTML Structure Across All Stations")
print("=" * 80)
for key, count in structure_stats.items():
    print(f"  {key}: {count} stations")

# Detailed results
print("\n" + "=" * 80)
print("DETAILED RESULTS BY STATION")
print("=" * 80)
for r in results:
    status = r.get('status', 'unknown')
    if status == 'error':
        print(f"{r['station_id']:15} ({r['station_name']:30}): ERROR - {r.get('error', 'unknown')}")
    elif status == 'no_songs':
        print(f"{r['station_id']:15} ({r['station_name']:30}): No songs found")
    elif status in ['http_error', 'unknown']:
        print(f"{r['station_id']:15} ({r['station_name']:30}): HTTP error")
    else:
        print(f"{r['station_id']:15} ({r['station_name']:30}): {status.upper():15} ({r['songs_found']:3} songs)")

# Save results to file for later analysis
import json
with open('station_structure_analysis.json', 'w') as f:
    json.dump({
        'stats': structure_stats,
        'results': results
    }, f, indent=2)
print(f"\nResults saved to station_structure_analysis.json")
