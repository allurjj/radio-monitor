"""
MBID Lookup module for Radio Monitor 1.0

This module handles MusicBrainz API lookups for artist MBIDs:
- MusicBrainz API client with proper User-Agent (contact info required)
- Rate limiting: 1 request/second (well under MusicBrainz's 50/sec limit)
- Database caching (avoid repeated lookups)
- Error handling with retry (10 retries with exponential backoff)
- Retry logic for failed lookups

Key Principle: Only artists with MBIDs are stored in the database.
Songs without MBIDs are skipped during scraping.

IMPORTANT: MusicBrainz requires User-Agent to include contact information.
Update musicbrainz.user_agent in radio_monitor_settings.json with your email or GitHub URL.
"""

import urllib.request
import urllib.error
import json
import time
import logging
import ssl
import re
from difflib import SequenceMatcher

# Get logger (will be configured properly in Phase 8)
logger = logging.getLogger(__name__)


# Similarity threshold for artist name matching (80%)
# Allows for minor variations but rejects major mismatches
NAME_SIMILARITY_THRESHOLD = 0.80

# Borderline threshold for logging warnings (70-80%)
NAME_SIMILARITY_WARNING = 0.70


def calculate_similarity(str1, str2):
    """Calculate string similarity using SequenceMatcher

    Args:
        str1: First string
        str2: Second string

    Returns:
        Float between 0.0 (no match) and 1.0 (perfect match)
    """
    # Normalize: lowercase, strip whitespace
    str1_norm = str1.lower().strip()
    str2_norm = str2.lower().strip()

    return SequenceMatcher(None, str1_norm, str2_norm).ratio()


# ==================== SAFE MATCHING FUNCTIONS ====================

def extract_words(text):
    """Extract individual words from text, removing punctuation and special chars

    Args:
        text: Text to extract words from

    Returns:
        List of lowercase words
    """
    if not text:
        return []

    # Remove special characters but keep spaces
    cleaned = re.sub(r'[^\w\s]', ' ', text.lower())
    # Split on whitespace and filter empty strings
    words = [w for w in cleaned.split() if w and len(w) > 1]

    return words


def has_word_overlap(our_artist, their_artist, min_words=1):
    """Check if our artist name has word overlap with their artist name

    This prevents bad matches like:
    - "Paul Russell" -> "Paul Smith" (only "Paul" matches)
    - "Toadies" -> "The Go-Betweens" (no meaningful overlap)

    Args:
        our_artist: Our artist name (from database/scraper)
        their_artist: Their artist name (from MusicBrainz)
        min_words: Minimum number of words that must overlap (default: 1)

    Returns:
        bool: True if sufficient word overlap exists
    """
    our_words = extract_words(our_artist)
    their_words = extract_words(their_artist)

    if not our_words or not their_words:
        return False

    # Find matching words (case-insensitive)
    our_set = set(our_words)
    their_set = set(their_words)

    # Count meaningful word overlaps (words longer than 2 chars)
    overlaps = our_set.intersection(their_set)
    meaningful_overlaps = [w for w in overlaps if len(w) > 2]

    # Require minimum word overlap
    has_enough = len(meaningful_overlaps) >= min_words

    if has_enough:
        logger.debug(
            f"Word overlap found: '{our_artist}' vs '{their_artist}' "
            f"(matches: {meaningful_overlaps})"
        )

    return has_enough


