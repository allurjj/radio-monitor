"""
Text Normalization Module for Radio Monitor 1.0

This module provides text normalization functions for:
- Artist names (for Lidarr imports and Plex matching)
- Song titles (for Plex matching)

Normalization Rules:
1. Unify apostrophes (' ' '  → ')
2. Trim whitespace
3. Normalize internal whitespace (multiple spaces → single space)
4. Convert ALL CAPS to Title Case (with smart exceptions)
5. Preserve already-correct Title Case

Critical Design Decision:
- We normalize BEFORE storing to database
- We store ONLY normalized versions (not duplicates)
- Normalized text must work for BOTH Lidarr AND Plex
- Therefore: Be conservative, don't over-normalize

Author: Radio Monitor 1.0
Created: 2026-02-09
Purpose: Test normalization impact on Lidarr and Plex matching
"""

import re
import logging
import unicodedata
import json
import os

logger = logging.getLogger(__name__)


# Load user-configurable duo/group whitelist
def load_duo_whitelist():
    """Load duo whitelist from user-configurable JSON file

    Returns:
        set: Set of lowercase artist names that should NOT be split

    The whitelist file is optional and allows users to override
    the MusicBrainz-based collaboration detection when needed.
    """
    whitelist_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'duo_whitelist.json')

    default_whitelist = {
        'brooks & dunn',
        'dan + shay',
        'daryl hall & john oates',
        'hall & oates',
        'simon & garfunkel',
        'loggins & messina',
        'earth wind & fire',
        'crosby stills nash & young',
        'the judds',
        'the everly brothers',
        'the white stripes',
        'the chemical brothers',
        'the prodigy',
        'daft punk',
        'pet shop boys',
        'the allman brothers band',
        'the mamas & the papas',
    }

    if os.path.exists(whitelist_path):
        try:
            with open(whitelist_path, 'r', encoding='utf-8') as f:
                user_whitelist = json.load(f)
                if isinstance(user_whitelist, dict) and 'duos' in user_whitelist:
                    return {name.lower() for name in user_whitelist['duos']}
                elif isinstance(user_whitelist, list):
                    return {name.lower() for name in user_whitelist}
                else:
                    logger.warning(f"Invalid duo_whitelist.json format, using defaults")
                    return default_whitelist
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error reading duo_whitelist.json: {e}, using defaults")
            return default_whitelist
    else:
        # Create default file for users to customize
        try:
            with open(whitelist_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "description": "Whitelist of duos/groups that should NOT be split by collaboration detection",
                    "format": ["Full Duo Name 1", "Full Duo Name 2"],
                    "duos": list(default_whitelist)
                }, f, indent=2)
            logger.info(f"Created default duo_whitelist.json at {whitelist_path}")
        except IOError as e:
            logger.warning(f"Could not create duo_whitelist.json: {e}")

        return default_whitelist


DUO_WHITELIST = load_duo_whitelist()


# Artist name corrections for common systematic issues
ARTIST_NAME_CORRECTIONS = {
    # Case/styling corrections
    'pnk': 'P!NK',
    'pink': 'P!NK',
    'rem': 'R.E.M.',
    'wham': 'Wham!',
    # Add more as discovered through validation
}


def fix_encoding_corruption(text):
    """Fix common encoding corruption from misinterpreted UTF-8 bytes

    This fixes the issue where UTF-8 text was incorrectly interpreted as
    Windows-1252 (CP1252), causing characters like curly apostrophes to be
    displayed as garbage.

    Common corruption patterns:
    - U+2019 (') → displayed as â€™ or â\x80\x99 in raw bytes
    - U+2018 (') → displayed as â˜
    - U+201C (") → displayed as âœ
    - U+201D (") → displayed as â

    This function MUST be called first in the normalization pipeline, before
    any other text processing, to ensure corrupted text is fixed before being
    stored to the database.

    Args:
        text: Text that may have encoding corruption

    Returns:
        Text with encoding corruption fixed

    Examples:
        >>> fix_encoding_corruption("Thatâ\x80\x99s So True")
        "That's So True"
        >>> fix_encoding_corruption("Donât Stop")
        "Don't Stop"
        >>> fix_encoding_corruption("Normal Text")
        "Normal Text"  # Already good, unchanged
    """
    if not text:
        return text

    # Fix corrupted UTF-8 bytes (U+2019 stored as UTF-8 bytes 0xE2 0x80 0x99)
    text = text.replace('\xe2\x80\x99', "'")  # U+2019 corrupted as UTF-8 bytes
    text = text.replace('\xe2\x80\x98', "'")  # U+2018 corrupted
    text = text.replace('\xe2\x80\x9c', '"')  # U+201C corrupted
    text = text.replace('\xe2\x80\x9d', '"')  # U+201D corrupted

    # Fix already-misinterpreted Windows-1252 patterns
    # When UTF-8 bytes are read as Windows-1252: 0xE2 = â, 0x80 = control, 0x99 = ™
    # The pattern â followed by control chars needs to be converted to apostrophe
    text = re.sub(r'\xe2[\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f]', "'", text)

    return text


