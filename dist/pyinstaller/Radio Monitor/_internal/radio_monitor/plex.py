"""
Plex Integration module for Radio Monitor 1.0

This module handles Plex playlist creation with multi-strategy fuzzy matching:
- Multi-strategy fuzzy matching (exact → normalized → fuzzy → partial)
- All playlist modes (merge, replace, append, create, snapshot)
- Test-matching command
- Playlist config file support

Multi-Strategy Matching:
1. Exact match - title and artist must match exactly (case-insensitive)
2. Normalized match - Title Case, apostrophes unified, special chars handled
3. Fuzzy match - Levenshtein distance (>= 90% similarity)
4. Partial match - substring matching (fallback)

Normalization (Strategy 2):
- Converts ALL CAPS to Title Case (AIN'T IT FUN → Ain't It Fun)
- Unifies apostrophe variants (''´` → ')
- Preserves known acronyms (ABBA, KISS, TLC)
- Handles Roman numerals, contractions, collaborations

Key Principle: Radio songs might not match Plex library exactly due to
different formatting, spelling variations, or remix versions.
"""

import re
import logging
from datetime import datetime
from rapidfuzz import fuzz
from radio_monitor.normalization import normalize_artist_name, normalize_song_title

logger = logging.getLogger(__name__)


# ============================================================================
# ARTIST NAME MAPPING TABLE
# Known artist name variations scraped from radio vs Plex library names
# Built from historical Plex match failures and manual verification
#
# Users can add their own mappings in user_mappings.json (see get_canonical_artist_name)
# ============================================================================

ARTIST_NAME_MAPPING = {
    # Truncated names (scraped without last name)
    'Celine': 'Céline Dion',
    'Michael Buble': 'Michael Bublé',
    'Desree': 'Des\'ree',
    'Whitney': 'Whitney Houston',
    'Mariah': 'Mariah Carey',
    'Cher': 'Cher',
    'Rihanna': 'Rihanna',
    'Snoop': 'Snoop Dogg',
    'Puff Daddy': 'P. Diddy',
    'Diddy': 'P. Diddy',

    # Special character variations
    'Pnk': 'P!NK',
    'P!nk': 'P!NK',
    'Pink': 'P!NK',
    'Beyonce': 'Beyoncé',  # Also handled by adaptive fuzzy, but explicit is better
    'Andre 3000': 'André 3000',

    # Hyphen variations
    'A Ha': 'A-ha',
    'Ne Yo': 'Ne-Yo',
    'J Holiday': 'J-Holiday',
    'Jay Z': 'Jay-Z',
    'Snoop Dogg': 'Snoop Dogg',
    'Dr Dre': 'Dr. Dre',
    'Ice Cube': 'Ice Cube',
    'Ice T': 'Ice-T',

    # Collaboration separators (& vs + vs spaces)
    'Brooks Dunn': 'Brooks & Dunn',
    'Dan Shay': 'Dan + Shay',
    'Daryl Hall John Oates': 'Daryl Hall & John Oates',
    'Hall Oates': 'Daryl Hall & John Oates',
    'Hootie The Blowfish': 'Hootie & The Blowfish',
    'K Ci Jojo': 'K-Ci & JoJo',
    'K-Ci Jojo': 'K-Ci & JoJo',
    'Sheila E': 'Sheila E.',
    'Billy Ray Cyrus': 'Billy Ray Cyrus',
    'Ricky Skaggs': 'Ricky Skaggs',
    'George Jones': 'George Jones',
    'Sonny Cher': 'Sonny & Cher',

    # Alternative spellings / common typos
    'Crosby Still Nash': 'Crosby, Stills, Nash & Young',
    'Crosby Stills Nash': 'Crosby, Stills & Nash',
    'The Alan Parsons Project': 'The Alan Parsons Project',
    'Guns N Roses': 'Guns N\' Roses',
    'Guns and Roses': 'Guns N\' Roses',
    'Tom Petty': 'Tom Petty & The Heartbreakers',
    'Heartbreakers': 'Tom Petty & The Heartbreakers',
    'Steve Miller': 'The Steve Miller Band',

    # Unicode normalization (already handled, but explicit is faster)
    'All\u20104\u2010One': 'All-4-One',  # U+2010 hyphens
    'A\u2010Ha': 'A-ha',  # U+2010 hyphen
    'Ne\u2010Yo': 'Ne-Yo',  # U+2010 hyphen
    'Des\u2019ree': 'Des\'ree',  # U+2019 apostrophe

    # Country collaborations (common pattern)
    'Tim Mcgraw': 'Tim McGraw',  # Capitalization
    'Vince Gill': 'Vince Gill',
    'Patty Loveless': 'Patty Loveless',
    'Travis Tritt': 'Travis Tritt',
    'Marty Roe': 'Marty Roe',
    'Jim Messina': 'Jim Messina',
    'Carrie Underwood': 'Carrie Underwood',
    'Miranda Lambert': 'Miranda Lambert',
    'Blake Shelton': 'Blake Shelton',
    'Luke Bryan': 'Luke Bryan',
    'Florida Georgia Line': 'Florida Georgia Line',
    'Rascal Flatts': 'Rascal Flatts',

    # Hip-hop / R&B collaborations
    'Drake': 'Drake',
    'DJ Snake': 'DJ Snake',
    'Juicy J': 'Juicy J',
    'Big Sean': 'Big Sean',
    'Post Malone': 'Post Malone',
    'Morgan Wallen': 'Morgan Wallen',
    'Kanye West': 'Kanye West',
    'Jay Z': 'Jay-Z',
    'Lil Wayne': 'Lil Wayne',
    'Drake Future': 'Drake & Future',
}