def safe_artist_match(our_artist, their_artist, threshold=NAME_SIMILARITY_THRESHOLD):
    """Determine if two artist names match safely

    This combines string similarity with word overlap verification
    to prevent bad matches while allowing for legitimate variations.

    Args:
        our_artist: Our artist name (from database/scraper)
        their_artist: Their artist name (from MusicBrainz)
        threshold: Minimum similarity threshold (default: 0.80)

    Returns:
        tuple: (is_match: bool, reason: str)
    """
    # Check for exact match (case-insensitive)
    if our_artist.lower().strip() == their_artist.lower().strip():
        return True, "exact match"

    # Calculate string similarity
    similarity = calculate_similarity(our_artist, their_artist)

    # Check word overlap
    word_overlap = has_word_overlap(our_artist, their_artist, min_words=1)

    # Decision logic
    if similarity >= 0.95:
        # Very high similarity - accept even without perfect word overlap
        # (handles cases like "Mary J Blige" vs "Mary J. Blige")
        if word_overlap:
            return True, "excellent match with overlap"
        else:
            # Even with high similarity, require some word overlap for safety
            return False, f"high similarity but no word overlap ({similarity:.1%})"

    elif similarity >= threshold:
        # Good similarity - require word overlap
        if word_overlap:
            return True, "good match with overlap"
        else:
            return False, f"good similarity but no word overlap ({similarity:.1%})"

    else:
        # Below threshold - reject regardless of word overlap
        return False, f"below similarity threshold ({similarity:.1%})"


def split_collaboration_artist(artist_name):
    """Split a collaboration artist string into individual artists

    This handles cases like "Marshmello Kane Brown Joel Corry" which might be
    a collaboration or remix that should match individual artists.

    Args:
        artist_name: Artist name that might be a collaboration

    Returns:
        list: Individual artist names found
    """
    # Try common collaboration separators first
    separators = [' & ', ' + ', ' x ', ' vs. ', ' ft.', ' feat ', ' with ']

    for sep in separators:
        if sep in artist_name.lower():
            # Split by this separator
            parts = artist_name.split(sep)
            # Clean up each part
            artists = [part.strip() for part in parts if part.strip()]
            if len(artists) > 1:
                return artists

    # If no explicit separators, try intelligent word grouping
    words = extract_words(artist_name)

    # Simple heuristic: if we have 4+ words, it's likely a collaboration
    # Group into 2-word artist names (most common pattern)
    if len(words) >= 4:
        artists = []
        for i in range(0, len(words), 2):
            # Take 2 words at a time
            if i + 1 < len(words):
                artist = f"{words[i].capitalize()} {words[i+1].capitalize()}"
                artists.append(artist)
            else:
                # Odd number of words, take the last one
                artists.append(words[i].capitalize())

        if len(artists) > 1:
            return artists

    # No collaboration detected
    return [artist_name]


def safe_collaboration_match(our_collaboration, their_artist, threshold=NAME_SIMILARITY_THRESHOLD):
    """Check if a collaboration artist matches a single artist

    This handles cases like "Marshmello Kane Brown Joel Corry" vs "Marshmello"
    by checking if any component of our collaboration matches their artist.

    Args:
        our_collaboration: Our collaboration artist (e.g., "Marshmello Kane Brown Joel Corry")
        their_artist: Their single artist (e.g., "Marshmello")
        threshold: Minimum similarity threshold (default: 0.80)

    Returns:
        tuple: (is_match: bool, reason: str, matched_component: str or None)
    """
    # First, try explicit collaboration splitting
    our_components = split_collaboration_artist(our_collaboration)

    if len(our_components) > 1:
        # Check each component against their artist
        for component in our_components:
            # Remove any remaining separators from component
            component_clean = component.strip(' &+x')

            # Try to match this component
            is_match, reason = safe_artist_match(component_clean, their_artist, threshold)

            if is_match:
                logger.info(
                    f"Collaboration match: '{our_collaboration}' matched '{their_artist}' "
                    f"via component '{component_clean}'"
                )
                return True, f"collaboration component match ({reason})", component_clean

    # If explicit splitting didn't work, try word overlap
    # But be strict to prevent bad matches
    our_words = extract_words(our_collaboration)
    their_words = extract_words(their_artist)

    # Check if any significant word overlaps (5+ chars, 40% significance)
    for our_word in our_words:
        if len(our_word) < 5:  # Skip short words
            continue

        if our_word in their_words:
            # Found a word overlap! Check if it's meaningful
            our_char_count = len(''.join(our_words))
            their_char_count = len(''.join(their_words))

            our_ratio = len(our_word) / our_char_count if our_char_count > 0 else 0
            their_ratio = len(our_word) / their_char_count if their_char_count > 0 else 0

            # Require 40% significance in BOTH names
            if our_ratio >= 0.4 and their_ratio >= 0.4:
                logger.info(
                    f"Collaboration word overlap: '{our_collaboration}' matched '{their_artist}' "
                    f"via word '{our_word}'"
                )
                return True, f"collaboration word overlap ({our_word})", our_word

    # No collaboration match found
    return False, "no collaboration component matched", None


