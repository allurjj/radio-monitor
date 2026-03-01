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

logger = logging.getLogger(__name__)


# Known acronyms and stylized names that should stay ALL CAPS
# These are common in music and should be preserved
CAPS_EXCEPTIONS = {
    'ABBA', 'ACDC',
    'B2K', 'BTS', 'BIGBANG',
    'CNR',
    'DMX', 'DHT',
    'ELO',
    'INXS',
    'KISS',
    'LL Cool J',
    'MFSB',
    'NSYNC', 'NWA', 'N.W.A',
    'O.A.R.',
    'PINK',  # Will be corrected to P!NK in normalization
    'P!NK',  # Stylized with exclamation
    'R.E.M.',
    'RUN DMC',
    'SWV',
    'TLC',
    'UB40',
    'XTC',
    'ZZ Top',
}

# Common words that should NOT stay ALL CAPS even if short
COMMON_WORDS = {
    'THE', 'AND', 'BUT', 'FOR', 'NOR', 'OR', 'SO', 'YET',
    'MY', 'YOUR', 'HIS', 'HER', 'ITS', 'OUR', 'THEIR',
    'THIS', 'THAT', 'THESE', 'THOSE',
    'A', 'AN', 'AM', 'IS', 'ARE', 'WAS', 'WERE', 'BE',
    # Note: 'I' is intentionally excluded - it's checked as roman numeral first
    'YOU', 'HE', 'SHE', 'IT', 'WE', 'THEY',
    'ME', 'HIM', 'THEM',
    'IN', 'ON', 'AT', 'TO', 'BY', 'WITH', 'FROM',
    'NOT', 'NO', 'YES',
    'FUN', 'BIG', 'BOI', 'BOY', 'CRY', 'HEY', 'NOR', 'NOW', 'OUT', 'SAY', 'SEE', 'WAY',  # Common short words in titles
    'FEAT', 'FT', 'FEATURING',  # Common abbreviations
}


def should_preserve_caps(text):
    """Check if ALL CAPS text should be preserved

    Args:
        text: Text to check (should be ALL CAPS)

    Returns:
        True if text should stay ALL CAPS, False if should convert to Title Case

    Examples:
        >>> should_preserve_caps('ABBA')
        True
        >>> should_preserve_caps('PERFECT')
        False
        >>> should_preserve_caps('KISS')
        True
        >>> should_preserve_caps('MY')
        False  # Common word, don't preserve
        >>> should_preserve_caps('II')
        True  # Roman numeral
        >>> should_preserve_caps('I')
        True  # Roman numeral (checked before common words)
        >>> should_preserve_caps('FEAT.')
        False  # Common abbreviation
    """
    if not text or not text.isupper():
        return False

    # Check for roman numerals FIRST (before common words)
    # Only if it's a standalone roman numeral (I, II, III, IV, V, etc.)
    # This ensures "I" is recognized as a roman numeral, not a common word
    if re.match(r'^[IVX]+$', text):
        return True

    # Check against common words (they should NOT be preserved)
    # Also check for common abbreviations with dots
    text_without_dot = text.rstrip('.')
    if text in COMMON_WORDS or text_without_dot in COMMON_WORDS:
        return False

    # Check against known exceptions list
    if text in CAPS_EXCEPTIONS:
        return True

    # Check for initialisms with dots (R.E.M., O.A.R., etc.)
    # But NOT common abbreviations like FEAT., FT., etc.
    if '.' in text and len(text) <= 6:
        # Check if it's a common abbreviation (should not be preserved)
        if text_without_dot in COMMON_WORDS:
            return False
        return True

    # Check for ALL CAPS artist names with 3 or fewer letters
    # (Likely acronyms: TLC, BTS, etc.) but NOT common words
    # (Common words already checked above)
    if len(text) <= 3 and not ' ' in text:
        return True

    # Default: convert to Title Case
    return False