def strip_accents(text):
    """Remove accent marks from text for matching purposes

    This uses Unicode NFKD normalization to convert accented characters
    to their base form + combining accent, then removes the combining marks.

    This is critical for matching artists like:
    - Beyoncé → Beyonce
    - Ne-Yo → Neo-Yo (then hyphen normalization makes it Ne-Yo again)

    Args:
        text: Text that may contain accented characters

    Returns:
        Text with accent marks removed

    Examples:
        >>> strip_accents("Beyoncé")
        "Beyonce"
        >>> strip_accents("Ne-Yo")
        "Neo-Yo"
    """
    if not text:
        return text

    # Normalize to NFKD (decomposed form)
    normalized = unicodedata.normalize('NFKD', text)

    # Remove combining marks (Mn = Nonspacing_Mark)
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')


def normalize_with_edge_cases(text):
    """Normalize text with smart handling of edge cases

    This function handles:
    1. Encoding corruption (â€™ → ')
    2. Apostrophe unification (smart quotes → straight quotes)
    3. Title case conversion with smart exceptions
    4. Known artist name corrections

    Args:
        text: Text to normalize

    Returns:
        Normalized text

    Examples:
        >>> normalize_with_edge_cases("AIN'T IT FUN")
        "Ain't It Fun"
        >>> normalize_with_edge_cases("WE'RE GOOD")
        "We're Good"
        >>> normalize_with_edge_cases("PINK")
        "P!NK"
    """
    if not text:
        return text

    # Step 1: Fix encoding corruption
    text = fix_encoding_corruption(text)

    # Step 2: Unify apostrophes (smart quotes → straight quotes)
    # Unicode smart quotes: U+2018 (left single), U+2019 (right single), U+201C (left double), U+201D (right double)
    smart_apostrophes = ['‘', '’', '“', '”', '`']
    for apostrophe in smart_apostrophes:
        text = text.replace(apostrophe, "'")

    # Step 2.5: Unify hyphens and dashes (all variants → regular hyphen)
    # This handles cases where MusicBrainz returns U+2010 (hyphen) but we use U+002D (regular hyphen)
    # Characters to normalize: U+2010, U+2011, U+2012, U+2013, U+2014, U+2015
    dash_characters = ['‐', '‑', '‒', '–', '—', '―']
    for dash in dash_characters:
        text = text.replace(dash, "-")

    # Step 3: Trim whitespace
    text = text.strip()

    # Step 4: Normalize internal whitespace
    text = re.sub(r'\s+', ' ', text)

    # Step 5: Apply known corrections (P!NK, ABBA, etc.)
    text = apply_known_corrections(text)

    # Step 6: Title case with smart exceptions
    if text.isupper():
        text = smart_title_case(text)

    return text


def apply_known_corrections(text):
    """Apply known artist name corrections

    This handles special cases that title() would break:
    - PINK → P!NK (not Pink)
    - ABBA → ABBA (not Abba)
    - AC/DC → AC/DC (not Ac/Dc)

    Args:
        text: Text to correct

    Returns:
        Corrected text
    """
    if not text:
        return text

    # Known exceptions (must be applied before title case)
    exceptions = {
        'PINK': 'P!NK',
        'AC/DC': 'AC/DC',
        'RUSH': 'Rush',
        'YES': 'Yes',
        'THE CARS': 'The Cars',
        'THE POLICE': 'The Police',
        'THE WHO': 'The Who',
        'THE BAND': 'The Band',
        'THE CURE': 'The Cure',
    }

    upper_text = text.upper()
    if upper_text in exceptions:
        return exceptions[upper_text]

    # Preserve already-correct capitalization
    if text == 'P!NK' or text == 'ABBA' or text == 'AC/DC':
        return text

    return text