# ==================== END SAFE MATCHING FUNCTIONS ====================


def lookup_artist_mbid(artist_name, db, user_agent=None, max_retries=10, auto_retry_pending=True):
    """Look up artist MBID from MusicBrainz API with caching and retry logic

    This function implements a multi-tier lookup strategy:
    1. Check database cache (artists table)
    2. If cached MBID is PENDING → auto-retry (if enabled)
    3. If cached MBID is NULL → retry lookup
    4. If not in cache → query MusicBrainz API (with retry on SSL errors)
    5. Use fuzzy name matching to validate results (80% similarity threshold)

    Args:
        artist_name: Artist name to look up
        db: RadioDatabase instance
        user_agent: Custom User-Agent string (optional)
        max_retries: Maximum number of retry attempts (default: 10)
        auto_retry_pending: Auto-retry PENDING MBIDs (default: True)

    Returns:
        Tuple of (mbid: str or None, verified_name: str or None)
        - mbid: MusicBrainz ID if found, None if not found
        - verified_name: Canonical artist name from MusicBrainz (or database), None if not found

    Flow:
        1. Check if artist exists in database
        2. If exists and has real MBID → return cached MBID and database name
        3. If exists and has PENDING MBID → auto-retry lookup
        4. If exists but MBID is NULL → retry lookup
        5. If not in database → query MusicBrainz API
        6. On connection error: retry quickly (0.7s, 0.9s, 1.1s, 1.3s... increasing)
        7. Rate limit: 1 second between requests (0.5s before + 0.5s after)
        8. Short timeout (5s) - fail fast on connection issues
        9. Validate artist name with fuzzy matching (80% threshold)
        10. Return (MBID, verified_name) or (None, None) if not found
    """
    # Check cache first
    artist = db.get_artist_by_name(artist_name)

    if artist:
        artist_mbid = artist['mbid']
        if artist_mbid:
            # Check if it's a PENDING MBID
            if artist_mbid.startswith('PENDING-'):
                if auto_retry_pending:
                    logger.info(f"Found PENDING MBID for {artist_name} - auto-retrying lookup")
                    # Clear the PENDING MBID temporarily to force re-lookup
                    db.update_artist_mbid_from_pending(artist_name, None)
                # else: Continue to MusicBrainz lookup (don't return None)
                # This allows manual retry via --retry-pending command
            else:
                # Valid cached MBID found
                logger.debug(f"Using cached MBID for {artist_name}: {artist_mbid}")
                # Return cached MBID and the artist's name from database
                return artist_mbid, artist.get('name')
        else:
            # Artist exists but MBID is NULL - retry lookup
            logger.info(f"Retrying MBID lookup for {artist_name}")
    else:
        # New artist - will be added after MBID lookup
        logger.debug(f"New artist: {artist_name} - looking up MBID")

    # Query MusicBrainz API with retry logic
    from urllib.parse import quote
    encoded_artist = quote(artist_name, safe='')

    # Increase limit to get more results for exact matching
    # (Don't filter by type because some artists are bands/groups)
    url = f"https://musicbrainz.org/ws/2/artist/?query=artist:{encoded_artist}&fmt=json&limit=10"

    # Set User-Agent (MusicBrainz requirement: must include app name and contact)
    # Using proper format to avoid rate limiting (Usage limit: 1 request/second)
    headers = {
        'User-Agent': user_agent or 'RadioMonitor/1.0.0 (https://github.com/allurjj/radio-monitor)'
    }

    # Retry loop for connection errors
    for attempt in range(max_retries):
        try:
            # Add delay before request to avoid overwhelming MusicBrainz
            # MusicBrainz allows 50/sec with proper User-Agent, we use 1/sec to be safe
            if attempt > 0:
                # For retries, use exponential backoff (fail fast, retry more)
                time.sleep(0.5 + (attempt * 0.2))  # 0.7s, 0.9s, 1.1s, 1.3s...
            else:
                # First attempt - minimal delay to space out requests
                time.sleep(0.5)

            # Create SSL context with proper certificate verification
            # MusicBrainz requires valid SSL certificates
            ssl_context = ssl.create_default_context()

            req = urllib.request.Request(url, headers=headers)

            # Shorter timeout (5s) - fail fast if connection is bad
            with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
                # Rate limiting - wait after successful request
                # (Total delay: 0.5s before + 0.5s after = 1 second between requests)
                time.sleep(0.5)

                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))

                    if data.get('artists'):
                        # Check all results to find best match
                        # Prioritize exact matches (case-insensitive) over fuzzy matches
                        best_match = None
                        best_similarity = 0.0
                        exact_match_found = False

                        for result in data['artists']:
                            result_mbid = result['id']
                            result_name = result.get('name', '')

                            # Check for exact match first (case-insensitive)
                            if result_name.lower() == artist_name.lower():
                                best_match = (result_mbid, result_name)
                                best_similarity = 1.0
                                exact_match_found = True
                                logger.debug(f"Found exact match: {result_name}")
                                break  # Stop searching, we found an exact match!

                            # No exact match, calculate similarity
                            similarity = calculate_similarity(artist_name, result_name)
                            logger.debug(f"Checking {artist_name} vs {result_name}: {similarity:.2%} similarity")

                            if similarity > best_similarity:
                                best_similarity = similarity
                                best_match = (result_mbid, result_name)

                        # ENHANCED: Use safe matching with word overlap verification
                        if exact_match_found:
                            # Exact match - accept immediately
                            mbid, matched_name = best_match
                            logger.info(f"Found MBID for {artist_name}: {mbid} (exact match)")

                            # Update database if artist exists with NULL or PENDING MBID
                            if artist and mbid:  # Only update if we found a match
                                if artist['mbid'] is None or artist['mbid'].startswith('PENDING-'):
                                    # Check if MBID already exists in database (prevent UNIQUE constraint violation)
                                    existing_with_mbid = db.get_artist_by_mbid(mbid)

                                    if existing_with_mbid:
                                        # MBID already exists with different artist name
                                        # This means we found a duplicate! Merge the PENDING artist into the real one.
                                        logger.info(
                                            f"MBID {mbid} already exists for artist '{existing_with_mbid['name']}'. "
                                            f"Merging '{artist_name}' into '{existing_with_mbid['name']}' to resolve duplicate."
                                        )

                                        # Import the merge function
                                        from radio_monitor.database.crud import merge_pending_artist_into_existing

                                        # Perform the merge
                                        merge_success = merge_pending_artist_into_existing(
                                            cursor=db.get_cursor(),
                                            conn=db.conn,
                                            pending_artist_name=artist_name,
                                            existing_mbid=existing_with_mbid['mbid'],
                                            existing_artist_name=existing_with_mbid['name']
                                        )

                                        if merge_success:
                                            logger.info(f"Successfully merged {artist_name} into {existing_with_mbid['name']}")
                                            # Return the existing artist's MBID and name
                                            return existing_with_mbid['mbid'], existing_with_mbid['name']
                                        else:
                                            logger.warning(f"Merge failed for {artist_name}, returning existing artist info")
                                            # Return the existing artist's MBID and name anyway
                                            return existing_with_mbid['mbid'], existing_with_mbid['name']

                                    # Safe to update - MBID doesn't exist yet
                                    db.update_artist_mbid_from_pending(artist_name, mbid)
                                    logger.debug(f"Updated MBID in database for {artist_name}")

                            return mbid, matched_name

                        elif best_similarity >= NAME_SIMILARITY_THRESHOLD:
                            # Potential match - verify with safety checks
                            is_safe, safety_reason = safe_artist_match(artist_name, best_match[1], NAME_SIMILARITY_THRESHOLD)

                            if is_safe:
                                mbid, matched_name = best_match
                                logger.info(
                                    f"Found MBID for {artist_name}: {mbid} "
                                    f"(matched: {matched_name}, {best_similarity:.1%} similarity, {safety_reason})"
                                )

                                # Warn on borderline matches (70-80%)
                                if NAME_SIMILARITY_WARNING <= best_similarity < NAME_SIMILARITY_THRESHOLD:
                                    logger.warning(f"Borderline match: {artist_name} -> {matched_name} ({best_similarity:.1%}) - please verify")

                                # Update database if artist exists with NULL or PENDING MBID
                                if artist:
                                    if artist['mbid'] is None or artist['mbid'].startswith('PENDING-'):
                                        # Check if MBID already exists in database (prevent UNIQUE constraint violation)
                                        existing_with_mbid = db.get_artist_by_mbid(mbid)

                                        if existing_with_mbid:
                                            # MBID already exists with different artist name
                                            # This means we found a duplicate! Merge the PENDING artist into the real one.
                                            logger.info(
                                                f"MBID {mbid} already exists for artist '{existing_with_mbid['name']}'. "
                                                f"Merging '{artist_name}' into '{existing_with_mbid['name']}' to resolve duplicate."
                                            )

                                            # Import the merge function
                                            from radio_monitor.database.crud import merge_pending_artist_into_existing

                                            # Perform the merge
                                            merge_success = merge_pending_artist_into_existing(
                                                cursor=db.get_cursor(),
                                                conn=db.conn,
                                                pending_artist_name=artist_name,
                                                existing_mbid=existing_with_mbid['mbid'],
                                                existing_artist_name=existing_with_mbid['name']
                                            )

                                            if merge_success:
                                                logger.info(f"Successfully merged {artist_name} into {existing_with_mbid['name']}")
                                                # Return the existing artist's MBID and name
                                                return existing_with_mbid['mbid'], existing_with_mbid['name']
                                            else:
                                                logger.warning(f"Merge failed for {artist_name}, returning existing artist info")
                                                # Return the existing artist's MBID and name anyway
                                                return existing_with_mbid['mbid'], existing_with_mbid['name']

                                        # Safe to update - MBID doesn't exist yet
                                        db.update_artist_mbid_from_pending(artist_name, mbid)
                                        logger.debug(f"Updated MBID in database for {artist_name}")

                                return mbid, matched_name

                            else:
                                # Failed safety check - try collaboration matching
                                logger.debug(f"Standard matching failed: {safety_reason}, trying collaboration match...")

                                is_collab_match, collab_reason, matched_component = safe_collaboration_match(
                                    artist_name, best_match[1], NAME_SIMILARITY_THRESHOLD
                                )

                                if is_collab_match:
                                    mbid, matched_name = best_match
                                    logger.info(
                                        f"Found MBID for {artist_name}: {mbid} "
                                        f"(collaboration match: {matched_name}, {best_similarity:.1%} similarity, {collab_reason})"
                                    )

                                    # Update database if artist exists with NULL or PENDING MBID
                                    if artist:
                                        if artist['mbid'] is None or artist['mbid'].startswith('PENDING-'):
                                            # Check if MBID already exists in database (prevent UNIQUE constraint violation)
                                            existing_with_mbid = db.get_artist_by_mbid(mbid)

                                            if existing_with_mbid:
                                                # MBID already exists with different artist name
                                                # This means we found a duplicate! Merge the PENDING artist into the real one.
                                                logger.info(
                                                    f"MBID {mbid} already exists for artist '{existing_with_mbid['name']}'. "
                                                    f"Merging '{artist_name}' into '{existing_with_mbid['name']}' to resolve duplicate."
                                                )

                                                # Import the merge function
                                                from radio_monitor.database.crud import merge_pending_artist_into_existing

                                                # Perform the merge
                                                merge_success = merge_pending_artist_into_existing(
                                                    cursor=db.get_cursor(),
                                                    conn=db.conn,
                                                    pending_artist_name=artist_name,
                                                    existing_mbid=existing_with_mbid['mbid'],
                                                    existing_artist_name=existing_with_mbid['name']
                                                )

                                                if merge_success:
                                                    logger.info(f"Successfully merged {artist_name} into {existing_with_mbid['name']}")
                                                    # Return the existing artist's MBID and name
                                                    return existing_with_mbid['mbid'], existing_with_mbid['name']
                                                else:
                                                    logger.warning(f"Merge failed for {artist_name}, returning existing artist info")
                                                    # Return the existing artist's MBID and name anyway
                                                    return existing_with_mbid['mbid'], existing_with_mbid['name']

                                            # Safe to update - MBID doesn't exist yet
                                            db.update_artist_mbid_from_pending(artist_name, mbid)
                                            logger.debug(f"Updated MBID in database for {artist_name}")

                                    return mbid, matched_name

                                else:
                                    # All matching attempts failed
                                    logger.warning(
                                        f"No good match found for {artist_name} "
                                        f"(best: {best_match[1]} at {best_similarity:.1%}) - {safety_reason}, {collab_reason}"
                                    )
                                    # Continue to next section (below threshold handling)
                        else:
                            # Below similarity threshold - reject all results
                            logger.warning(
                                f"No good match found for {artist_name} "
                                f"(best: {best_match[1] if best_match else 'N/A'} at {best_similarity:.1%})"
                            )
                            return None, None

                elif response.status == 404:
                    # Not found
                    logger.warning(f"No MBID found for {artist_name} (HTTP 404)")
                    return None, None
                else:
                    # Other error
                    logger.error(f"MusicBrainz API error for {artist_name}: HTTP {response.status}")
                    return None, None

        except urllib.error.URLError as e:
            # SSL, EOF, and connection errors - retry with exponential backoff
            if 'SSL' in str(e) or 'EOF' in str(e) or '10054' in str(e) or 'forcibly closed' in str(e).lower():
                # Network/Connection error - retry
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + 2  # 3s, 4s, 6s (slightly longer)
                    logger.warning(f"MusicBrainz connection error for {artist_name} (attempt {attempt + 1}/{max_retries}): {e}")
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"MusicBrainz connection error for {artist_name} after {max_retries} attempts: {e}")
                    return None, None
            else:
                # Other URL errors - don't retry
                logger.error(f"MusicBrainz API request failed for {artist_name}: {e}")
                return None, None

        except urllib.error.URLError as e:
            # Other URL errors
            if hasattr(e, 'reason'):
                logger.error(f"MusicBrainz API request failed for {artist_name}: {e.reason}")
            else:
                logger.error(f"MusicBrainz API request failed for {artist_name}: {e}")
            return None, None

        except Exception as e:
            logger.error(f"Unexpected error looking up MBID for {artist_name}: {e}")
            return None, None

    return None, None