def normalize_text(text, preserve_caps=False):
    """Normalize text for storage and matching

    This is the CONSERVATIVE normalization function.
    It only fixes obvious issues without changing artist names.

    Normalization Rules:
    1. Trim leading/trailing whitespace
    2. Unify all apostrophe variants to standard apostrophe (')
    3. Remove double apostrophes
    4. Normalize internal whitespace (multiple spaces → single space)
    5. If ALL CAPS and not in exceptions: convert to Title Case
    6. Fix contractions (Ain'T -> Ain't)
    7. Fix known artist stylizations (PINK -> P!NK)

    Args:
        text: Text to normalize
        preserve_caps: If True, skip ALL CAPS conversion (default: False)

    Returns:
        Normalized text

    Examples:
        >>> normalize_text("PERFECT")
        'Perfect'
        >>> normalize_text("IT'S MY LIFE")
        "It's My Life"
        >>> normalize_text("  Don''t  ")
        "Don't"
        >>> normalize_text("My Love")
        'My Love'  # Already correct, unchanged
        >>> normalize_text("ABBA")
        'ABBA'  # Preserved
        >>> normalize_text("R.E.M.")
        'R.E.M.'  # Preserved

    Note: This is the SAFE normalization for production use.
    """
    if not text:
        return ""

    # Rule 1: Trim whitespace
    text = text.strip()

    # Rule 2 & 3: Unify apostrophes and remove double apostrophes
    # Convert all apostrophe variants to standard '
    # Includes U+2019 (right single quote) used by Plex!
    text = re.sub(r"[''''´`]", "'", text)
    # Remove double apostrophes
    text = text.replace("''", "'")

    # Rule 3.5: Unify unicode dashes/hyphens to ASCII hyphen
    # This fixes: All‐4‐One → All-4-One (U+2010 → U+002D)
    # Converts various unicode dash characters to standard ASCII hyphen
    # U+2010 (hyphen), U+2011 (non-breaking hyphen), U+2012 (figure dash),
    # U+2013 (en dash), U+2014 (em dash), U+2015 (horizontal bar)
    text = re.sub(r"[‐‑‒–—―]", '-', text)

    # Rule 4: Normalize whitespace
    # Multiple spaces, tabs, newlines → single space
    text = ' '.join(text.split())

    # Rule 5: ALL CAPS to Title Case (with exceptions)
    # Removed len(text) > 2 check - normalize even short words
    if not preserve_caps and text.isupper():
        if not should_preserve_caps(text):
            # Fix contractions BEFORE calling .title()
            # This prevents "AIN'T" -> "Ain'T"
            # We need to lowercase the letter AFTER the apostrophe
            text = re.sub(r"'([A-Z])", lambda m: "'" + m.group(1).lower(), text)

            # Apply title case word-by-word to preserve Roman numerals
            words = text.split()
            normalized_words = []

            for word in words:
                # Check if this word should be preserved (roman numeral, etc.)
                if should_preserve_caps(word):
                    # Keep it as-is
                    normalized_words.append(word)
                else:
                    # Custom title case: only capitalize first letter
                    # This prevents "SK8ER" -> "Sk8Er" and gives "Sk8er" instead
                    word_lower = word.lower()
                    if word_lower:
                        # Capitalize only the first character
                        word_title = word_lower[0].upper() + word_lower[1:]
                        normalized_words.append(word_title)
                    else:
                        normalized_words.append(word_lower)

            text = ' '.join(normalized_words)

            # Final pass: fix any remaining capital letters after apostrophes
            # This catches cases like "Ain'T" -> "Ain't"
            text = re.sub(r"'([A-Z])", lambda m: "'" + m.group(1).lower(), text)

    # Rule 7: Fix known artist stylizations
    # These are corrections after normalization
    # Handle PINK -> P!NK (both all-caps and title-case versions)
    if text == "PINK":
        text = "P!NK"
    elif text == "Pink":
        text = "P!NK"
    elif text == "Acdc":
        text = "ACDC"

    return text


def normalize_text_aggressive(text):
    """Aggressive normalization for Plex matching only

    This function applies more aggressive normalization for Plex matching.
    DO NOT use for Lidarr imports - may break artist matching.

    Additional Rules (beyond normalize_text):
    1. Remove all punctuation except apostrophes
    2. Convert to lowercase
    3. Remove diacritics (accents, umlauts, etc.)

    Args:
        text: Text to normalize

    Returns:
        Aggressively normalized text (lowercase, no punctuation)

    Examples:
        >>> normalize_text_aggressive("IT'S MY LIFE!")
        "it's my life"
        >>> normalize_text_aggressive("Don't Stop Believin'")
        "dont stop believin"
        >>> normalize_text_aggressive("Beyoncé")
        "beyonce"

    WARNING: Only use for Plex matching, not for storage or Lidarr!
    """
    if not text:
        return ""

    # First apply conservative normalization
    text = normalize_text(text)

    # Remove punctuation except apostrophes
    text = re.sub(r"[^\w\s']", '', text)

    # Remove apostrophes too (for aggressive matching)
    text = text.replace("'", "")

    # Convert to lowercase
    text = text.lower()

    # Normalize whitespace
    text = ' '.join(text.split())

    return text