def get_canonical_artist_name(artist_name):
    """
    Get the canonical Plex name for an artist using the mapping table.

    Checks mappings in this order:
    1. User-defined mappings from user_mappings.json (if exists)
    2. Built-in mappings from ARTIST_NAME_MAPPING table

    Args:
        artist_name: Artist name from database

    Returns:
        Canonical artist name if found in mapping, otherwise original name
    """
    import os
    import json

    # Normalize input for lookup
    normalized_input = artist_name.strip()

    # STEP 1: Check user-defined mappings first (allows override of built-ins)
    user_mappings_file = 'user_mappings.json'
    if os.path.exists(user_mappings_file):
        try:
            with open(user_mappings_file, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
                user_mappings = user_data.get('mappings', {})

            # Case-insensitive lookup in user mappings
            for key, value in user_mappings.items():
                if key.lower() == normalized_input.lower():
                    if value != normalized_input:
                        logger.debug(f"  User artist mapping: {normalized_input} → {value}")
                    return value
        except Exception as e:
            logger.warning(f"Error loading user_mappings.json: {e}")

    # STEP 2: Check built-in mappings
    for key, value in ARTIST_NAME_MAPPING.items():
        if key.lower() == normalized_input.lower():
            if value != normalized_input:
                logger.debug(f"  Built-in artist mapping: {normalized_input} → {value}")
            return value

    # Return original if no mapping found
    return normalized_input


def calculate_match_confidence(db_song, db_artist, plex_track, strategy_used):
    """
    Calculate confidence score for a Plex match.

    Returns a confidence score (0-100) and confidence level (HIGH/MEDIUM/LOW).

    Args:
        db_song: Song title from database
        db_artist: Artist name from database
        plex_track: Plex Track object
        strategy_used: Which strategy found the match (0-4)

    Returns:
        tuple: (confidence_score, confidence_level, details)
            - confidence_score: 0-100
            - confidence_level: 'HIGH', 'MEDIUM', or 'LOW'
            - details: dict with scoring breakdown
    """
    try:
        plex_song = plex_track.title if hasattr(plex_track, 'title') else ""
        plex_artist = plex_track.artist().title if plex_track.artist() else ""

        # Base score depends on strategy used
        strategy_scores = {
            '0a': 98,  # Artist-first exact match
            '0b': 95,  # Artist-first normalized match
            '0c': 85,  # Artist-first adaptive fuzzy
            '1': 98,   # Exact match
            '2': 90,   # Normalized match
            '3': 80,   # Adaptive fuzzy match
            '4': 70,   # Partial match
        }
        base_score = strategy_scores.get(str(strategy_used), 70)

        # Calculate fuzzy ratios
        song_ratio = fuzzy_ratio(db_song, plex_song)
        artist_ratio = fuzzy_ratio(db_artist, plex_artist)

        # Adjust score based on fuzzy ratios
        min_ratio = min(song_ratio, artist_ratio)

        # Boost for very high ratios
        if min_ratio >= 98:
            base_score += 2
        elif min_ratio >= 95:
            base_score += 1

        # Penalty for lower ratios
        if min_ratio < 85:
            base_score -= 10
        elif min_ratio < 90:
            base_score -= 5

        # Bonus for exact artist name match (after normalization)
        db_artist_norm = normalize_artist_name(db_artist)
        plex_artist_norm = normalize_artist_name(plex_artist)
        if db_artist_norm.lower() == plex_artist_norm.lower():
            base_score += 3

        # Bonus for exact song title match
        db_song_norm = normalize_song_title(db_song)
        plex_song_norm = normalize_song_title(plex_song)
        if db_song_norm.lower() == plex_song_norm.lower():
            base_score += 2

        # Bonus for artist name mapping table match
        canonical_artist = get_canonical_artist_name(db_artist)
        if canonical_artist.lower() == plex_artist_norm.lower():
            base_score += 5

        # Penalty for very short strings (higher chance of false positive)
        if len(db_song) < 5 or len(db_artist) < 3:
            base_score -= 5

        # Ensure score is within bounds
        confidence_score = max(0, min(100, base_score))

        # Determine confidence level
        if confidence_score >= 90:
            confidence_level = 'HIGH'
        elif confidence_score >= 75:
            confidence_level = 'MEDIUM'
        else:
            confidence_level = 'LOW'

        details = {
            'strategy': strategy_used,
            'song_ratio': song_ratio,
            'artist_ratio': artist_ratio,
            'min_ratio': min_ratio,
            'db_artist': db_artist,
            'plex_artist': plex_artist,
            'db_song': db_song,
            'plex_song': plex_song,
        }

        return confidence_score, confidence_level, details

    except Exception as e:
        logger.error(f"Error calculating match confidence: {e}")
        return 50, 'LOW', {'error': str(e)}


def fuzzy_ratio(str1, str2):
    """Calculate Levenshtein similarity ratio (0-100)

    Args:
        str1: First string
        str2: Second string

    Returns:
        Similarity percentage (0-100)
    """
    if not str1 or not str2:
        return 0

    return int(fuzz.ratio(str1.lower(), str2.lower()))


def adaptive_fuzzy_match(str1, str2, debug=False):
    """Calculate fuzzy match score with adaptive threshold for common patterns

    Uses a lower threshold (85%) for single-character differences like:
    - Missing apostrophe: "Beyonce" vs "Beyoncé" (85.7%)
    - Missing ampersand: "Dan Shay" vs "Dan + Shay" (88.9%)
    - Missing hyphen: "A Ha" vs "A-ha" (75% - but short string, so might not match)

    Args:
        str1: First string
        str2: Second string
        debug: Enable debug logging

    Returns:
        True if strings match according to adaptive rules, False otherwise
    """
    if not str1 or not str2:
        return False

    # Calculate base fuzzy ratio
    ratio = fuzz.ratio(str1.lower(), str2.lower())

    # Standard threshold: 90%
    if ratio >= 90:
        return True

    # Adaptive threshold: 85% for specific patterns
    if ratio >= 85:
        # Calculate character-level differences
        try:
            import Levenshtein
            distance = Levenshtein.distance(str1.lower(), str2.lower())
            max_len = max(len(str1), len(str2))

            # Allow match if:
            # 1. Only 1-2 character difference AND
            # 2. String is long enough (>8 chars for medium strings, >12 for shorter strings) AND
            # 3. Ratio is above 85%
            #
            # Rationale:
            # - "Beyonce" (7) vs "Beyoncé" (7): distance=1, ratio=85.7% - should match but too short
            # - "Dan + Shay" (9) vs "Dan Shay" (8): distance=1, ratio=88.9% - should match
            # - "Brooks & Dunn" (12) vs "Brooks Dunn" (11): distance=1, ratio=91.7% - should match
            #
            # For very short strings (<8 chars), require higher threshold (90%)
            # For medium strings (8-12 chars), allow 85%+ with max 1-2 char diff
            # For long strings (>12 chars), allow 85%+ with max 1-2 char diff

            if max_len > 8:
                # Medium to long strings: 85%+ with 1-2 char difference
                if distance <= 2:
                    if debug:
                        logger.debug(f"  ✓ Adaptive fuzzy match: {ratio:.1f}% (distance={distance}, max_len={max_len})")
                    return True
            else:
                # Very short strings: need slightly higher threshold (85.5%+)
                # This allows "Beyonce" (7 chars) vs "Beyoncé" (7 chars) at 85.7%
                if ratio >= 85.5:
                    if debug:
                        logger.debug(f"  ✓ Adaptive fuzzy match (short string): {ratio:.1f}%")
                    return True

        except ImportError:
            # Levenshtein package not available, use ratio-only logic
            if ratio >= 87:  # Slightly higher threshold without distance calculation
                if debug:
                    logger.debug(f"  ✓ Adaptive fuzzy match: {ratio:.1f}%")
                return True

    return False


def get_title_variations(title):
    """Generate multiple title variations for Plex searching

    Handles common punctuation and formatting differences:
    - Removes parentheses with (feat., remix, extended, etc.)
    - Removes apostrophes (tries both with and without)
    - Removes periods from abbreviations (MR., DR.)
    - Replaces hyphens with spaces
    - Removes diacritics/accents (ROSÉ → ROSE)
    - Normalizes whitespace

    Args:
        title: Original song title

    Returns:
        List of title variations to try (original first, then cleaned versions)
    """
    import re
    import unicodedata
    variations = [title]  # Always try original first

    # Variation 1: Remove parenthetical content (feat., remix, extended, etc.)
    # This helps: "TOO Sweet (extended Intro)" -> "TOO Sweet"
    no_paren = re.sub(r'\s*[(\[].*?[)\]]', '', title).strip()
    if no_paren != title:
        variations.append(no_paren)

    # Variation 2a: Convert regular apostrophes (U+0027) to Plex apostrophe (U+2019)
    # This helps when database has U+0027 but Plex has U+2019
    plex_apos = title.replace("\u0027", "\u2019")  # ' → '
    if plex_apos != title:
        variations.append(plex_apos)

    # Variation 2b: Remove apostrophes entirely
    # This helps: "Summer Of '69" -> "Summer Of 69"
    # But can hurt: "It's Time" -> "Its Time"
    no_apostrophe = re.sub(r"[''''`´]", '', title)  # Includes U+2019 right single quote
    if no_apostrophe != title:
        variations.append(no_apostrophe)

    # Variation 3: Remove periods from abbreviations
    # This helps: "MR. Electric Blue" -> "MR Electric Blue"
    no_period = title.replace('.', '')
    if no_period != title:
        variations.append(no_period)

    # Variation 4: Replace hyphens with spaces
    # This helps: "Undone - The Sweater Song" -> "Undone  The Sweater Song"
    with_spaces = title.replace('-', ' ')
    with_spaces = ' '.join(with_spaces.split())  # Normalize multiple spaces
    if with_spaces != title:
        variations.append(with_spaces)

    # Variation 5: Remove diacritics/accents
    # This helps: "ROSÉ" -> "ROSE", "Beyoncé" -> "Beyonce"
    # Normalize unicode to ASCII form, remove combining diacritics
    normalized = unicodedata.normalize('NFKD', title)
    no_diacritics = ''.join([c for c in normalized if not unicodedata.combining(c)])
    if no_diacritics != title:
        variations.append(no_diacritics)

    # Variation 6: Combined aggressive cleaning (no paren + no apostrophe + no period + no hyphen + no diacritics)
    aggressive = no_paren
    aggressive = re.sub(r"['''`´]", '', aggressive)  # Includes U+2019
    aggressive = aggressive.replace('.', '')
    aggressive = aggressive.replace('-', ' ')
    aggressive = ' '.join(aggressive.split())
    # Also remove diacritics from aggressive version
    aggressive_norm = unicodedata.normalize('NFKD', aggressive)
    aggressive = ''.join([c for c in aggressive_norm if not unicodedata.combining(c)])
    if aggressive != title and aggressive not in variations:
        variations.append(aggressive)

    # Variation 7: Add back apostrophes for common contractions
    # This helps: "I Dont Want" → "I Don't Want", "Nothin Like You" → "Nothin' Like You"
    # List of common contractions that should have apostrophes
    contractions_map = {
        'dont': "don't",
        'Dont': "Don't",
        'DONT': "DON'T",
        'cant': "can't",
        'Cant': "Can't",
        'wont': "won't",
        'Wont': "Won't",
        'im': "i'm",
        'Im': "I'm",
        'its': "it's",
        'Its': "It's",
        'thats': "that's",
        'Thats': "That's",
        'youre': "you're",
        'Youre': "You're",
        'aint': "ain't",
        'Aint': "Ain't",
        'nothin': "nothin'",
        'Nothin': "Nothin'",
        'gimme': "gimme'",
        'Gimme': "Gimme'",
        'goin': "goin'",
        'Goin': "Goin'",
        'comin': "comin'",
        'Comin': "Comin'",
        'whatcha': "whatcha'",
        'Whatcha': "Whatcha'",
        'kinda': "kinda'",
        'Kinda': "Kinda'",
        'outta': "outta'",
        'Outta': "Outta'",
        'coulda': "coulda'",
        'Coulda': "Coulda'",
        'woulda': "woulda'",
        'Woulda': "Woulda'",
        'shoulda': "shoulda'",
        'Shoulda': "Shoulda'",
        'musta': "musta'",
        'Musta': "Musta'",
        'howre': "how're",
        'Howre': "How're",
        'whats': "what's",
        'Whats': "What's",
        'whos': "who's",
        'Whos': "Who's",
        'lets': "let's",
        'Lets': "Let's",
        'theres': "there's",
        'Theres': "There's",
        'heres': "here's",
        'Heres': "Here's",
        'everybodys': "everybody's",
        'Everybodys': "Everybody's",
        'somebodys': "somebody's",
        'Somebodys': "Somebody's",
        'nobodys': "nobody's",
        'Nobodys': "Nobody's",
        'everyones': "everyone's",
        'Everyones': "Everyone's",
        'someones': "someone's",
        'Someones': "Someone's",
        'anyones': "anyone's",
        'Anyones': "Anyone's",
        'elses': "else's",
        'Elses': "Else's",
        'girls': "girls'",
        "girl's": "girls'",
        'boys': "boys'",
        "boy's": "boys'",
        'todays': "today's",
        'Todays': "Today's",
        'yesterdays': "yesterday's",
        'Yesterdays': "Yesterday's",
        'tomorrows': "tomorrow's",
        'Tomorrows': "Tomorrow's",
        'summers': "summer's",
        'winters': "winter's",
        'nights': "nights'",
        'morns': "morn's",
    }

    # Check if any contraction is in the title (case-sensitive replacement)
    title_with_apostrophes = title
    found_contraction = False
    for without_apos, with_apos in contractions_map.items():
        if without_apos in title:
            title_with_apostrophes = title_with_apostrophes.replace(without_apos, with_apos)
            found_contraction = True

    if found_contraction and title_with_apostrophes not in variations:
        variations.append(title_with_apostrophes)

    # Variation 8: Add back apostrophes + remove diacritics (combination for Beyonce → Beyoncé type cases)
    if found_contraction:
        # Remove diacritics from the version with added apostrophes
        with_apos_norm = unicodedata.normalize('NFKD', title_with_apostrophes)
        with_apos_no_diacritics = ''.join([c for c in with_apos_norm if not unicodedata.combining(c)])
        if with_apos_no_diacritics != title and with_apos_no_diacritics not in variations:
            variations.append(with_apos_no_diacritics)

    return variations


def get_artist_variations(artist_name):
    """Generate multiple artist name variations for Plex searching

    Handles common differences between database and Plex artist names:
    - Artist name mapping table lookups (Celine → Céline Dion)
    - Adds hyphens to two-word names (A Ha → A-ha)
    - Adds common collaboration separators (&, +) for two-word and multi-word names
    - Complex collaboration detection (3+ words like "Daryl Hall John Oates")
    - Removes all separators (Brooks & Dunn → Brooks Dunn)
    - Converts unicode hyphens to ASCII hyphens
    - Converts unicode apostrophes to ASCII apostrophes

    Args:
        artist_name: Original artist name

    Returns:
        List of artist name variations to try (original first, then variations)
    """
    import unicodedata

    # STEP 1: Check artist name mapping table FIRST
    # This handles known variations like "Celine" → "Céline Dion"
    canonical_name = get_canonical_artist_name(artist_name)
    variations = [canonical_name]  # Start with canonical name

    # If canonical name is different, it's already the first variation
    if canonical_name != artist_name:
        # Also keep original for backward compatibility
        variations.insert(0, artist_name)

    # Pre-processing: normalize unicode characters
    # Convert all unicode dashes/hyphens to ASCII hyphen
    normalized = re.sub(r"[‐‑‒–—―]", '-', artist_name)
    # Convert all apostrophe variants to ASCII apostrophe
    normalized = re.sub(r"[''''´`]", "'", normalized)

    if normalized != artist_name and normalized not in variations:
        variations.append(normalized)

    # Variation 1: Spaces → Hyphens (for artist names like "A Ha" → "A-ha")
    # Only apply to 2-word names without existing hyphens
    if ' ' in normalized and '-' not in normalized:
        parts = normalized.split()
        # Only for short 2-word artist names (likely to be hyphenated)
        if len(parts) == 2 and len(normalized) < 30:
            with_hyphens = normalized.replace(' ', '-')
            if with_hyphens not in variations:
                variations.append(with_hyphens)

    # Variation 2: Add common collaboration separators (&, +) for 2-word names
    # For "Brooks Dunn" → "Brooks & Dunn", "Brooks + Dunn"
    if ' ' in normalized and not any(sep in normalized for sep in ['&', '+', '/']):
        parts = normalized.split()
        if len(parts) == 2:  # Only for 2-word artist names (likely collaborations)
            # Skip very common words and short words that aren't collaborations
            first_word_lower = parts[0].lower()
            second_word_lower = parts[1].lower()
            skip_words = {'the', 'and', 'or', 'feat', 'ft', 'featuring', 'with'}

            # Both words must be at least 3 letters to be a collaboration
            # This prevents "A Ha" → "A & Ha" (false positive)
            both_long_enough = len(parts[0]) >= 3 and len(parts[1]) >= 3

            if (first_word_lower not in skip_words and
                second_word_lower not in skip_words and
                both_long_enough):
                # Try ampersand
                with_ampersand = f"{parts[0]} & {parts[1]}"
                if with_ampersand not in variations:
                    variations.append(with_ampersand)

                # Try plus sign
                with_plus = f"{parts[0]} + {parts[1]}"
                if with_plus not in variations:
                    variations.append(with_plus)

    # Variation 3: Complex collaboration detection (3+ words)
    # For "Daryl Hall John Oates" → "Daryl Hall & John Oates"
    # For "Joe Cocker Jennifer Warnes" → "Joe Cocker & Jennifer Warnes"
    if ' ' in normalized and not any(sep in normalized for sep in ['&', '+', '/']):
        parts = normalized.split()
        if len(parts) >= 3:  # 3 or more words
            # Try to insert & between last two artists
            # Pattern: "Artist1 Artist2 Artist3" → "Artist1 Artist2 & Artist3"
            # This handles: "Daryl Hall John Oates" → "Daryl Hall & John Oates"
            if len(parts) >= 3:
                # Assume last 2 parts are separate artists
                with_ampersand = ' '.join(parts[:-2]) + ' ' + ' & '.join(parts[-2:])
                if with_ampersand not in variations:
                    variations.append(with_ampersand)

                # Also try with + sign
                with_plus = ' '.join(parts[:-2]) + ' ' + ' + '.join(parts[-2:])
                if with_plus not in variations:
                    variations.append(with_plus)

                # For 4+ words, try other combinations
                # "K Ci Jojo" → "K-Ci & JoJo" (special case handled by mapping)
                if len(parts) >= 4:
                    # Try inserting & between each pair
                    for i in range(1, len(parts)):
                        if i < len(parts) - 1:
                            combo = ' & '.join([
                                ' '.join(parts[:i]),
                                ' '.join(parts[i:])
                            ])
                            if combo not in variations:
                                variations.append(combo)

    # Variation 4: Remove all separators (for reverse matching)
    # "Brooks & Dunn" → "Brooks Dunn"
    no_separators = normalized.replace('&', '').replace('+', '').replace('/', '')
    no_separators = re.sub(r'\s+', ' ', no_separators).strip()
    if no_separators != normalized and no_separators not in variations:
        variations.append(no_separators)

    return variations


def find_song_in_library(music_library, song_title, artist_name, debug=False):
    """Find song in Plex library using multi-strategy fuzzy matching

    Args:
        music_library: Plex music library section
        song_title: Song title to find
        artist_name: Artist name to find
        debug: Enable debug logging

    Returns:
        Plex Track object or None
    """
    if debug:
        logger.debug(f"Searching for: {song_title} - {artist_name}")

    # STRATEGY 0: Artist-first search (bypasses Plex search limitations)
    # For common song titles, Plex search doesn't return all tracks
    # So we search by artist first, then within their catalog
    if debug:
        logger.debug(f"  Trying Strategy 0: Artist-first search")

    # Get artist variations for matching
    artist_variations = get_artist_variations(artist_name)
    if debug and len(artist_variations) > 1:
        logger.debug(f"  Will try {len(artist_variations)} artist variations")

    try:
        # Search for artist using each variation
        for search_artist in artist_variations:
            if len(artist_variations) > 1 and debug:
                logger.debug(f"  Searching for artist: {search_artist}")

            artists = music_library.search(search_artist, libtype='artist')

        if artists:
            # Check each artist match
            for artist in artists:
                artist_title = artist.title if hasattr(artist, 'title') else str(artist)

                # Check if artist name matches any of our variations (case-insensitive)
                # This handles "A Ha" matching "A-ha", "Brooks Dunn" matching "Brooks & Dunn", etc.
                artist_match_found = False
                for variation in artist_variations:
                    if artist_title.lower() == variation.lower():
                        artist_match_found = True
                        break

                if artist_match_found:
                    if debug:
                        logger.debug(f"  Found artist: {artist_title}")

                    # Get ALL tracks from this artist
                    all_tracks = []
                    for album in artist.albums():
                        all_tracks.extend(album.tracks())

                    if debug:
                        logger.debug(f"  Artist has {len(all_tracks)} tracks")

                    # Search for matching title within artist's catalog
                    # Try all title variations
                    for search_title in get_title_variations(song_title):
                        # Match using all strategies (exact, normalized, fuzzy)
                        for track in all_tracks:
                            try:
                                # Strategy 0a: Exact match (case-insensitive)
                                if track.title.lower() == search_title.lower():
                                    if debug:
                                        logger.debug(f"  ✓ Artist-first exact match: {track.title}")
                                    return track

                                # Strategy 0b: Normalized match
                                track_norm = normalize_song_title(track.title)
                                search_norm = normalize_song_title(search_title)

                                if (track_norm.lower() == search_norm.lower() or
                                    track_norm.lower() in search_norm.lower() or
                                    search_norm.lower() in track_norm.lower()):
                                    if debug:
                                        logger.debug(f"  ✓ Artist-first normalized match: {track.title}")
                                    return track

                                # Strategy 0c: Adaptive fuzzy match
                                # Uses 85% threshold for single-character differences
                                if adaptive_fuzzy_match(track.title, search_title, debug=debug):
                                    return track
                            except Exception:
                                continue
                    break
    except Exception as e:
        if debug:
            logger.debug(f"  Artist-first search failed: {e}")

    # Get title variations to try for traditional search
    title_variations = get_title_variations(song_title)

    if debug and len(title_variations) > 1:
        logger.debug(f"  Will try {len(title_variations)} title variations")

    # Try each title variation
    for variation_idx, search_title in enumerate(title_variations):
        if variation_idx > 0 and debug:
            logger.debug(f"  Trying variation {variation_idx}: \"{search_title}\"")

        # Search for tracks with matching title
        try:
            # Limit search results to avoid timeout on common song titles
            tracks = music_library.search(title=search_title, libtype='track', maxresults=100)
        except Exception as e:
            logger.error(f"Error searching Plex library: {e}")
            continue

        if not tracks:
            if debug:
                logger.debug(f"  No tracks found with title: {search_title}")
            continue

        if debug:
            logger.debug(f"  Found {len(tracks)} tracks with title: {search_title}")

        # Strategy 1: Exact match (with artist variations)
        for track in tracks:
            try:
                track_artist = track.artist().title if track.artist() else ""
                # Check if artist matches any variation
                for search_artist in artist_variations:
                    if track_artist.lower() == search_artist.lower() and track.title.lower() == song_title.lower():
                        if debug:
                            logger.debug(f"  ✓ Exact match: {track.title} - {track_artist}")
                        return track
            except Exception as e:
                if debug:
                    logger.debug(f"  Error accessing track: {e}")
                continue

        # Strategy 2: Normalized match (using proper normalization + artist variations)
        song_norm = normalize_song_title(song_title)

        # Try matching with each artist variation
        for search_artist in artist_variations:
            artist_norm = normalize_artist_name(search_artist)

            for track in tracks:
                try:
                    track_artist = track.artist().title if track.artist() else ""
                    track_artist_norm = normalize_artist_name(track_artist)
                    track_song_norm = normalize_song_title(track.title)

                    # Check if normalized artist and song match
                    # Use substring matching to handle remixes, features, etc.
                    artist_match = (artist_norm.lower() in track_artist_norm.lower() or
                                   track_artist_norm.lower() in artist_norm.lower())
                    song_match = (song_norm.lower() in track_song_norm.lower() or
                                 track_song_norm.lower() in song_norm.lower())

                    if artist_match and song_match:
                        if debug:
                            logger.debug(f"  ✓ Normalized match: {track.title} - {track_artist}")
                            logger.debug(f"    DB norm: {song_norm} - {artist_norm}")
                            logger.debug(f"    Plex norm: {track_song_norm} - {track_artist_norm}")
                        return track
                except Exception as e:
                    continue

        # Strategy 3: Adaptive fuzzy match (Levenshtein with adaptive threshold + artist variations)
        best_match = None
        best_score = 0

        for track in tracks[:20]:  # Check top 20 for fuzzy
            try:
                track_artist = track.artist().title if track.artist() else ""

                # Check against all artist variations
                for search_artist in artist_variations:
                    artist_ratio = fuzzy_ratio(search_artist, track_artist)
                    song_ratio = fuzzy_ratio(song_title, track.title)

                    if artist_ratio > best_score and song_ratio > best_score:
                        best_score = min(artist_ratio, song_ratio)
                        best_match = (track, artist_ratio, song_ratio)

                    # Use adaptive fuzzy matching for both artist AND song
                    if adaptive_fuzzy_match(search_artist, track_artist, debug=debug) and \
                       adaptive_fuzzy_match(song_title, track.title, debug=debug):
                        if debug:
                            logger.debug(f"  ✓ Adaptive fuzzy match: {track.title} - {track_artist} (artist: {artist_ratio}%, song: {song_ratio}%)")
                        return track
            except Exception as e:
                continue

        # Strategy 4: Partial match (substring with artist variations)
        for track in tracks:
            try:
                track_artist = track.artist().title if track.artist() else ""
                # Check if any artist variation is a substring
                for search_artist in artist_variations:
                    if search_artist.lower() in track_artist.lower() and song_title.lower() in track.title.lower():
                        if debug:
                            logger.debug(f"  ✓ Partial match: {track.title} - {track_artist}")
                        return track
            except Exception as e:
                continue

    # If we get here, no match found with any title variation
    if debug:
        logger.debug(f"  ✗ No match found for: {song_title} - {artist_name}")

    return None

def create_playlist(db, plex, playlist_name, mode='merge', filters=None):
    """Create or update Plex playlist

    Args:
        db: RadioDatabase instance
        plex: PlexServer instance
        playlist_name: Name of playlist
        mode: Playlist mode ('merge', 'replace', 'append', 'create', 'snapshot', 'recent', 'random')
        filters: Dict with filter criteria:
            - days: Only include songs from last N days
            - limit: Maximum number of songs
            - station_ids: Array of station IDs to filter by (optional)
            - min_plays: Minimum play count (default: 1)
            - max_plays: Maximum play count (optional, NULL = no maximum)
            - exclude_blocklist: Exclude blocked artists/songs (default: True)

    Returns:
        dict with:
        - added: Number of songs added to playlist
        - not_found: Number of songs not found in Plex
        - not_found_list: List of dicts with song_title and artist_name
        - excluded_by_blocklist: Number of songs excluded by blocklist
    """
    if filters is None:
        filters = {'days': 7, 'limit': 50, 'min_plays': 1}

    days = filters.get('days', 7)
    limit = filters.get('limit', 50)
    station_ids = filters.get('station_ids', None)
    min_plays = filters.get('min_plays', 1)
    max_plays = filters.get('max_plays', None)
    exclude_blocklist = filters.get('exclude_blocklist', True)

    # Calculate over-query limit (35% more to account for Plex matching failures)
    # Cap at 2500 for database queries (Plex playlist itself will be capped at 1500)
    over_query_limit = min(int(limit * 1.35), 2500)
    logger.info(f"Querying for {over_query_limit} songs (target: {limit}, 35% buffer for Plex matching)")

    # Get music library

    # Get music library
    music_library_name = filters.get('music_library_name', 'Music')
    try:
        music_library = plex.library.section(music_library_name)
    except Exception as e:
        logger.error(f"Error accessing Plex music library '{music_library_name}': {e}")
        return {
            'added': 0,
            'not_found': 0,
            'not_found_list': [],
            'error': f"Music library '{music_library_name}' not found"
        }

    # Query database for songs based on mode
    if mode == 'random':
        # NEW: Random mode
        if station_ids:
            songs = db.get_random_songs(
                station_ids=station_ids,
                min_plays=min_plays,
                max_plays=max_plays,
                days=days,
                limit=over_query_limit
            )
        else:
            songs = db.get_random_songs(
                min_plays=min_plays,
                max_plays=max_plays,
                days=days,
                limit=over_query_limit
            )
    elif mode == 'recent':
        if station_ids:
            songs = db.get_recent_songs(days=days, station_ids=station_ids, limit=over_query_limit)
        else:
            songs = db.get_recent_songs(days=days, limit=over_query_limit)
    else:
        # Top songs mode (merge, replace, append, create, snapshot)
        if station_ids:
            songs = db.get_top_songs(days=days, station_ids=station_ids, limit=over_query_limit)
        else:
            songs = db.get_top_songs(days=days, limit=over_query_limit)

    logger.info(f"Found {len(songs)} songs in database matching criteria")

    # Filter out blocklisted songs if requested
    excluded_by_blocklist = 0
    if exclude_blocklist:
        original_count = len(songs)
        from radio_monitor.database import crud
        filtered_songs = []
        for song in songs:
            # song format: (song_id, song_title, artist_name, play_count)
            song_id, song_title, artist_name, play_count = song
            # Get artist_mbid for blocking check
            cursor = db.get_cursor()
            try:
                cursor.execute("SELECT artist_mbid FROM songs WHERE id = ?", (song_id,))
                row = cursor.fetchone()
                artist_mbid = row[0] if row else None
            finally:
                cursor.close()

            if not crud.is_song_blocked(db.get_cursor(), song_id, artist_mbid):
                filtered_songs.append(song)

        songs = filtered_songs
        excluded_by_blocklist = original_count - len(songs)
        logger.info(f"Excluded {excluded_by_blocklist} songs by blocklist, {len(songs)} remaining")

    # Find songs in Plex library
    songs_to_add = []
    not_found = []

    for idx, (song_id, song_title, artist_name, play_count) in enumerate(songs, 1):
        if idx % 10 == 0 or idx == len(songs):
            logger.info(f"Processing song {idx}/{len(songs)}: {song_title} - {artist_name}")

        track = find_song_in_library(music_library, song_title, artist_name)

        if track:
            songs_to_add.append(track)
        else:
            not_found.append((song_id, song_title, artist_name))
            # Log Plex failure to database
            try:
                from radio_monitor.database import plex_failures
                cursor = db.get_cursor()
                plex_failures.log_plex_failure(
                    cursor,
                    song_id=song_id,
                    playlist_id=None,  # We don't have playlist_id yet
                    failure_reason='no_match',
                    search_attempts=4,  # We try 4 strategies
                    search_terms={'title': song_title, 'artist': artist_name}
                )
                db.conn.commit()
                cursor.close()
            except Exception as e:
                logger.error(f"Failed to log Plex failure: {e}")

    logger.info(f"Finished searching Plex: found {len(songs_to_add)}/{len(songs)} songs")

    # Trim to requested limit if we have too many matches
    if len(songs_to_add) > limit:
        logger.info(f"Trimming playlist from {len(songs_to_add)} to requested limit of {limit}")
        songs_to_add = songs_to_add[:limit]

    # Create or update playlist based on mode
    try:
        if mode == 'create':
            # Create new playlist (error if exists)
            playlist = plex.createPlaylist(playlist_name, items=songs_to_add)
            logger.info(f"Created playlist '{playlist_name}' with {len(songs_to_add)} songs")

        elif mode == 'replace':
            # Replace existing playlist (or create if doesn't exist)
            try:
                playlist = plex.playlist(playlist_name)
                playlist.removeItems(playlist.items())
                playlist.addItems(songs_to_add)
                logger.info(f"Replaced playlist '{playlist_name}' with {len(songs_to_add)} songs")
            except:
                # Playlist doesn't exist, create it
                playlist = plex.createPlaylist(playlist_name, items=songs_to_add)
                logger.info(f"Created playlist '{playlist_name}' with {len(songs_to_add)} songs")

        elif mode == 'append':
            # Append to existing playlist (or create if doesn't exist)
            try:
                playlist = plex.playlist(playlist_name)
                existing_keys = {item.ratingKey for item in playlist.items()}
                new_songs = [s for s in songs_to_add if s.ratingKey not in existing_keys]
                if new_songs:
                    playlist.addItems(new_songs)
                logger.info(f"Appended {len(new_songs)} songs to '{playlist_name}'")
            except:
                # Playlist doesn't exist, create it
                playlist = plex.createPlaylist(playlist_name, items=songs_to_add)
                logger.info(f"Created playlist '{playlist_name}' with {len(songs_to_add)} songs")

        elif mode == 'merge':
            # Smart merge: remove stale, add new
            try:
                playlist = plex.playlist(playlist_name)
                existing_items = playlist.items()
                existing_keys = {item.ratingKey for item in existing_items}

                # Remove stale items (no longer in database)
                to_remove = [item for item in existing_items if item.ratingKey not in [s.ratingKey for s in songs_to_add]]
                if to_remove:
                    playlist.removeItems(to_remove)

                # Add new items
                to_add = [s for s in songs_to_add if s.ratingKey not in existing_keys]
                if to_add:
                    playlist.addItems(to_add)

                logger.info(f"Merged '{playlist_name}': -{len(to_remove)}, +{len(to_add)}")
            except:
                # Playlist doesn't exist, create it
                playlist = plex.createPlaylist(playlist_name, items=songs_to_add)
                logger.info(f"Created playlist '{playlist_name}' with {len(songs_to_add)} songs")

        elif mode == 'snapshot':
            # Create timestamped snapshot
            timestamp = datetime.now().strftime('%Y-%m-%d')
            snapshot_name = f"{playlist_name} {timestamp}"
            playlist = plex.createPlaylist(snapshot_name, items=songs_to_add)
            logger.info(f"Created snapshot '{snapshot_name}' with {len(songs_to_add)} songs")

        elif mode == 'recent':
            # Recent mode: replace with most recently played songs
            # Works like replace - clear old list, add new recent songs
            try:
                playlist = plex.playlist(playlist_name)
                playlist.removeItems(playlist.items())
                playlist.addItems(songs_to_add)
                logger.info(f"Updated recent playlist '{playlist_name}' with {len(songs_to_add)} songs")
            except:
                # Playlist doesn't exist, create it
                playlist = plex.createPlaylist(playlist_name, items=songs_to_add)
                logger.info(f"Created recent playlist '{playlist_name}' with {len(songs_to_add)} songs")

        elif mode == 'random':
            # Random mode: replace with random songs
            # Works like replace - clear old list, add new random songs
            try:
                playlist = plex.playlist(playlist_name)
                playlist.removeItems(playlist.items())
                playlist.addItems(songs_to_add)
                logger.info(f"Updated random playlist '{playlist_name}' with {len(songs_to_add)} songs")
            except:
                # Playlist doesn't exist, create it
                playlist = plex.createPlaylist(playlist_name, items=songs_to_add)
                logger.info(f"Created random playlist '{playlist_name}' with {len(songs_to_add)} songs")

        else:
            logger.error(f"Unknown playlist mode: {mode}")
            return {
                'added': 0,
                'not_found': len(not_found),
                'not_found_list': not_found,
                'error': f"Unknown mode: {mode}",
                'excluded_by_blocklist': excluded_by_blocklist
            }

    except Exception as e:
        logger.error(f"Error creating/updating playlist: {e}")
        return {
            'added': 0,
            'not_found': len(not_found),
            'not_found_list': not_found,
            'error': str(e),
            'excluded_by_blocklist': excluded_by_blocklist
        }

    # Report not found songs
    if not_found:
        logger.warning(f"{len(not_found)} songs not found in Plex library")
        for song_id, song_title, artist_name in not_found[:10]:
            logger.warning(f"  - {song_title} - {artist_name}")
        if len(not_found) > 10:
            logger.warning(f"  ... and {len(not_found) - 10} more")

    # Convert not_found tuples to dicts for JSON response
    not_found_list = [
        {'song_id': song_id, 'song_title': song_title, 'artist_name': artist_name}
        for song_id, song_title, artist_name in not_found
    ]

    result = {
        'added': len(songs_to_add),
        'not_found': len(not_found),
        'not_found_list': not_found_list,
        'excluded_by_blocklist': excluded_by_blocklist
    }

    # Log activity
    try:
        from radio_monitor.database.activity import log_activity
        severity = 'success' if len(not_found) == 0 else 'warning' if len(not_found) < len(songs) else 'error'
        log_activity(
            db.get_cursor(),
            event_type='playlist_update',
            title=f"Playlist updated: {playlist_name} ({mode})",
            description=f"Added {len(songs_to_add)} songs to '{playlist_name}' ({len(not_found)} not found)",
            metadata={
                'playlist_name': playlist_name,
                'mode': mode,
                'added': len(songs_to_add),
                'not_found': len(not_found),
                'days': days,
                'limit': limit
            },
            severity=severity,
            source='user'
        )
    except Exception as e:
        logger.error(f"Failed to log playlist activity: {e}")

    # Send notifications
    try:
        from radio_monitor.notifications import send_notifications
        logger.info(f"Sending playlist notifications: error={bool(result.get('error'))}, added={result.get('added', 0)}, not_found={result.get('not_found', 0)}")

        if not result.get('error'):
            logger.info(f"Sending on_playlist_update notification for '{playlist_name}'")
            sent = send_notifications(
                db,
                'on_playlist_update',
                f'Playlist Updated: {playlist_name}',
                f"Added {result['added']} songs to '{playlist_name}' ({result['not_found']} not found in Plex)",
                'success' if result['not_found'] == 0 else 'warning',
                {
                    'playlist_name': playlist_name,
                    'mode': mode,
                    'added': result['added'],
                    'not_found': result['not_found']
                }
            )
            logger.info(f"on_playlist_update notification sent to {sent} provider(s)")
        else:
            logger.info(f"Sending on_playlist_error notification for '{playlist_name}': {result.get('error')}")
            sent = send_notifications(
                db,
                'on_playlist_error',
                f'Playlist Error: {playlist_name}',
                result.get('error', 'Failed to create/update playlist'),
                'error',
                {'playlist_name': playlist_name, 'mode': mode}
            )
            logger.info(f"on_playlist_error notification sent to {sent} provider(s)")
    except Exception as e:
        logger.error(f"Failed to send playlist notifications: {e}", exc_info=True)

    return result


def test_matching(db, plex, test_songs_file=None, songs=None):
    """Test Plex fuzzy matching

    Args:
        db: RadioDatabase instance
        plex: PlexServer instance
        test_songs_file: Path to file with test songs (one per line: "artist - song")
        songs: List of (artist, song) tuples (alternative to test_songs_file)

    Returns:
        dict with:
        - total: Total songs tested
        - found: Number found in Plex
        - not_found: Number not found
        - match_rate: Percentage found
        - not_found_list: List of (song_title, artist_name) tuples
    """
    if test_songs_file:
        # Load test songs from file
        test_songs = []
        with open(test_songs_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '-' in line:
                    parts = line.split('-', 1)
                    if len(parts) == 2:
                        artist = parts[0].strip()
                        song = parts[1].strip()
                        test_songs.append((artist, song))
    elif songs:
        test_songs = songs
    else:
        # Use top songs from database
        top_songs = db.get_top_songs(limit=20)
        test_songs = [(artist, song) for song, artist, _ in top_songs]

    # Get music library
    music_library_name = 'Music'
    try:
        music_library = plex.library.section(music_library_name)
    except Exception as e:
        logger.error(f"Error accessing Plex music library: {e}")
        return {
            'total': 0,
            'found': 0,
            'not_found': 0,
            'match_rate': 0,
            'not_found_list': [],
            'error': str(e)
        }

    # Test matching
    found = 0
    not_found_list = []

    for artist_name, song_title in test_songs:
        track = find_song_in_library(music_library, song_title, artist_name, debug=True)

        if track:
            found += 1
            print(f"[OK] {song_title} - {artist_name}")
        else:
            not_found_list.append((song_title, artist_name))
            print(f"[NOT FOUND] {song_title} - {artist_name}")

    total = len(test_songs)
    match_rate = (found / total * 100) if total > 0 else 0

    print(f"\nMatch rate: {found}/{total} ({match_rate:.1f}%)")

    return {
        'total': total,
        'found': found,
        'not_found': total - found,
        'match_rate': match_rate,
        'not_found_list': not_found_list
    }


def update_playlists_from_config(db, plex, config_file, settings):
    """Update multiple playlists from config file

    Args:
        db: RadioDatabase instance
        plex: PlexServer instance
        config_file: Path to JSON config file
        settings: Settings dict with default music_library_name

    Returns:
        List of result dicts from create_playlist()
    """
    import json

    with open(config_file, 'r', encoding='utf-8') as f:
        playlists = json.load(f)

    results = []

    for playlist_config in playlists:
        name = playlist_config.get('name', 'Playlist')
        mode = playlist_config.get('mode', 'merge')
        days = playlist_config.get('days', 7)
        limit = playlist_config.get('limit', 50)
        station_id = playlist_config.get('station', None)

        filters = {
            'days': days,
            'limit': limit,
            'station_id': station_id,
            'music_library_name': settings.get('plex', {}).get('music_library_name', 'Music')
        }

        print(f"\nProcessing playlist: {name} (mode: {mode})")
        result = create_playlist(db, plex, name, mode, filters)
        results.append(result)

        if result.get('error'):
            print(f"  Error: {result['error']}")
        else:
            print(f"  Added: {result['added']}, Not found: {result['not_found']}")

    return results


def get_plex_libraries(settings):
    """Get available music libraries from Plex

    Args:
        settings: Settings dict with plex configuration

    Returns:
        List of library dicts with 'name' and 'key', or None
    """
    try:
        from plexapi.server import PlexServer

        plex_url = settings.get('plex', {}).get('url', 'http://localhost:32400')
        token = settings.get('plex', {}).get('token', '')

        if not token:
            logger.error("No Plex token configured")
            return None

        plex = PlexServer(plex_url, token, timeout=10)

        # Get all libraries
        libraries = []
        for lib in plex.library.sections():
            # Only include music libraries
            if lib.type == 'artist':
                libraries.append({
                    'name': lib.title,
                    'key': str(lib.key)
                })

        logger.info(f"Found {len(libraries)} music libraries in Plex")
        return libraries

    except Exception as e:
        logger.error(f"Error getting Plex libraries: {e}")
        return None


def test_plex_connection(settings):
    """Test connection to Plex

    Args:
        settings: Settings dict with plex configuration

    Returns:
        (success, message) tuple
    """
    try:
        from plexapi.server import PlexServer

        plex_url = settings.get('plex', {}).get('url', 'http://localhost:32400')
        token = settings.get('plex', {}).get('token', '')

        if not token:
            return False, "No Plex token configured"

        # Add explicit timeout
        plex = PlexServer(plex_url, token, timeout=(5, 10))

        # Get server info
        server_name = plex.friendlyName
        version = plex.version

        return True, f"Connected to {server_name} (Plex {version})"

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Plex connection error: {e}")

        # Provide helpful error messages
        if "Connection refused" in error_msg or "Errno 111" in error_msg or "Errno 61" in error_msg:
            return False, "Connection refused - Is Plex running?"
        elif "401" in error_msg or "Unauthorized" in error_msg:
            return False, "Authentication failed - Check your token"
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            return False, "Connection timeout - Is Plex responding?"
        else:
            return False, f"Connection failed: {error_msg}"


# ==================== MANUAL PLAYLIST FUNCTIONS (Phase 7) ====================

def get_plex_server(settings):
    """Get Plex server instance from settings

    Args:
        settings: Settings dict with plex configuration

    Returns:
        PlexServer instance or None
    """
    try:
        from plexapi.server import PlexServer

        plex_url = settings.get('plex', {}).get('url', 'http://localhost:32400')
        token = settings.get('plex', {}).get('token', '')

        if not token:
            logger.error("No Plex token configured")
            return None

        plex = PlexServer(plex_url, token, timeout=30)
        return plex

    except Exception as e:
        logger.error(f"Error connecting to Plex: {e}")
        return None


def create_plex_manual_playlist(playlist_name, songs, plex_url, plex_token, music_library_name='Music'):
    """Create manual playlist in Plex

    Args:
        playlist_name: Name of playlist to create
        songs: List of dicts with 'title' and 'artist_name' keys
        plex_url: Plex server URL
        plex_token: Plex server token
        music_library_name: Name of music library in Plex

    Returns:
        dict with:
        - success: True/False
        - added: Number of songs added
        - not_found: Number of songs not found
        - not_found_list: List of songs not found
        - error: Error message (if any)
    """
    try:
        from plexapi.server import PlexServer

        # Connect to Plex
        plex = PlexServer(plex_url, plex_token, timeout=30)

        # Get music library
        try:
            music_library = plex.library.section(music_library_name)
        except Exception as e:
            logger.error(f"Error accessing Plex music library '{music_library_name}': {e}")
            return {
                'success': False,
                'added': 0,
                'not_found': len(songs),
                'not_found_list': songs,
                'error': f"Music library '{music_library_name}' not found"
            }

        # Find songs in Plex
        songs_to_add = []
        not_found = []

        for idx, song in enumerate(songs, 1):
            song_title = song.get('title')
            artist_name = song.get('artist_name')

            if not song_title or not artist_name:
                logger.warning(f"Skipping song {idx}: missing title or artist")
                not_found.append(song)
                continue

            logger.info(f"Processing song {idx}/{len(songs)}: {song_title} - {artist_name}")

            # Use existing fuzzy matching function
            track = find_song_in_library(music_library, song_title, artist_name, debug=False)

            if track:
                songs_to_add.append(track)
                logger.info(f"  ✓ Found: {track.title}")
            else:
                not_found.append(song)
                logger.warning(f"  ✗ Not found in Plex: {song_title} - {artist_name}")

        logger.info(f"Finished searching Plex: found {len(songs_to_add)}/{len(songs)} songs")

        # Create playlist in Plex
        if songs_to_add:
            playlist = plex.createPlaylist(playlist_name, items=songs_to_add)
            logger.info(f"Created Plex playlist '{playlist_name}' with {len(songs_to_add)} songs")
        else:
            logger.error(f"No songs found in Plex for playlist '{playlist_name}'")
            return {
                'success': False,
                'added': 0,
                'not_found': len(not_found),
                'not_found_list': not_found,
                'error': 'No songs found in Plex library'
            }

        # Return result
        result = {
            'success': True,
            'added': len(songs_to_add),
            'not_found': len(not_found),
            'not_found_list': not_found
        }

        # Log warning if some songs not found
        if not_found:
            logger.warning(f"{len(not_found)} songs not found in Plex for playlist '{playlist_name}'")

        return result

    except Exception as e:
        logger.error(f"Error creating Plex playlist: {e}")
        return {
            'success': False,
            'added': 0,
            'not_found': len(songs),
            'not_found_list': songs,
            'error': str(e)
        }


def update_plex_manual_playlist(playlist_name, songs, plex_url, plex_token, old_playlist_name=None, music_library_name='Music'):
    """Update manual playlist in Plex (delete and recreate)

    Args:
        playlist_name: Name of playlist to create/update
        songs: List of dicts with 'title' and 'artist_name' keys
        plex_url: Plex server URL
        plex_token: Plex server token
        old_playlist_name: Old playlist name (if different from new name)
        music_library_name: Name of music library in Plex

    Returns:
        dict with:
        - success: True/False
        - added: Number of songs added
        - not_found: Number of songs not found
        - not_found_list: List of songs not found
        - error: Error message (if any)
    """
    try:
        from plexapi.server import PlexServer

        # Connect to Plex
        plex = PlexServer(plex_url, plex_token, timeout=30)

        # Delete old playlist if exists
        playlist_to_delete = old_playlist_name or playlist_name

        try:
            existing_playlist = plex.playlist(playlist_to_delete)
            logger.info(f"Deleting existing Plex playlist '{playlist_to_delete}'")
            existing_playlist.delete()
        except:
            # Playlist doesn't exist, that's fine
            logger.info(f"Playlist '{playlist_to_delete}' not found in Plex (will create new)")

        # Create new playlist
        result = create_plex_manual_playlist(playlist_name, songs, plex_url, plex_token, music_library_name)

        return result

    except Exception as e:
        logger.error(f"Error updating Plex playlist: {e}")
        return {
            'success': False,
            'added': 0,
            'not_found': len(songs),
            'not_found_list': songs,
            'error': str(e)
        }


def create_or_update_manual_playlist(playlist_name, songs, plex_url, plex_token, music_library_name='Music'):
    """Create or update manual playlist in Plex using replace mode

    This uses the same approach as auto playlists - clears existing playlist
    and adds new songs, rather than deleting and recreating.

    Args:
        playlist_name: Name of playlist to create/update
        songs: List of dicts with 'title' and 'artist_name' keys
        plex_url: Plex server URL
        plex_token: Plex server token
        music_library_name: Name of music library in Plex

    Returns:
        dict with:
        - success: True/False
        - added: Number of songs added
        - not_found: Number of songs not found
        - not_found_list: List of songs not found
        - error: Error message (if any)
    """
    try:
        from plexapi.server import PlexServer

        # Connect to Plex
        plex = PlexServer(plex_url, plex_token, timeout=30)

        # Get music library
        try:
            music_library = plex.library.section(music_library_name)
        except Exception as e:
            logger.error(f"Error accessing Plex music library '{music_library_name}': {e}")
            return {
                'success': False,
                'added': 0,
                'not_found': len(songs),
                'not_found_list': songs,
                'error': f"Music library '{music_library_name}' not found"
            }

        # Find songs in Plex
        songs_to_add = []
        not_found = []

        for idx, song in enumerate(songs, 1):
            song_title = song.get('title')
            artist_name = song.get('artist_name')

            if not song_title or not artist_name:
                logger.warning(f"Skipping song {idx}: missing title or artist")
                not_found.append(song)
                continue

            # Find track in Plex library
            track = find_song_in_library(music_library, song_title, artist_name)

            if track:
                songs_to_add.append(track)
            else:
                logger.debug(f"Song not found in Plex: {song_title} - {artist_name}")
                not_found.append(song)

        # Create or update playlist using replace mode (same as auto playlists)
        try:
            # Try to get existing playlist
            playlist = plex.playlist(playlist_name)
            # Remove all existing items
            playlist.removeItems(playlist.items())
            # Add new items
            playlist.addItems(songs_to_add)
            logger.info(f"Updated manual playlist '{playlist_name}' with {len(songs_to_add)} songs")
        except:
            # Playlist doesn't exist, create it
            playlist = plex.createPlaylist(playlist_name, items=songs_to_add)
            logger.info(f"Created manual playlist '{playlist_name}' with {len(songs_to_add)} songs")

        return {
            'success': True,
            'added': len(songs_to_add),
            'not_found': len(not_found),
            'not_found_list': not_found
        }

    except Exception as e:
        logger.error(f"Error creating/updating manual playlist in Plex: {e}")
        return {
            'success': False,
            'added': 0,
            'not_found': len(songs),
            'not_found_list': songs,
            'error': str(e)
        }


def delete_plex_playlist(playlist_name, plex_url, plex_token):
    """Delete playlist from Plex

    Args:
        playlist_name: Name of playlist to delete
        plex_url: Plex server URL
        plex_token: Plex server token

    Returns:
        dict with:
        - success: True/False
        - error: Error message (if any)
    """
    try:
        from plexapi.server import PlexServer

        # Connect to Plex
        plex = PlexServer(plex_url, plex_token, timeout=30)

        # Find and delete playlist
        try:
            playlist = plex.playlist(playlist_name)
            playlist.delete()
            logger.info(f"Deleted Plex playlist '{playlist_name}'")
            return {'success': True}
        except:
            # Playlist doesn't exist
            logger.warning(f"Playlist '{playlist_name}' not found in Plex")
            return {'success': True, 'message': 'Playlist not found (may have been already deleted)'}

    except Exception as e:
        logger.error(f"Error deleting Plex playlist: {e}")
        return {
            'success': False,
            'error': str(e)
        }
