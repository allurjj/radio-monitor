"""Test live iHeartRadio scraper - debug HTML"""
import sys
sys.path.insert(0, 'C:\\Users\\allurjj\\Documents\\Radio_Monitor')

import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

live_station = 'https://www.iheart.com/chicago/us99-1019/'

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

    print(f"Status: {response.status_code}")
    print(f"Content length: {len(response.text)}")

    # Save HTML to file for inspection
    with open('iheart_html.txt', 'w', encoding='utf-8') as f:
        f.write(response.text)
    print("Saved HTML to iheart_html.txt")

    # Look for common collaboration patterns in the HTML
    print("\n" + "=" * 80)
    print("Looking for artist collaboration patterns in HTML:")
    print("=" * 80)

    search_patterns = [
        'Gotye',
        'Kimbra',
        'Kenny',
        'Chesney',
        'Pitbull',
        'Afrojack',
        'Ne-Yo',
        'Brad',
        'Paisley',
        'Alison',
        'Krauss',
        'feat.',
        'featuring',
        '&',
        ';',
    ]

    html_lower = response.text.lower()

    for pattern in search_patterns:
        if pattern.lower() in html_lower:
            # Find context around the pattern
            idx = html_lower.find(pattern.lower())
            context = response.text[max(0, idx-100):idx+100]
            print(f"\nFound '{pattern}':")
            print(f"  Context: ...{context}...")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