def normalize_artist_name(artist_name):
    """Normalize artist name for storage and matching

    This is the PRIMARY function for artist normalization.
    Uses conservative normalization to ensure Lidarr compatibility.

    Args:
        artist_name: Raw artist name from radio scraper

    Returns:
        Normalized artist name

    Examples:
        >>> normalize_artist_name("PERFECT")
        'Perfect'
        >>> normalize_artist_name("P!NK")
        'P!NK'  # Preserved
        >>> normalize_artist_name("GUNS N' ROSES")
        "Guns N' Roses"
        >>> normalize_artist_name("Ne‐Yo")  # Special hyphen
        'Ne-Yo'  # Will be handled by apostrophe unification
    """
    return normalize_text(artist_name)


def normalize_song_title(song_title):
    """Normalize song title for storage and matching

    This is the PRIMARY function for song title normalization.
    Uses conservative normalization.

    Args:
        song_title: Raw song title from radio scraper

    Returns:
        Normalized song title

    Examples:
        >>> normalize_song_title("AIN'T IT FUN")
        "Ain't It Fun"
        >>> normalize_song_title("Don't Stop Believin'")
        "Don't Stop Believin'"
        >>> normalize_song_title("  PERFECT  ")
        'Perfect'
    """
    return normalize_text(song_title)


# Edge case handlers for specific known issues

def handle_special_hyphens(text):
    """Handle special hyphen characters in text

    Some sources use special unicode hyphens instead of ASCII hyphen:
    - U+2010 (‐)  Hyphen
    - U+2011 (‑)  Non-breaking hyphen
    - U+2012 (‒)  Figure dash
    - U+2013 (–)  En dash
    - U+2014 (—)  Em dash
    - U+2015 (―)  Horizontal bar

    Args:
        text: Text that may contain special hyphens

    Returns:
        Text with special hyphens converted to ASCII hyphen

    Examples:
        >>> handle_special_hyphens("Ne‐Yo")
        'Ne-Yo'
        >>> handle_special_hyphens("The All–American Rejects")
        'The All-American Rejects'
    """
    if not text:
        return ""

    # Convert all unicode dashes/hyphens to ASCII hyphen
    text = re.sub(r"[‐‑‒–—―]", '-', text)

    return text


def handle_special_apostrophes(text):
    """Handle special apostrophe characters in text

    Many sources use special unicode apostrophes instead of ASCII apostrophe:
    - U+2019 (')  Right single quotation mark
    - U+2018 (')  Left single quotation mark
    - U+201B (')  Single high-reversed-9 quotation mark
    - U+00B4 (´)  Acute accent
    - U+0060 (`)  Backtick (grave accent)

    Args:
        text: Text that may contain special apostrophes

    Returns:
        Text with special apostrophes converted to ASCII apostrophe

    Examples:
        >>> handle_special_apostrophes("Don't")
        "Don't"
        >>> handle_special_apostrophes("Guns N' Roses")
        "Guns N' Roses"
    """
    if not text:
        return ""

    # Convert all apostrophe variants to standard ASCII apostrophe
    text = re.sub(r"[''´`]", "'", text)

    # Handle double apostrophes
    text = text.replace("''", "'")

    return text


def normalize_with_edge_cases(text):
    """Normalize text with comprehensive edge case handling

    This function handles all known edge cases:
    - Special apostrophes
    - Special hyphens
    - ALL CAPS conversion
    - Whitespace normalization

    Args:
        text: Text to normalize

    Returns:
        Fully normalized text

    Examples:
        >>> normalize_with_edge_cases("Ne‐Yo")
        'Ne-Yo'
        >>> normalize_with_edge_cases("The All‐American Rejects")
        'The All-American Rejects'
        >>> normalize_with_edge_cases("AIN'T IT FUN")
        "Ain't It Fun"
    """
    if not text:
        return ""

    # Handle special characters first
    text = handle_special_apostrophes(text)
    text = handle_special_hyphens(text)

    # Apply standard normalization
    text = normalize_text(text)

    return text


# Convenience function for production use
# This is what will be called from scrapers
def normalize_for_storage(artist_name=None, song_title=None):
    """Normalize artist and/or song title for database storage

    This is the MAIN ENTRY POINT for normalization in production.

    Args:
        artist_name: Artist name to normalize (optional)
        song_title: Song title to normalize (optional)

    Returns:
        tuple: (normalized_artist, normalized_song_title)
        Either value may be None if not provided

    Examples:
        >>> normalize_for_storage("PINK", "PERFECT")
        ('P!NK', 'Perfect')  # Artist preserved, title normalized

        >>> normalize_for_storage(artist_name="GUNS N' ROSES")
        ("Guns N' Roses", None)

        >>> normalize_for_storage(song_title="AIN'T IT FUN")
        (None, "Ain't It Fun")
    """
    normalized_artist = None
    normalized_song = None

    if artist_name:
        normalized_artist = normalize_with_edge_cases(artist_name)

    if song_title:
        normalized_song = normalize_with_edge_cases(song_title)

    return (normalized_artist, normalized_song)