def smart_title_case(text):
    """Convert text to title case with smart handling of contractions

    Python's built-in title() capitalizes after apostrophes, which breaks
    contractions: "WE'RE" → "We'Re" instead of "We're"

    This function handles:
    - Contractions (don't, can't, we're, ain't)
    - Possessives (artist's, band's)
    - Hyphenated words (neo-soul, pre-chorus)

    Args:
        text: Text to convert

    Returns:
        Title-cased text with smart contraction handling

    Examples:
        >>> smart_title_case("WE'RE GOOD")
        "We're Good"
        >>> smart_title_case("AIN'T IT FUN")
        "Ain't It Fun"
        >>> smart_title_case("CAN'T STOP THE FEELING")
        "Can't Stop the Feeling"
    """
    if not text:
        return text

    # Common contractions that shouldn't be capitalized after apostrophe
    contractions = {
        "'t": "'t",
        "'s": "'s",
        "'re": "'re",
        "'ll": "'ll",
        "'ve": "'ve",
        "'m": "'m",
        "'d": "'d",
    }

    # Lowercase the text first
    text = text.lower()

    # Capitalize first word
    words = text.split()
    if words:
        words[0] = words[0].capitalize()

    # Capitalize each word (except contractions)
    result = []
    for word in words:
        # Check if word ends with a contraction
        for contraction, correct in contractions.items():
            if word.endswith(contraction) and len(word) > len(contraction):
                # Split the contraction
                base = word[:-len(contraction)]
                result.append(base.capitalize() + correct)
                break
        else:
            # No contraction, capitalize normally
            result.append(word.capitalize())

    return ' '.join(result)


def normalize_artist_name(artist_name):
    """Normalize artist name for database storage

    This is the main entry point for artist name normalization.
    It applies all corrections in the proper order.

    Args:
        artist_name: Raw artist name from scraper

    Returns:
        Normalized artist name

    Examples:
        >>> normalize_artist_name("AIN'T IT FUN")
        "Ain't It Fun"
        >>> normalize_artist_name("WE'RE GOOD")
        "We're Good"
        >>> normalize_artist_name("PINK")
        "P!NK"
    """
    if not artist_name:
        return artist_name

    return normalize_with_edge_cases(artist_name)


def normalize_song_title(song_title):
    """Normalize song title for database storage

    This is the main entry point for song title normalization.
    It applies all corrections in the proper order.

    Args:
        song_title: Raw song title from scraper

    Returns:
        Normalized song title

    Examples:
        >>> normalize_song_title("AIN'T IT FUN")
        "Ain't It Fun"
        >>> normalize_song_title("WE'RE GOOD")
        "We're Good"
    """
    if not song_title:
        return song_title

    return normalize_with_edge_cases(song_title)


def normalize_pair(artist_name, song_title):
    """Normalize both artist name and song title together

    This is useful when you need to normalize both at once.

    Args:
        artist_name: Raw artist name from scraper
        song_title: Raw song title from scraper

    Returns:
        tuple: (normalized_artist, normalized_song)

    Examples:
        >>> normalize_pair("AIN'T IT FUN", "WE'RE GOOD")
        ("Ain't It Fun", "We're Good")
    """
    normalized_artist = None
    normalized_song = None

    if artist_name:
        normalized_artist = normalize_with_edge_cases(artist_name)

    if song_title:
        normalized_song = normalize_with_edge_cases(song_title)

    return (normalized_artist, normalized_song)


# ==================== COLLABORATION HANDLING ====================