def batch_lookup_mbids(artist_names, db, user_agent=None):
    """Look up multiple artists in batch (with rate limiting)

    Args:
        artist_names: List of artist names to look up
        db: RadioDatabase instance
        user_agent: Custom User-Agent string (optional)

    Returns:
        Dict mapping {artist_name: (mbid: str or None, verified_name: str or None)}
    """
    results = {}

    for artist_name in artist_names:
        mbid, verified_name = lookup_artist_mbid(artist_name, db, user_agent)
        results[artist_name] = (mbid, verified_name)

    return results


def retry_pending_artists(db, user_agent=None, max_artists=None):
    """Retry MBID lookup for all PENDING artists

    This function attempts to resolve all artists with PENDING- MBIDs
    by re-querying the MusicBrainz API.

    Args:
        db: RadioDatabase instance
        user_agent: Custom User-Agent string (optional)
        max_artists: Maximum number of artists to retry (None = all)

    Returns:
        Dict with stats: {'total': int, 'resolved': int, 'failed': int, 'results': list}
    """
    pending = db.get_pending_artists()

    if not pending:
        logger.info("No PENDING artists to retry")
        return {'total': 0, 'resolved': 0, 'failed': 0, 'results': []}

    total = len(pending)
    if max_artists:
        pending = pending[:max_artists]
        logger.info(f"Retrying MBID lookup for {len(pending)}/{total} PENDING artists")
    else:
        logger.info(f"Retrying MBID lookup for {total} PENDING artists")

    results = []
    resolved = 0
    failed = 0

    for artist_name, pending_mbid in pending:
        logger.info(f"Retrying {artist_name}...")

        # Handle collaborations: Extract primary artist(s)
        artists_to_lookup = [artist_name]

        # Check for "feat." or "featuring" - use primary artist (left side)
        if ' feat.' in artist_name.lower() or ' featuring ' in artist_name.lower():
            if ' feat.' in artist_name.lower():
                primary_artist = artist_name.lower().split(' feat.')[0].strip()
            else:
                primary_artist = artist_name.lower().split(' featuring ')[0].strip()

            # Preserve original casing
            for word in artist_name.split():
                if word.lower() in primary_artist.split():
                    primary_artist = primary_artist.replace(word.lower(), word)

            artists_to_lookup = [primary_artist]
            logger.info(f"  [feat.] Extracted primary artist: {primary_artist}")

        # Check for "&" - try each artist separately
        elif ' & ' in artist_name:
            collaboration_artists = [a.strip() for a in artist_name.split(' & ')]
            artists_to_lookup = collaboration_artists
            logger.info(f"  [&] Will try {len(collaboration_artists)} artists separately")

        # Try to lookup each primary artist (stop at first success)
        mbid = None
        for primary_artist in artists_to_lookup:
            if len(artists_to_lookup) > 1:
                logger.info(f"  Trying: {primary_artist}")

            # Look up MBID (auto_retry_pending=False to avoid infinite loop)
            mbid = lookup_artist_mbid(primary_artist, db, user_agent, auto_retry_pending=False)

            if mbid:
                logger.info(f"  Found MBID for {primary_artist}: {mbid}")
                break  # Success! Stop trying other artists
            else:
                if len(artists_to_lookup) > 1:
                    logger.warning(f"  No MBID found for {primary_artist}")

        result = {
            'name': artist_name,
            'old_mbid': pending_mbid,
            'new_mbid': mbid,
            'resolved': mbid is not None
        }

        if mbid:
            resolved += 1
            logger.info(f"[OK] Resolved {artist_name}: {pending_mbid} -> {mbid}")

            # If this was a collaboration that we resolved by extracting primary artist,
            # delete the old PENDING collaboration entry
            if ' feat.' in artist_name.lower() or ' & ' in artist_name:
                try:
                    # Disable foreign keys BEFORE starting transaction
                    db.cursor.execute("PRAGMA foreign_keys = OFF")
                    db.cursor.execute("BEGIN TRANSACTION")

                    # Delete songs under the PENDING collaboration MBID
                    db.cursor.execute("""
                        DELETE FROM songs
                        WHERE artist_mbid = ?
                    """, (pending_mbid,))

                    # Delete the PENDING collaboration artist entry
                    db.cursor.execute("""
                        DELETE FROM artists
                        WHERE mbid = ?
                    """, (pending_mbid,))

                    db.conn.commit()
                    logger.info(f"  [Cleaned up] Deleted old PENDING collaboration entry: {artist_name}")
                except Exception as e:
                    db.conn.rollback()
                    db.cursor.execute("PRAGMA foreign_keys = ON")
                    logger.warning(f"  [Warning] Could not delete PENDING collaboration {artist_name}: {e}")
        else:
            failed += 1
            logger.warning(f"[FAIL] Failed to resolve {artist_name}")

        results.append(result)

    logger.info(f"Retry complete: {resolved} resolved, {failed} still failed")

    return {
        'total': total,
        'resolved': resolved,
        'failed': failed,
        'results': results
    }


