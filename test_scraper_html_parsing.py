"""Test HTML parsing for iHeartRadio structure"""
from bs4 import BeautifulSoup

# Simulate the HTML structure based on what user described
html_examples = [
    # Example 1: Prince & the Revolution
    '''
    <div>
        <a href="/artist/prince-the-revolution-3403/songs/purple-rain-270063548">Purple Rain</a>
        <a href="/artist/prince-the-revolution-3403/">Prince & the Revolution</a>
    </div>
    ''',
    # Example 2: *NSYNC
    '''
    <div>
        <a href="/artist/nsync-31882/songs/this-i-promise-you-1800616">This I Promise You</a>
        <a href="/artist/nsync-31882/">*NSYNC</a>
    </div>
    ''',
    # Example 3: Complex collaboration (HUNTR/X, EJAE, etc.)
    '''
    <div>
        <a href="/artist/huntrx-ejae-audrey-nuna-rei-ami-kpop-demon-hunters-cast-47120415/songs/golden-337090518">Golden</a>
        HUNTR/X, EJAE, Audrey Nuna, REI AMI & KPop Demon Hunters Cast
    </div>
    ''',
    # Example 4: What if they're all in one line?
    '''
    <div>
        <a href="/artist/nsync-31882/songs/this-i-promise-you-1800616">This I Promise You</a> *NSYNC
    </div>
    ''',
]

print("Testing HTML parsing with different structures:")
print("=" * 80)

for i, html in enumerate(html_examples, 1):
    print(f"\nExample {i}:")
    soup = BeautifulSoup(html, "html.parser")

    # Find song link
    song_link = soup.find("a", href=lambda h: h and "/songs/" in h)
    if song_link:
        song_title = song_link.get_text(strip=True)
        href = song_link.get("href", "")
        print(f"  Song link: {href}")
        print(f"  Song title: '{song_title}'")

        # Try to find artist link (same method as scraper)
        parent = song_link.parent
        artist_link = parent.find(
            "a", href=lambda h: h and "/artist/" in h and "/songs/" not in h
        ) if parent else None

        if artist_link:
            artist_name = artist_link.get_text(strip=True)
            print(f"  Artist link: {artist_link.get('href')}")
            print(f"  Artist name (from link): '{artist_name}'")
        else:
            print(f"  No artist link found!")
            # Try getting all text from parent
            parent_text = parent.get_text(strip=True)
            print(f"  Parent text: '{parent_text}'")

print("\n" + "=" * 80)
print("Analysis:")
print("=" * 80)
print("""
If the artist link exists (Examples 1, 2):
  - Scraper should get the text from the link: "Prince & the Revolution", "*NSYNC"
  - This is CORRECT with separators

If NO artist link exists (Examples 3, 4):
  - Scraper falls back to URL slug
  - URL slug: "huntrx-ejae-audrey-nuna-rei-ami-kpop-demon-hunters-cast"
  - After dash→space: "Huntrx Ejae Audrey Nuna Rei Ami Kpop Demon Hunters Cast"
  - This is WRONG (lost all separators)
""")
