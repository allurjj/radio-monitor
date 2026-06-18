"""Test live iHeartRadio scraper to see actual artist data"""
import sys
sys.path.insert(0, 'C:\\Users\\allurjj\\Documents\\Radio_Monitor')

import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Test with a specific iHeartRadio station
stations_to_test = [
    'https://www.iheart.com/artist/kenny-chesney-5216/songs/',  # Kenny Chesney
    'https://www.iheart.com/artist/brad-paisley-4250/songs/',   # Brad Paisley
]

# Or test a live station page
live_station = 'https://www.iheart.com/chicago/us99-1019/'  # US99 (country station)

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

print(f"Testing live station: {live_station}")
print("=" * 80)

try:
    response = requests.get(live_station, headers=headers, timeout=15, verify=False)
    response.encoding = 'utf-8'

    soup = BeautifulSoup(response.text, "html.parser")

    # Find all artist links
    artist_links = soup.find_all("a", href=lambda h: h and "/artist/" in h and "/songs/" not in h)

    print(f"Found {len(artist_links)} artist links")
    print("\nFirst 20 artist names from iHeartRadio:")
    print("-" * 80)

    for i, link in enumerate(artist_links[:20]):
        artist_name = link.get_text(strip=True)
        print(f"{i+1}. '{artist_name}'")

    # Also check for the specific collaborations
    print("\n" + "=" * 80)
    print("Looking for specific collaborations:")
    print("=" * 80)

    target_artists = ['Gotye', 'Kimbra', 'Kenny', 'Chesney', 'Uncle', 'Kracker', 'Brad', 'Paisley', 'Alison', 'Krauss', 'Pitbull', 'Afrojack', 'Ne-Yo']

    for link in artist_links:
        artist_name = link.get_text(strip=True).lower()
        for target in target_artists:
            if target.lower() in artist_name:
                print(f"Found: '{link.get_text(strip=True)}'")
                break

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