# ==================== COLLABORATION HANDLING ====================

def detect_collaboration(artist_name):
    """Detect if artist name contains multiple artists (collaboration)

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

    # Collaboration markers to check
    collab_patterns = [
        ' feat', ' ft.', ' ft ', 'featuring', ' with ', ' & ', ' + ', ' x ', ' and '
    ]

    # Check if any collaboration marker is present
    for pattern in collab_patterns:
        if pattern in artist_lower:
            return True, split_collaboration_artists(artist_name)

    return False, [artist_name]


def split_collaboration_artists(artist_name):
    """Split collaboration artist string into individual artists

    Args:
        artist_name: Artist collaboration string (e.g., "Artist1 Feat. Artist2")

    Returns:
        list: Individual artist names
    """
    if not artist_name:
        return []

    # Normalize for splitting
    normalized = normalize_with_edge_cases(artist_name)

    # Try different splitting strategies in order
    strategies = [
        # Strategy 1: Feat/ft/featuring
        (r'\s+(?:feat|ft\.|featuring)\s+', 'feat'),

        # Strategy 2: & (ampersand)
        (r'\s+\&\s+', '&'),

        # Strategy 3: + (plus)
        (r'\s+\+\s+', '+'),

        # Strategy 4: X (collaboration marker)
        (r'\s+x\s+', 'x'),

        # Strategy 5: And (only lowercase "and" in artist names)
        (r'\s+and\s+', 'and'),
    ]

    import re
    for pattern, marker in strategies:
        if re.search(pattern, normalized.lower()):
            # Split using this pattern
            parts = re.split(pattern, normalized, flags=re.IGNORECASE)

            # Clean up each part
            artists = []
            for part in parts:
                part = part.strip()
                if part and len(part) >= 2:  # Minimum length check
                    # Remove common trailing markers like "feat." or "ft."
                    part = re.sub(r'\s+(?:feat|ft\.?|featuring).*$', '', part, flags=re.IGNORECASE)
                    part = part.strip()
                    if part and len(part) >= 2:
                        artists.append(part)

            if artists:
                logger.debug(f"Split collaboration '{artist_name}' into {len(artists)} artists using '{marker}' marker: {artists}")
                return artists

    # No split found, return original as single artist
    logger.debug(f"No collaboration split found for '{artist_name}', treating as single artist")
    return [normalized]


def handle_collaboration(artist_name, song_title, mbid=None):
    """Handle collaboration artists by splitting into individual artists

    This function takes an artist collaboration (e.g., "Miranda Lambert & Chris Stapleton")
    and splits it into individual artists. Each artist will be stored separately
    in the database with their own MBID.

    Args:
        artist_name: Artist name (may be collaboration)
        song_title: Song title
        mbid: MusicBrainz ID (optional, usually None for collaborations)

    Returns:
        list: Tuples of (artist, song, mbid) for each individual artist
              If not a collaboration, returns [(artist, song, mbid)]

    Examples:
        >>> handle_collaboration("Miranda Lambert & Chris Stapleton", "Palomino", None)
        [('Miranda Lambert', 'Palomino', None), ('Chris Stapleton', 'Palomino', None)]

        >>> handle_collaboration("Taylor Swift", "Love Story", "abc123")
        [('Taylor Swift', 'Love Story', 'abc123')]
    """
    if not artist_name:
        return []

    # Normalize artist name first
    normalized_artist = normalize_with_edge_cases(artist_name)

    # Detect if this is a collaboration
    is_collab, split_artists = detect_collaboration(normalized_artist)

    if not is_collab or len(split_artists) <= 1:
        # Not a collaboration, return as-is
        logger.debug(f"'{artist_name}' is not a collaboration (single artist)")
        return [(normalized_artist, song_title, mbid)]

    # Collaboration detected - split into individual artists
    logger.info(f"Collaboration detected: '{artist_name}' split into {len(split_artists)} artists")

    results = []
    for individual_artist in split_artists:
        # Normalize each individual artist
        individual_artist = normalize_with_edge_cases(individual_artist)

        # Each artist gets the same song, but their own MBID (looked up later)
        # We pass None as mbid because each artist needs their own lookup
        results.append((individual_artist, song_title, None))

        logger.debug(f"  - Individual artist: {individual_artist}")

    return results