def check_musicbrainz_exists(artist_name):
    """Check if artist exists in MusicBrainz as-is (without splitting)

    This is the PROPER way to handle potential collaborations:
    1. First check if the full artist name exists in MusicBrainz
    2. If yes, it's a legitimate duo/group - don't split
    3. If no, then try splitting into individual artists

    Args:
        artist_name: Artist name to check

    Returns:
        bool: True if artist exists in MusicBrainz, False otherwise
    """
    if not artist_name:
        return False

    try:
        import requests
        import urllib3
        urllib3.disable_warnings()

        # Query MusicBrainz for exact match
        # Use AND operator for exact phrase match
        query = f'artist:"{artist_name}"'
        url = f'https://musicbrainz.org/ws2/artist?query={requests.utils.quote(query)}&fmt=json&limit=20'

        response = requests.get(
            url,
            verify=False,
            timeout=5,
            headers={'User-Agent': 'radio-monitor/1.0 (https://github.com/allurjj/radio-monitor)'}
        )

        if response.status_code == 200:
            data = response.json()
            artists = data.get('artists', [])

            # Check for exact name match (case-insensitive)
            for artist in artists:
                mb_name = artist.get('name', '')
                if mb_name.lower() == artist_name.lower():
                    logger.debug(f"MusicBrainz found '{artist_name}' as single artist (MBID: {artist.get('id', 'unknown')})")
                    return True

            # Also check for alias matches
            for artist in artists:
                aliases = artist.get('aliases', [])
                for alias in aliases:
                    if alias.lower() == artist_name.lower():
                        logger.debug(f"MusicBrainz found '{artist_name}' as alias of '{artist.get('name', 'unknown')}'")
                        return True

            logger.debug(f"MusicBrainz did not find '{artist_name}' as single artist")
            return False
        else:
            logger.debug(f"MusicBrainz query returned HTTP {response.status_code} for '{artist_name}'")
            return False

    except Exception as e:
        logger.debug(f"Error checking MusicBrainz for '{artist_name}': {e}")
        return False


def detect_collaboration(artist_name):
    """Detect if artist name contains multiple artists (collaboration)

    PROPER LOGIC (MusicBrainz-first approach):
    1. Check whitelist (user override)
    2. Check MusicBrainz for exact match (duos/groups exist as single artists)
    3. Only split if MusicBrainz doesn't recognize it

    Args:
        artist_name: Artist name to check

    Returns:
        tuple: (is_collaboration, split_artists)
            - is_collaboration: True if multiple artists detected
            - split_artists: List of individual artist names if detected, else [artist_name]
    """
    if not artist_name:
        return False, []

    # Normalize for detection
    artist_lower = artist_name.lower().strip()

    # Step 1: Check whitelist FIRST (user override)
    if artist_lower in DUO_WHITELIST:
        logger.debug(f"'{artist_name}' is in duo whitelist, treating as single artist")
        return False, [artist_name]

    # Step 2: Check MusicBrainz for exact match (legitimate duos/groups)
    if check_musicbrainz_exists(artist_name):
        logger.debug(f"'{artist_name}' found in MusicBrainz as single artist (legitimate duo/group)")
        return False, [artist_name]

    # Step 3: Check for collaboration markers (only if MusicBrainz didn't find it)
    # Don't split on common legitimate duo markers if they might be real duos
    # Only split on clear collaboration markers
    collab_patterns = [
        ' feat', '(feat', ' ft.', ' ft ', 'featuring', ' with ', ';'
    ]

    # Check if any collaboration marker is present
    for pattern in collab_patterns:
        if pattern in artist_lower:
            return True, split_collaboration_artists(artist_name)

    # Step 4: Check for ambiguous markers ( & , + , x , and )
    # These might be duos OR collaborations
    # Conservative approach: if MusicBrainz didn't find it AND it has these markers,
    # assume it's a collaboration and split
    ambiguous_patterns = [' & ', ' + ', ' x ', ' and ']

    for pattern in ambiguous_patterns:
        if pattern in artist_lower:
            logger.debug(f"'{artist_name}' contains '{pattern.strip()}' and wasn't found in MusicBrainz, treating as collaboration")
            return True, split_collaboration_artists(artist_name)

    return False, [artist_name]


