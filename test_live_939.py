"""Fetch and analyze live iHeartRadio 93.9 page"""
import requests
from bs4 import BeautifulSoup
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = 'https://www.iheart.com/live/939-lite-fm-853'

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

print(f"Fetching: {url}")
print("=" * 80)

try:
    response = requests.get(url, headers=headers, timeout=15, verify=False)
    response.encoding = 'utf-8'

    print(f"Status: {response.status_code}")
    print(f"Content length: {len(response.text)}")

    # Save HTML for inspection
    with open('iheart_939_live.html', 'w', encoding='utf-8') as f:
        f.write(response.text)
    print("Saved HTML to iheart_939_live.html")

    # Parse HTML
    soup = BeautifulSoup(response.text, "html.parser")

    # Look for song/artist links
    print("\n" + "=" * 80)
    print("Looking for song/artist links:")
    print("=" * 80)

    # Find all song links
    song_links = soup.find_all("a", href=lambda h: h and "/songs/" in h)
    print(f"Found {len(song_links)} song links")

    # Analyze first 20 songs
    for i, link in enumerate(song_links[:20]):
        song_title = link.get_text(strip=True)
        song_href = link.get("href", "")

        # Check if there's an artist link in the same parent
        parent = link.parent
        artist_link = parent.find(
            "a", href=lambda h: h and "/artist/" in h and "/songs/" not in h
        ) if parent else None

        print(f"\nSong {i+1}: '{song_title}'")
        print(f"  Song href: {song_href}")

        if artist_link:
            artist_name = artist_link.get_text(strip=True)
            artist_href = artist_link.get("href", "")
            print(f"  Artist link found: {artist_href}")
            print(f"  Artist name: '{artist_name}'")
        else:
            # No artist link - check parent text
            parent_text = parent.get_text(strip=True)
            print(f"  NO artist link found!")
            print(f"  Parent text: '{parent_text}'")

            # Try to extract from URL slug
            parts = song_href.strip("/").split("/")
            if len(parts) > 1:
                artist_slug = parts[1]
                # Strip trailing numeric ID
                artist_slug = re.sub(r"-\d+$", "", artist_slug)
                # Convert dashes to spaces
                from_slug = artist_slug.replace("-", " ").title()
                print(f"  URL slug: {artist_slug}")
                print(f"  From slug: '{from_slug}'")

    # Look for the specific songs user mentioned
    print("\n" + "=" * 80)
    print("Looking for specific songs:")
    print("=" * 80)

    target_patterns = ['golden', 'nsync', 'this i promise', 'purple rain', 'prince']

    for link in song_links:
        song_title = link.get_text(strip=True).lower()
        for pattern in target_patterns:
            if pattern in song_title:
                print(f"\nFound match for '{pattern}': '{link.get_text(strip=True)}'")
                parent = link.parent
                artist_link = parent.find(
                    "a", href=lambda h: h and "/artist/" in h and "/songs/" not in h
                ) if parent else None
                if artist_link:
                    print(f"  Artist: '{artist_link.get_text(strip=True)}'")
                else:
                    parent_text = parent.get_text(strip=True)
                    print(f"  Parent: '{parent_text}'")
                break

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
