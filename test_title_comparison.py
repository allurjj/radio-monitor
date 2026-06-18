"""Test title comparison for Gotye - Somebody That I Used To Know"""
import unicodedata
import re

mbid = "6f6fd596-76e0-4b82-aa37-f558ac2d337b"
song_title = "Somebody That I Used To Know"

# Simulate the validation process
def clean_song_title_for_query(title: str) -> str:
    """Clean song title for MusicBrainz queries"""
    if not title:
        return ""

    cleaned = title.strip()

    # Remove parentheticals: (Live), (Remix), etc.
    cleaned = re.sub(r'\s*\(.*?\)\s*', ' ', cleaned)

    # Remove brackets: [Official Video], [Lyrics], etc.
    cleaned = re.sub(r'\s*\[.*?\]\s*', ' ', cleaned)

    # Remove "feat." and variations (keep main artist only)
    cleaned = re.sub(r'\s+feat\.?\s.*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+featuring\s.*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+ft\.?\s.*$', '', cleaned, flags=re.IGNORECASE)

    # Remove collaboration separators after main title
    cleaned = re.sub(r'\s*&\s.*$', '', cleaned)
    cleaned = re.sub(r'\s*\+\s.*$', '', cleaned)
    cleaned = re.sub(r'\s*x\s.*$', '', cleaned, flags=re.IGNORECASE)

    return cleaned.strip()

def is_recording_match(recording_title: str, expected_title: str) -> bool:
    """Check if a MusicBrainz recording title matches our song title"""

    # Clean both titles the same way for fair comparison
    recording_title = clean_song_title_for_query(recording_title)
    expected_title = clean_song_title_for_query(expected_title)

    # Normalize Unicode apostrophes to ASCII apostrophe
    recording_title = unicodedata.normalize('NFKC', recording_title)
    recording_title = re.sub(r"[''''']]", "'", recording_title)
    recording_title = re.sub(r'[\x00-\x1F\x7F-\x9F]', "'", recording_title)

    expected_title = unicodedata.normalize('NFKC', expected_title)
    expected_title = re.sub(r"[''''']]", "'", expected_title)
    expected_title = re.sub(r'[\x00-\x1F\x7F-\x9F]', "'", expected_title)

    # Case-insensitive title comparison
    if recording_title.lower() != expected_title.lower():
        return False

    return True

# Test cases from MusicBrainz
test_cases = [
    "Somebody That I Used to Know",  # Note: lowercase "to"!
    "Somebody That I Used To Know",
]

print("Title Comparison Tests:")
print(f"Expected: '{song_title}'")
print()

for test_title in test_cases:
    result = is_recording_match(test_title, song_title)
    print(f"Test: '{test_title}'")
    print(f"  Cleaned: '{clean_song_title_for_query(test_title)}'")
    print(f"  Match: {result}")
    print()

# Test with cleaned versions
print("=" * 80)
print("Detailed comparison:")
print("=" * 80)

expected_clean = clean_song_title_for_query(song_title)
expected_normalized = unicodedata.normalize('NFKC', expected_clean)

for test_title in test_cases:
    test_clean = clean_song_title_for_query(test_title)
    test_normalized = unicodedata.normalize('NFKC', test_clean)

    print(f"Expected: '{expected_normalized}' (lower: '{expected_normalized.lower()}')")
    print(f"Test:     '{test_normalized}' (lower: '{test_normalized.lower()}')")
    print(f"Equal:    {expected_normalized.lower() == test_normalized.lower()}")
    print()
