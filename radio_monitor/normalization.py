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

logger = logging.getLogger(__name__)


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
        "Ne-Yo"  # hyphen preserved
        >>> strip_accents("café")
        "cafe"
    """
    if not text:
        return text

    # Normalize to NFKD form: decomposes accented chars into base + combining accent
    # Example: "é" → "e" + combining acute accent
    normalized = unicodedata.normalize('NFKD', text)

    # Remove combining diacritical marks (Unicode category Mn)
    # This keeps the base character but removes the accent
    return ''.join(
        c for c in normalized
        if not unicodedata.combining(c)
    )


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

# Known artist name corrections for database consistency
# These are systematic corrections applied BEFORE MBID lookup
# Maps incorrect/alternate forms to canonical MusicBrainz names
ARTIST_NAME_CORRECTIONS = {
    # Case/styling corrections
    'pnk': 'P!NK',
    'pink': 'P!NK',
    'rem': 'R.E.M.',
    'wham': 'Wham!',
    # Add more as discovered through validation
}


def apply_artist_corrections(artist_name: str) -> str:
    """Apply known artist name corrections

    This function corrects known systematic issues with artist names
    before they are stored in the database or used for MBID lookup.

    Args:
        artist_name: Raw artist name (may be incorrect)

    Returns:
        Corrected artist name (or original if no correction known)

    Examples:
        >>> apply_artist_corrections('pnk')
        'P!NK'
        >>> apply_artist_corrections('P!NK')
        'P!NK'  # Already correct
        >>> apply_artist_corrections('Unknown Artist')
        'Unknown Artist'  # No correction known
    """
    if not artist_name:
        return artist_name

    # Check lowercase version for case-insensitive matching
    artist_lower = artist_name.lower().strip()

    # Apply correction if known
    if artist_lower in ARTIST_NAME_CORRECTIONS:
        corrected = ARTIST_NAME_CORRECTIONS[artist_lower]
        logger.debug(f"Applied artist correction: {artist_name} → {corrected}")
        return corrected

    # No correction needed
    return artist_name


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

    # Rule 0: Fix encoding corruption (MUST BE FIRST)
    # This fixes corrupted UTF-8 bytes before any other processing
    text = fix_encoding_corruption(text)

    # Rule 0.5: Strip accent marks for matching
    # This fixes: Beyoncé → Beyonce (allows matching across accents)
    # Critical for MusicBrainz matching where accents may vary
    text = strip_accents(text)

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
    elif text == "Ac/dc":
        text = "AC/DC"  # Fix AC/DC after title case conversion

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
    # Apply known corrections first (pnk → P!NK, etc.)
    artist_name = apply_artist_corrections(artist_name)

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


def clean_song_title_for_query(song_title: str) -> str:
    """Clean song title for MusicBrainz queries

    Removes parentheticals, features, and other notation that MusicBrainz
    doesn't include in recording titles. Use this BEFORE querying MusicBrainz,
    but store the original title in the database.

    This is NON-DESTRUCTIVE - original title is preserved.

    Args:
        song_title: Original song title (may have parentheticals, etc.)

    Returns:
        Cleaned song title for MusicBrainz queries

    Examples:
        >>> clean_song_title_for_query('Rooster (2022 Remaster)')
        'Rooster'
        >>> clean_song_title_for_query('Meant to Be (feat. Florida Georgia Line)')
        'Meant to Be'
        >>> clean_song_title_for_query('Stateside + Zara Larsson')
        'Stateside'
    """
    if not song_title:
        return song_title

    cleaned = song_title

    # Remove parentheticals: (2022 Remaster), (Radio Edit), etc.
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
    cleaned = re.sub(r'\s+/\s.*$', '', cleaned)

    # Normalize whitespace
    cleaned = ' '.join(cleaned.split())

    # Log if title was changed
    if cleaned != song_title:
        logger.debug(f"Cleaned song title for query: '{song_title}' → '{cleaned}'")

    return cleaned.strip()


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
    text = re.sub(r"[''''´`]", '', text)

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
    match_key = normalize_for_matching(artist_name)

    # Safety check: ensure match_key is not empty
    if not match_key or match_key.strip() == '':
        # Fallback: use artist name (shouldn't happen, but safety net)
        logger.warning(f"Empty match_key generated for '{artist_name}', using fallback")
        match_key = artist_name.lower().replace(' ', '')

    # Safety check: ensure match_key is not too long
    if len(match_key) > 500:
        # Truncate extremely long names (shouldn't happen)
        logger.warning(f"match_key too long ({len(match_key)} chars) for '{artist_name}', truncating")
        match_key = match_key[:500]

    return match_key


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
        ' feat', ' ft.', ' ft ', 'featuring', ' with ', ' & ', ' + ', ' x ', ' and ', ';'
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

    # Normalize for splitting
    normalized = normalize_with_edge_cases(artist_name)

    # Splitting patterns in priority order
    # IMPORTANT: Order matters! Check comma/ampersand BEFORE feat
    # Otherwise "A & B feat. C" will split incorrectly
    strategies = [
        # Strategy 1: Semicolon (iHeartRadio uses this)
        (r'\s*;\s*', ';'),

        # Strategy 2: Commas (multiple artists like "Artist1, Artist2, Artist3")
        (r',\s*', ','),

        # Strategy 3: & (ampersand) - RELAXED: allow no spaces
        (r'\s*\&\s*', '&'),

        # Strategy 4: + (plus) - RELAXED: allow no spaces
        (r'\s*\+\s*', '+'),

        # Strategy 5: X (collaboration marker) - Must have spaces on both sides
        (r'\s+x\s+', 'x'),

        # Strategy 6: And (only lowercase "and" in artist names)
        (r'\s+and\s+', 'and'),

        # Strategy 7: Feat/ft/featuring (period is optional for "ft")
        # Check AFTER comma/ampersand to avoid incorrect splits
        (r'\s+(?:feat\.?|ft\.?|featuring)\s+', 'feat'),
    ]

    import re

    # Recursively split artist string until no more separators found
    def recursive_split(parts, depth=0):
        """Recursively split artist parts using all strategies"""
        if depth > 10:  # Prevent infinite recursion
            logger.warning(f"Recursion depth exceeded for '{parts}', stopping")
            return parts

        result = []
        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Try each strategy in order
            split_happened = False
            for pattern, marker in strategies:
                if re.search(pattern, part.lower()):
                    # Split this part using the pattern
                    sub_parts = re.split(pattern, part, flags=re.IGNORECASE)
                    # Clean sub-parts (strip whitespace, no feat removal yet)
                    cleaned_sub_parts = [sub.strip() for sub in sub_parts if sub.strip()]

                    # Recursively split the cleaned sub-parts FIRST
                    if cleaned_sub_parts:
                        final_parts = recursive_split(cleaned_sub_parts, depth + 1)
                        result.extend(final_parts)
                        split_happened = True
                    break  # Only use first matching pattern per recursion level

            if not split_happened:
                # No more splits possible, clean and add this part
                # Remove trailing feat markers only at the end
                part = re.sub(r'\s+(?:feat|ft\.?|featuring).*$', '', part, flags=re.IGNORECASE).strip()
                if part and len(part) >= 2:
                    result.append(part)

        return result

    # Start recursive splitting
    artists = recursive_split([normalized])

    # Remove duplicates while preserving order
    seen = set()
    unique_artists = []
    for artist in artists:
        if artist not in seen:
            seen.add(artist)
            unique_artists.append(artist)

    if unique_artists:
        logger.debug(f"Split collaboration '{artist_name}' into {len(unique_artists)} artists: {unique_artists}")
        return unique_artists

    # No split found, return original as single artist
    logger.debug(f"No collaboration split found for '{artist_name}', treating as single artist")
    return [normalized]


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

    if not is_collab or len(split_artists) <= 1:
        # Not a collaboration, return as-is
        logger.debug(f"'{artist_name}' is not a collaboration (single artist)")
        return [(normalized_artist, song_title, mbid)]

    # Collaboration detected - extract PRIMARY artist only
    # The primary artist is the first one before any collaboration markers
    primary_artist = split_artists[0]
    primary_artist = normalize_with_edge_cases(primary_artist)

    logger.info(f"Collaboration detected: '{artist_name}' -> Primary artist: '{primary_artist}' (ignoring featured artists)")

    # Return only the primary artist with the song
    # Featured artists are ignored to prevent Lidarr/Plex workflow issues
    return [(primary_artist, song_title, mbid)]