def verify_mbid_exists(mbid, user_agent=None):
    """Verify if MBID exists on MusicBrainz and get artist name.

    This function queries MusicBrainz API directly by MBID to verify:
    1. MBID exists on MusicBrainz
    2. Retrieve the artist name associated with the MBID

    Args:
        mbid: MusicBrainz ID to verify (UUID format)
        user_agent: Custom User-Agent string (optional)

    Returns:
        tuple: (exists: bool, artist_name: str or None)
            - exists: True if MBID found on MusicBrainz, False otherwise
            - artist_name: Artist name if found, None if not found

    Example:
        >>> exists, name = verify_mbid_exists("5bc41f77-cce4-4e76-a3e9-324c0201824f")
        >>> if exists:
        ...     print(f"MBID belongs to: {name}")
    """
    # Build API URL for direct MBID lookup
    url = f"https://musicbrainz.org/ws/2/artist/{mbid}?fmt=json"

    # Set User-Agent (MusicBrainz requirement)
    headers = {
        'User-Agent': user_agent or 'RadioMonitor/1.0.0 (https://github.com/allurjj/radio-monitor)'
    }

    try:
        # Add delay to respect rate limiting
        time.sleep(0.5)

        # Create SSL context
        ssl_context = ssl.create_default_context()

        req = urllib.request.Request(url, headers=headers)

        # Query MusicBrainz API
        with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
            # Rate limiting - wait after successful request
            time.sleep(0.5)

            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))

                # Extract artist name from response
                artist_name = data.get('name', None)

                if artist_name:
                    logger.debug(f"Verified MBID {mbid} belongs to artist: {artist_name}")
                    return True, artist_name
                else:
                    logger.warning(f"MBID {mbid} found but no artist name in response")
                    return True, None
            else:
                logger.warning(f"MusicBrainz returned HTTP {response.status} for MBID {mbid}")
                return False, None

    except urllib.error.HTTPError as e:
        if e.code == 404:
            # MBID not found
            logger.debug(f"MBID {mbid} not found on MusicBrainz (HTTP 404)")
            return False, None
        elif e.code == 400:
            # Invalid MBID format
            logger.warning(f"Invalid MBID format: {mbid} (HTTP 400)")
            return False, None
        else:
            # Other HTTP errors
            logger.error(f"MusicBrainz HTTP error for MBID {mbid}: {e.code}")
            return False, None

    except urllib.error.URLError as e:
        # Network/connection errors
        logger.error(f"MusicBrainz connection error verifying MBID {mbid}: {e}")
        return False, None

    except Exception as e:
        # Unexpected errors
        logger.error(f"Unexpected error verifying MBID {mbid}: {e}")
        return False, None


def get_artist_from_mbid(mbid, user_agent=None):
    """Get artist information from MusicBrainz by MBID.

    This is a wrapper around verify_mbid_exists that returns the full artist dict
    for consistency with other lookup functions.

    Args:
        mbid: MusicBrainz ID (UUID format)
        user_agent: Custom User-Agent string (optional)

    Returns:
        dict or None: Artist information if found, None otherwise
            {
                'mbid': str,
                'name': str
            }

    Example:
        >>> artist = get_artist_from_mbid("5bc41f77-cce4-4e76-a3e9-324c0201824f")
        >>> if artist:
        ...     print(f"Artist: {artist['name']}")
    """
    exists, artist_name = verify_mbid_exists(mbid, user_agent)

    if exists and artist_name:
        return {
            'mbid': mbid,
            'name': artist_name
        }
    else:
        return None