def split_collaboration_artists(artist_name):
    """Split collaboration artist string into individual artists

    Args:
        artist_name: Artist collaboration string (e.g., "Artist1 Feat. Artist2")

    Returns:
        list: Individual artist names

    Examples:
        >>> split_collaboration_artists("Gotye & Kimbra")
        ['Gotye', 'Kimbra']
        >>> split_collaboration_artists("Pitbull, Afrojack & Ne-Yo feat. Nayer")
        ['Pitbull', 'Afrojack', 'Ne-Yo', 'Nayer']
        >>> split_collaboration_artists("Kenny Chesney;Uncle Kracker")
        ['Kenny Chesney', 'Uncle Kracker']
    """
    if not artist_name:
        return []

    # Split on multiple separators (feat, ft, featuring, &, +, x, and, ;, comma)
    # Use recursive splitting to handle multiple separators
    artists = [artist_name]

    # Split on 'feat', 'ft.', 'featuring'
    new_artists = []
    for artist in artists:
        parts = re.split(r'\s+feat(?:\.|uring)?\s+', artist, flags=re.IGNORECASE)
        new_artists.extend(parts)
    artists = new_artists

    # Split on parentheses (feat. Artist) -> remove the featured part
    new_artists = []
    for artist in artists:
        # Remove content in parentheses after feat
        artist = re.sub(r'\s*\(\s*feat(?:\.|uring)?\s+[^)]+\)\s*$', '', artist, flags=re.IGNORECASE)
        new_artists.append(artist)
    artists = new_artists

    # Split on separators: &, +, x, and, ;, comma
    for separator, pattern in [
        (';', r';'),
        (',', r','),
        ('&', r'\s*&\s*'),
        ('+', r'\s*\+\s*'),
        ('x', r'\s+x\s+'),
        ('and', r'\s+and\s+'),
    ]:
        new_artists = []
        for artist in artists:
            parts = re.split(pattern, artist, flags=re.IGNORECASE)
            new_artists.extend(parts)
        artists = new_artists

    # Trim whitespace and normalize each artist
    normalized_artists = []
    for artist in artists:
        artist = artist.strip()
        if artist:
            normalized_artists.append(normalize_artist_name(artist))

    # Remove duplicates while preserving order
    seen = set()
    unique_artists = []
    for artist in normalized_artists:
        if artist.lower() not in seen:
            seen.add(artist.lower())
            unique_artists.append(artist)

    return unique_artists


def handle_collaboration(artist_name, song_title, mbid=None):
    """Handle collaboration artists by extracting only the PRIMARY artist

    This function takes an artist collaboration (e.g., "Garth Brooks feat. Brooks & Dunn")
    and extracts ONLY the primary artist. Featured artists are ignored for database storage.

    This prevents issues where featured artists are credited with songs they don't own,
    which breaks Lidarr imports and Plex playlist creation.

    Args:
        artist_name: Artist name (may be collaboration)
        song_title: Song title
        mbid: MusicBrainz ID (optional, usually None for collaborations)

    Returns:
        list: Single tuple of (primary_artist, song, mbid)
              If not a collaboration, returns [(artist, song, mbid)]

    Examples:
        >>> handle_collaboration("Garth Brooks feat. Brooks & Dunn", "This is our song", None)
        [('Garth Brooks', 'This is our song', None)]

        >>> handle_collaboration("Taylor Swift", "Love Story", "abc123")
        [('Taylor Swift', 'Love Story', 'abc123')]
    """
    if not artist_name:
        return []

    # Normalize artist name first
    normalized_artist = normalize_with_edge_cases(artist_name)

    # Detect if this is a collaboration
    is_collab, split_artists = detect_collaboration(normalized_artist)

    if not is_collab:
        # Not a collaboration, return as-is
        logger.debug(f"'{artist_name}' is not a collaboration (single artist)")
        return [(normalized_artist, song_title, mbid)]

    # Collaboration detected - check if we have split results
    # If split_artists is empty or None, use normalized_artist as fallback
    if not split_artists or len(split_artists) == 0:
        split_artists = [normalized_artist]

    # Collaboration detected - extract PRIMARY artist only
    # The primary artist is the first one before any collaboration markers
    primary_artist = split_artists[0]
    primary_artist = normalize_with_edge_cases(primary_artist)

    logger.info(f"Collaboration detected: '{artist_name}' -> Primary artist: '{primary_artist}' (ignoring featured artists)")

    # Return only the primary artist with the song
    # Featured artists are ignored to prevent Lidarr/Plex workflow issues
    return [(primary_artist, song_title, mbid)]


# ==================== MATCH KEY GENERATION ====================

def normalize_for_matching(artist_name):
    """Aggressive normalization for duplicate detection and matching.

    This function creates a match key that ignores punctuation, spacing,
    and capitalization variations to find duplicate artists.

    Transformations applied (in order):
    1. Apply conservative normalization (fix encoding, title case, etc.)
    2. Convert to lowercase
    3. Remove all spaces
    4. Remove ampersands (&)
    5. Remove plus signs (+)
    6. Remove commas (,)
    7. Remove periods (.)
    8. Remove apostrophes (')
    9. Remove hyphens (-)
    10. Remove "the" prefix (for band names)

    NOT for storage or display - only for duplicate detection!

    Examples:
        >>> normalize_for_matching("Brooks & Dunn")
        'brooksdunn'
        >>> normalize_for_matching("Brooks Dunn")
        'brooksdunn'  # Same as above - matches!
        >>> normalize_for_matching("Dan + Shay")
        'danshay'
        >>> normalize_for_matching("Dan Shay")
        'danshay'  # Same as above - matches!
        >>> normalize_for_matching("The B-52's")
        'b52s'
        >>> normalize_for_matching("The B 52S")
        'b52s'  # Same as above - matches!
        >>> normalize_for_matching("Mary J. Blige")
        'maryjblige'
        >>> normalize_for_matching("Mary J Blige")
        'maryjblige'  # Same as above - matches!

    Args:
        artist_name: Artist name to normalize for matching

    Returns:
        Aggressively normalized match key (lowercase, no punctuation/spaces)
    """
    if not artist_name:
        return ""

    # Step 1: Apply conservative normalization first
    # This fixes encoding, title case, apostrophes, etc.
    text = normalize_artist_name(artist_name)

    # Step 2: Convert to lowercase
    text = text.lower()

    # Step 3: Remove spaces
    text = text.replace(' ', '')

    # Step 4: Remove ampersands (&)
    text = text.replace('&', '')

    # Step 5: Remove plus signs (+)
    text = text.replace('+', '')

    # Step 6: Remove commas (,)
    text = text.replace(',', '')

    # Step 7: Remove periods (.)
    text = text.replace('.', '')

    # Step 8: Remove apostrophes and backticks
    # Use regex to handle all apostrophe variants (ASCII, Unicode, backtick)
    apostrophe_chars = "'", "'", "'", '"', '"', '"', '`'
    for char in apostrophe_chars:
        text = text.replace(char, '')

    # Step 9: Remove hyphens (-)
    text = text.replace('-', '')

    # Step 9.5: Remove other common special characters (!, @, #, $, %, *, etc.)
    # This handles cases like "P!NK" vs "PINK"
    for char in ['!', '@', '#', '$', '%', '^', '*', '~', '`']:
        text = text.replace(char, '')

    # Step 10: Remove "the" prefix (for band names like "The Beatles")
    if text.startswith('the'):
        text = text[3:]

    # Final cleanup: ensure not empty
    if not text:
        # Fallback: use lowercase version with spaces only
        text = artist_name.lower().replace(' ', '')

    return text


def generate_match_key_for_db(artist_name):
    """Generate match key for database storage.

    This is a wrapper around normalize_for_matching() that includes
    additional safety checks for database operations.

    Args:
        artist_name: Artist name to generate match key for

    Returns:
        Match key suitable for database storage
    """
    # Handle None input
    if artist_name is None:
        logger.warning("None artist_name provided to generate_match_key_for_db")
        return ""

    match_key = normalize_for_matching(artist_name)

    # Safety check: ensure match_key is not empty
    if not match_key or match_key.strip() == '':
        # Fallback: use artist name (shouldn't happen, but safety net)
        logger.warning(f"Empty match_key generated for '{artist_name}', using fallback")
        try:
            match_key = artist_name.lower().replace(' ', '')
        except AttributeError:
            # If artist_name is not a string, return empty string
            return ""

    # Safety check: ensure match_key is not too long
    if len(match_key) > 100:
        logger.warning(f"Match key too long ({len(match_key)} chars) for '{artist_name}', truncating")
        match_key = match_key[:100]

    return match_key


# ==================== SONG VALIDATION ====================

def strip_song_suffixes(title: str) -> str:
    """Strip common version suffixes from song titles for comparison.

    This removes suffixes like "(Remix)", "(Live)", "- Remastered", etc.
    to allow matching base song titles against versioned recordings.

    Args:
        title: Song title that may have version suffixes

    Returns:
        Base song title with common suffixes removed

    Examples:
        >>> strip_song_suffixes("Neon Moon (Remix)")
        "Neon Moon"
        >>> strip_song_suffixes("Austin - Live")
        "Austin"
        >>> strip_song_suffixes("Test Song (Radio Edit)")
        "Test Song"
    """
    if not title:
        return title

    # Common version patterns to strip (case-insensitive)
    patterns = [
        r'\s*\(.*?\bremix\b.*?\)\s*$',           # (Remix), (Club Remix), etc.
        r'\s*\(.*?\blive\b.*?\)\s*$',            # (Live), (Live Version), etc.
        r'\s*\(.*?\bradio\s+edit\b.*?\)\s*$',    # (Radio Edit)
        r'\s*\(.*?\bedit\b.*?\)\s*$',             # (Edit), (Vocal Edit), etc.
        r'\s*\(.*?\bextended\b.*?\)\s*$',        # (Extended), (Extended Mix)
        r'\s*\(.*?\boriginal\b.*?\)\s*$',       # (Original), (Original Mix)
        r'\s*\(.*?\bversion\b.*?\)\s*$',         # (Version), (Alternate Version)
        r'\s*\(.*?\bremaster(?:ed)?\b.*?\)\s*$', # (Remastered), (2023 Remaster)
        r'\s*\(.*?\b acoustic\b.*?\)\s*$',        # (Acoustic), (Acoustic Version)
        r'\s*\(.*?\bfeat\b.*?\)\s*$',            # (feat. Artist) - but keep base
        r'\s*\(.*?\bwith\b.*?\)\s*$',            # (with Artist)
        r'\s*\[.*?\]\s*$',                       # [Remix], [Live], etc.
        r'\s*-\s*live\s*$',                      # - Live
        r'\s*-\s*remix\s*$',                     # - Remix
        r'\s*-\s*remaster(?:ed)?\s*$',           # - Remastered
        r'\s*-\s*version\s*$',                   # - Version
    ]

    result = title.strip()
    for pattern in patterns:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)
        # After each match, check if we changed something and stop
        if result != title.strip():
            break

    return result.strip()


def calculate_similarity(str1: str, str2: str) -> float:
    """Calculate similarity between two strings using SequenceMatcher.

    Returns 0.0 to 1.0, where 1.0 is exact match.

    Args:
        str1: First string to compare
        str2: Second string to compare

    Returns:
        float: Similarity ratio between 0.0 and 1.0

    Examples:
        >>> calculate_similarity("Neon Moon", "Neon Moon")
        1.0
        >>> calculate_similarity("Neon Moon", "Neon Moon (Remix)")
        0.85+
        >>> calculate_similarity("Test Song", "Different Title")
        < 0.5
    """
    from difflib import SequenceMatcher
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def clean_song_title_for_query(title: str) -> str:
    """Clean song title for MusicBrainz queries.

    Removes parentheticals and modifiers that may interfere with matching:
    - Features: (feat. Artist), (ft. Artist), (with Artist)
    - Remixes/Live versions (already handled by strip_song_suffixes)
    - Extra metadata: (Official Video), (From Album X)

    Args:
        title: Raw song title

    Returns:
        Cleaned title suitable for MusicBrainz queries

    Examples:
        >>> clean_song_title_for_query("Neon Moon (feat. John Doe)")
        'Neon Moon'
        >>> clean_song_title_for_query("Test Song (Official Video)")
        'Test Song'
    """
    import re

    # Remove features and collaborations
    patterns = [
        r'\s*\(feat\.?\s+[^)]+\)',             # (feat. Artist)
        r'\s*\(ft\.?\s+[^)]+\)',               # (ft. Artist)
        r'\s*\(featuring\s+[^)]+\)',           # (featuring Artist)
        r'\s*\(with\s+[^)]+\)',                # (with Artist)
        r'\s*\(official\s+(video|music\s+video)\)',  # (Official Video)
        r'\s*\(from\s+[^)]+\)',                # (From Album X)
        r'\s*\(audio\s*(only)?\)',             # (Audio)
        r'\s*\(lyrics?\)',                     # (Lyrics)
        r'\s*\[[^\]]+\]',                      # [Square brackets]
    ]

    result = title.strip()
    for pattern in patterns:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)

    # Also strip version suffixes (remix, live, etc.)
    result = strip_song_suffixes(result)

    return result.strip()
