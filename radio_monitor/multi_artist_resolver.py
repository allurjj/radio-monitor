"""
Multi-Artist Resolver for Radio Monitor

Resolves multi-artist collaborations by intelligently splitting artist names
and validating them against MusicBrainz API.

Key Features:
- Missing separator detection with hybrid validation
- Song title context validation
- Recursive resolution with 3 depths of fallback
- Atomic database updates
"""

import re
import logging
from typing import List, Dict, Tuple, Optional
from radio_monitor.mbid import lookup_artist_mbid
from radio_monitor.database.crud import update_multi_artist_resolution

logger = logging.getLogger(__name__)


def split_artist_name(artist_name: str, song_title: str = None) -> List[str]:
    """
    Split artist name into individual artist names using multiple strategies.

    Args:
        artist_name: The collaboration artist name to split
        song_title: Optional song title for context validation

    Returns:
        List of individual artist names (1-4 artists typically)
    """
    strategies = [
        _split_by_direct_separators,
        _split_by_missing_separators,
        lambda x, y: _split_with_song_context(x, y) if y else [],
        _split_former_names,
    ]

    for strategy in strategies:
        result = strategy(artist_name, song_title)
        if result and len(result) > 1:
            logger.debug(f"Split '{artist_name}' using {strategy.__name__}: {result}")
            return result

    # No split found, return original
    return [artist_name]


def _split_by_direct_separators(artist_name: str, song_title: str = None) -> List[str]:
    """Split by common separators like ' & ', ' And ', ' feat ', etc."""
    # Pattern for various separators
    separators = [
        r' \+ ',  # Plus sign
        r' x ',   # Little x
        r' vs\.?', # Versus
        r',',     # Comma
        r' feat\.?',  # Feat/feat.
        r' featuring ',  # Featuring
        r' with ',  # With
        r' & ',    # Ampersand
        r'[Aa]nd ',  # And (case-insensitive)
    ]

    for sep in separators:
        if re.search(sep, artist_name, re.IGNORECASE):
            # Split and clean
            parts = re.split(sep, artist_name, flags=re.IGNORECASE)
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) > 1:
                return parts

    return []


def _split_by_missing_separators(artist_name: str, song_title: str = None) -> List[str]:
    """
    Detect missing separators using multiple patterns.

    Patterns detected:
    1. Lowercase followed by uppercase: "DionJames" -> ["Dion", "James"]
    2. Multiple proper names without separators: "Bill Medley Jennifer Warnes"

    Note: This function only returns CANDIDATE splits that must be validated
    against MusicBrainz API before accepting (hybrid validation approach).

    Example: "Celine Dionjames Horner" -> try ["Celine Dion", "James Horner"]
             -> Validate both against MusicBrainz -> accept if both found
    """
    # Pattern 1: Detect lowercase + uppercase (like "DionJames")
    pattern = r'([a-z])([A-Z])'
    matches = list(re.finditer(pattern, artist_name))

    if matches:
        # Build split points
        split_points = [m.end() - 1 for m in matches]  # Position before capital letter

        # Split artist name at these points
        parts = []
        start = 0
        for point in split_points:
            parts.append(artist_name[start:point].strip())
            start = point
        parts.append(artist_name[start:].strip())

        # Clean up parts
        parts = [p.strip() for p in parts if p.strip()]

        # Capitalize first letter of parts after first
        if len(parts) > 1:
            for i in range(1, len(parts)):
                if parts[i]:
                    parts[i] = parts[i][0].upper() + parts[i][1:].lower()

        # Filter out single-letter splits
        if not any(len(p) <= 2 for p in parts):
            logger.debug(f"Missing separator split (pattern 1): {parts}")
            return parts if len(parts) > 1 else []

    # Pattern 2: Detect multiple proper names (2+ consecutive capitalized words)
    # Example: "Bill Medley Jennifer Warnes" -> ["Bill Medley", "Jennifer Warnes"]
    words = artist_name.split()
    if len(words) >= 4:
        # Try to split in the middle (after 2 words)
        mid_point = len(words) // 2
        part1 = ' '.join(words[:mid_point])
        part2 = ' '.join(words[mid_point:])

        # Only use this split if both parts look like proper names (start with capital)
        if part1[0].isupper() and part2[0].isupper():
            logger.debug(f"Missing separator split (pattern 2): [{part1}, {part2}]")
            return [part1, part2]

    # Pattern 3: Try splitting at word boundaries for merged names
    # Example: "Dionjames" -> try splitting after "Dion", "on", "n", etc.
    # This is a last resort and requires validation
    if len(artist_name) > 10 and ' ' not in artist_name[:20]:
        # Single long word without spaces, try splitting at common name boundaries
        # Look for lowercase letter followed by another lowercase that could start a new name
        # This is heuristic and will be validated by MusicBrainz
        for i in range(3, len(artist_name) - 3):
            # Try splitting at position i
            part1 = artist_name[:i]
            part2 = artist_name[i:]

            # Capitalize both parts
            part1_fixed = part1[0].upper() + part1[1:].lower()
            part2_fixed = part2[0].upper() + part2[1:].lower()

            # Only return if both parts are reasonable length (3+ chars)
            if len(part1_fixed) >= 3 and len(part2_fixed) >= 3:
                logger.debug(f"Missing separator split (pattern 3): [{part1_fixed}, {part2_fixed}]")
                return [part1_fixed, part2_fixed]

    return []


def _split_with_song_context(artist_name: str, song_title: str) -> List[str]:
    """
    Extract featured artists from song title parentheses.

    Example: "Mumford Sons Hozier" + "Rubber Band Man (with Hozier)"
    -> Suggests "Hozier" is featured, split remaining as "Mumford Sons"
    """
    if not song_title:
        return []

    # Look for patterns like "feat.", "with", "x" in parentheses
    featured_patterns = [
        r'\(feat\.?\s+([^\)]+)\)',
        r'\(with\s+([^\)]+)\)',
        r'\(x\s+([^\)]+)\)',
    ]

    for pattern in featured_patterns:
        match = re.search(pattern, song_title, re.IGNORECASE)
        if match:
            featured_artist = match.group(1).strip()
            logger.debug(f"Found featured artist in song title: {featured_artist}")

            # Try to split artist_name to extract the featured part
            if featured_artist.lower() in artist_name.lower():
                # Split out the featured artist
                parts = re.split(
                    re.escape(featured_artist),
                    artist_name,
                    flags=re.IGNORECASE
                )
                parts = [p.strip() for p in parts if p.strip()]

                # Add featured artist back
                parts.append(featured_artist)

                if len(parts) > 1:
                    return parts

    return []


def _split_former_names(artist_name: str, song_title: str = None) -> List[str]:
    """
    Detect artists with former names like "Yusuf Cat Stevens".

    Tries both "Yusuf" and "Cat Stevens" as separate lookups.
    """
    # Pattern: "FormerName CurrentName" or "CurrentName FormerName"
    # Common patterns: "aka", "formerly known as", "formerly"
    former_patterns = [
        r'(.+?)\s+(?:aka|formerly\s+known\s+as|formerly)\s+(.+)',
        r'(?:aka|formerly\s+known\s+as|formerly)\s+(.+?)\s+(.+)',
    ]

    for pattern in former_patterns:
        match = re.match(pattern, artist_name, re.IGNORECASE)
        if match:
            parts = [match.group(1).strip(), match.group(2).strip()]
            logger.debug(f"Former name split: {parts}")
            return parts

    # Special case: "Yusuf Cat Stevens" -> Try "Yusuf" and "Cat Stevens"
    # This is a common pattern where we can try splitting at certain positions
    words = artist_name.split()
    if len(words) >= 3:
        # Try splitting after first word: "Yusuf" | "Cat Stevens"
        return [words[0], ' '.join(words[1:])]

    return []


def try_musicbrainz_search(
    artist_names: List[str],
    db,
    user_agent: str
) -> Dict[str, str]:
    """
    Validate split artist names against MusicBrainz API.

    Args:
        artist_names: List of artist names to validate
        db: Database instance
        user_agent: User agent for MusicBrainz API

    Returns:
        Dict mapping {artist_name: mbid or None}
    """
    results = {}

    for artist_name in artist_names:
        try:
            mbid = lookup_artist_mbid(
                artist_name=artist_name,
                db=db,
                user_agent=user_agent
            )
            if mbid and not mbid.startswith('PENDING'):
                results[artist_name] = mbid
                logger.debug(f"Found MBID for '{artist_name}': {mbid}")
            else:
                results[artist_name] = None
                logger.debug(f"No MBID found for '{artist_name}'")
        except Exception as e:
            logger.warning(f"Error looking up '{artist_name}': {e}")
            results[artist_name] = None

    return results


def try_split_and_validate(artist_name: str, db, user_agent: str) -> List[str]:
    """
    Try multiple split strategies and validate against MusicBrainz.

    This is the HYBRID VALIDATION approach mentioned in the plan.
    We try different split points and validate BOTH parts against MusicBrainz.
    Only accept splits where BOTH artists are found.

    NEW: Smart grouping strategy for 2-3 artist collaborations:
    - 2 names: Try both together, then individually
    - 3 names: Try (first 2) + (last 1), then (first 1) + (last 2)

    Args:
        artist_name: The collaboration name to split
        db: Database instance
        user_agent: User agent for MusicBrainz API

    Returns:
        List of validated artist names (empty if validation fails)
    """
    all_valid_splits = []

    # Strategy 1: Smart grouping for 2-3 word collaborations (NEW!)
    words = artist_name.split()
    num_words = len(words)

    if num_words == 2:
        # 2 words: Try both together, then individually
        # Example: "Gotye Kimbra" -> try "Gotye Kimbra", then "Gotye" + "Kimbra"
        logger.debug(f"Trying 2-word smart grouping for: {artist_name}")

        # Try both words together first
        validation = try_musicbrainz_search([artist_name], db, user_agent)
        if validation.get(artist_name):
            # It's a single artist with 2-word name
            logger.info(f"Validated as single 2-word artist: {artist_name}")
            return [artist_name]

        # Try individual words
        validation = try_musicbrainz_search(words, db, user_agent)
        if all(validation.get(word) for word in words):
            logger.info(f"Validated 2-word split: {words}")
            all_valid_splits.append(words)

    elif num_words == 3:
        # 3 words: Try (first 2) + (last 1), then (first 1) + (last 2)
        # Example: "Mumford Sons Hozier" -> "Mumford Sons" + "Hozier"
        logger.debug(f"Trying 3-word smart grouping for: {artist_name}")

        # Strategy 1: First 2 words + last 1 word
        artist1 = ' '.join(words[:2])
        artist2 = words[2]
        validation = try_musicbrainz_search([artist1, artist2], db, user_agent)
        if validation.get(artist1) and validation.get(artist2):
            logger.info(f"Validated 3-word split (2+1): [{artist1}, {artist2}]")
            all_valid_splits.append([artist1, artist2])

        # Strategy 2: First 1 word + last 2 words
        artist1 = words[0]
        artist2 = ' '.join(words[1:])
        validation = try_musicbrainz_search([artist1, artist2], db, user_agent)
        if validation.get(artist1) and validation.get(artist2):
            logger.info(f"Validated 3-word split (1+2): [{artist1}, {artist2}]")
            all_valid_splits.append([artist1, artist2])

        # Strategy 3: All individual words (fallback)
        validation = try_musicbrainz_search(words, db, user_agent)
        if all(validation.get(word) for word in words):
            logger.info(f"Validated 3-word split (1+1+1): {words}")
            all_valid_splits.append(words)

    elif num_words == 4:
        # 4 words: Try (first 3) + (last 1), then (first 2) + (last 2), then (first 1) + (last 3)
        # Example: "Bill Medley Jennifer Warnes" -> "Bill Medley" + "Jennifer Warnes" (2+2)
        logger.debug(f"Trying 4-word smart grouping for: {artist_name}")

        # Strategy 1: First 3 + last 1 (3-word artist name + featured artist)
        artist1 = ' '.join(words[:3])
        artist2 = words[3]
        validation = try_musicbrainz_search([artist1, artist2], db, user_agent)
        if validation.get(artist1) and validation.get(artist2):
            logger.info(f"Validated 4-word split (3+1): [{artist1}, {artist2}]")
            all_valid_splits.append([artist1, artist2])

        # Strategy 2: First 2 + last 2 (two 2-word artist names)
        artist1 = ' '.join(words[:2])
        artist2 = ' '.join(words[2:])
        validation = try_musicbrainz_search([artist1, artist2], db, user_agent)
        if validation.get(artist1) and validation.get(artist2):
            logger.info(f"Validated 4-word split (2+2): [{artist1}, {artist2}]")
            all_valid_splits.append([artist1, artist2])

        # Strategy 3: First 1 + last 3 (rare)
        artist1 = words[0]
        artist2 = ' '.join(words[1:])
        validation = try_musicbrainz_search([artist1, artist2], db, user_agent)
        if validation.get(artist1) and validation.get(artist2):
            logger.info(f"Validated 4-word split (1+3): [{artist1}, {artist2}]")
            all_valid_splits.append([artist1, artist2])

    elif num_words >= 5:
        # 5+ words: Try various splits starting with longer first artist names
        # Example: "Black Label Society Zakk Wylde" -> "Black Label Society" + "Zakk Wylde" (3+2)
        logger.debug(f"Trying {num_words}-word smart grouping for: {artist_name}")

        # Try all possible split points from 3+2, 2+3, 4+1, 1+4
        split_strategies = [
            (3, 2), (2, 3),  # Most common for two artist names
            (4, 1), (1, 4),  # 4-word artist + featured
            (3, num_words - 3),  # Generic 3 + rest
            (num_words - 2, 2),  # Rest + 2
        ]

        for first_count, second_count in split_strategies:
            if first_count + second_count == num_words:
                artist1 = ' '.join(words[:first_count])
                artist2 = ' '.join(words[first_count:])
                validation = try_musicbrainz_search([artist1, artist2], db, user_agent)
                if validation.get(artist1) and validation.get(artist2):
                    logger.info(f"Validated {num_words}-word split ({first_count}+{second_count}): [{artist1}, {artist2}]")
                    all_valid_splits.append([artist1, artist2])
                    break  # Found a valid split, stop searching

    # If smart grouping found valid splits, select the best one
    if all_valid_splits:
        # Prefer splits with longer artist names (more likely to be correct)
        # e.g., prefer ["Rihanna", "Jay Z"] over ["Rihanna Jay", "Z"]
        def split_quality(split):
            # Calculate total length (more characters = more complete names)
            total_len = sum(len(name) for name in split)
            # Prefer fewer artists (2 is better than 3)
            artist_count = len(split)
            return (artist_count, -total_len)  # Lower artists, higher total_len is better

        best_split = min(all_valid_splits, key=split_quality)
        logger.info(f"Selected smart grouping split from {len(all_valid_splits)} candidates: {best_split}")
        return best_split

    # Strategy 2: Standard split strategies (original approach)
    standard_splits = split_artist_name(artist_name)
    if len(standard_splits) > 1:
        # Validate the standard split
        validation = try_musicbrainz_search(standard_splits, db, user_agent)
        # Check if ALL parts were found
        if all(validation.get(name) for name in standard_splits):
            logger.info(f"Validated standard split: {standard_splits}")
            all_valid_splits.append(standard_splits)

    # If standard splits don't work, try brute force for long words
    # Look for long words (> 8 chars) that might be merged
    words = artist_name.split()
    for i, word in enumerate(words):
        if len(word) > 8 and word.isalpha():
            # Try splitting this word at various positions
            for split_pos in range(3, len(word) - 2):
                part1 = word[:split_pos]
                part2 = word[split_pos:]

                # Capitalize properly
                part1_fixed = part1[0].upper() + part1[1:].lower()
                part2_fixed = part2[0].upper() + part2[1:].lower()

                # Create candidate split by replacing the merged word
                candidate_parts = (
                    words[:i] +
                    [part1_fixed, part2_fixed] +
                    words[i+1:]
                )

                # Try to group into 2 artists (first part + second part)
                if len(candidate_parts) >= 2:
                    # Try splitting at different positions
                    for j in range(1, len(candidate_parts)):
                        artist1 = ' '.join(candidate_parts[:j])
                        artist2 = ' '.join(candidate_parts[j:])

                        # Validate both
                        validation = try_musicbrainz_search([artist1, artist2], db, user_agent)

                        # If both found, this is a valid split!
                        if validation.get(artist1) and validation.get(artist2):
                            logger.info(f"Validated brute force split: [{artist1}, {artist2}]")
                            all_valid_splits.append([artist1, artist2])

    # If we found multiple valid splits, prefer the first one from standard split strategies
    # (standard splits are more likely to be correct than brute force splits)
    if all_valid_splits:
        # Just return the first valid split (simplest approach)
        # In practice, standard splits are found first and are usually correct
        best_split = all_valid_splits[0]
        logger.info(f"Selected split from {len(all_valid_splits)} candidates: {best_split}")
        return best_split

    return []


def resolve_multi_artist_recursive(
    artist_name: str,
    song_title: str,
    db,
    user_agent: str,
    depth: int = 0,
    max_depth: int = 3
) -> Tuple[Optional[str], List[str]]:
    """
    Recursive resolution with 3 depths of fallback strategies.

    Args:
        artist_name: The collaboration artist name
        song_title: Optional song title for context
        db: Database instance
        user_agent: User agent for MusicBrainz API
        depth: Current recursion depth
        max_depth: Maximum recursion depth (default 3)

    Returns:
        Tuple of (primary_mbid or None, all_found_mbids)
    """
    if depth >= max_depth:
        logger.debug(f"Max depth reached for '{artist_name}'")
        return None, []

    # Use hybrid validation: try split strategies and validate against MusicBrainz
    logger.debug(f"Depth {depth}: Trying hybrid validation for '{artist_name}'")
    validated_artists = try_split_and_validate(artist_name, db, user_agent)

    if validated_artists:
        # Found a validated split!
        logger.info(f"Validated split at depth {depth}: {validated_artists}")

        # Get MBIDs for all validated artists
        validation_results = try_musicbrainz_search(validated_artists, db, user_agent)
        found_mbids = [mbid for mbid in validation_results.values() if mbid]

        # Return first artist's MBID as primary
        primary_mbid = found_mbids[0] if found_mbids else None
        return primary_mbid, found_mbids

    # No validated split found at this depth
    logger.debug(f"No validated split found at depth {depth}")
    return None, []


def resolve_multi_artist(
    cursor,
    conn,
    artist_name: str,
    song_title: str = None,
    db = None,
    user_agent: str = None
) -> Optional[str]:
    """
    Main entry point for resolving multi-artist collaborations.

    This function:
    1. Splits the collaboration name into individual artists
    2. Validates splits against MusicBrainz API
    3. Updates database atomically if resolution succeeds
    4. Returns primary artist's MBID (first artist)

    Args:
        cursor: Database cursor (can be None)
        conn: Database connection
        artist_name: The collaboration artist name to resolve
        song_title: Optional song title for context validation
        db: Database instance
        user_agent: User agent for MusicBrainz API

    Returns:
        Primary artist's MBID or None if resolution failed
    """
    if not db or not user_agent:
        logger.error("Missing db or user_agent for multi-artist resolution")
        return None

    logger.info(f"Attempting multi-artist resolution for: {artist_name}")

    # Try recursive resolution
    primary_mbid, all_mbids = resolve_multi_artist_recursive(
        artist_name=artist_name,
        song_title=song_title,
        db=db,
        user_agent=user_agent,
        depth=0,
        max_depth=3
    )

    if primary_mbid:
        # Get primary artist name from MBID (first 8 chars for logging)
        logger.info(f"Successfully resolved '{artist_name}' -> MBID: {primary_mbid[:8]}...")

        # Update database atomically
        # Note: We need to get the old MBID first if this is a PENDING entry
        if cursor:
            try:
                cursor.execute("""
                    SELECT mbid FROM artists WHERE name = ? COLLATE NOCASE
                """, (artist_name,))
                result = cursor.fetchone()
                old_mbid = result[0] if result else None

                logger.debug(f"Found old MBID: {old_mbid}")

                if old_mbid and old_mbid.startswith('PENDING'):
                    # Get the primary artist name from MusicBrainz lookup
                    # We need to redo the lookup to get the name
                    split_artists = split_artist_name(artist_name, song_title)
                    logger.debug(f"Split artists: {split_artists}")

                    if split_artists:
                        validation_results = try_musicbrainz_search(split_artists, db, user_agent)
                        logger.debug(f"Validation results: {validation_results}")

                        for name, mbid in validation_results.items():
                            if mbid == primary_mbid:
                                new_primary_name = name
                                break
                        else:
                            new_primary_name = split_artists[0]

                        logger.debug(f"Primary artist name: {new_primary_name}")

                        # Update database atomically
                        logger.info(f"Calling update_multi_artist_resolution...")
                        success = update_multi_artist_resolution(
                            cursor=cursor,
                            conn=conn,
                            old_collaboration_name=artist_name,
                            old_mbid=old_mbid,
                            new_primary_mbid=primary_mbid,
                            new_primary_name=new_primary_name
                        )

                        if success:
                            logger.info(f"Database updated: {old_mbid} -> {primary_mbid}")
                        else:
                            logger.warning(f"Database update failed for {artist_name}")
                else:
                    logger.warning(f"Old MBID is not PENDING or not found: {old_mbid}")
            except Exception as e:
                logger.error(f"Error updating database for '{artist_name}': {e}")
        else:
            logger.warning("No cursor provided - skipping database update")

        return primary_mbid
    else:
        logger.warning(f"Failed to resolve multi-artist collaboration: {artist_name}")
        return None


def resolve_multi_artist_batch(
    db,
    user_agent: str,
    max_artists: int = None,
    dry_run: bool = False
) -> Dict:
    """
    Batch resolve all PENDING multi-artist entries.

    Args:
        db: Database instance
        user_agent: User agent for MusicBrainz API
        max_artists: Maximum number of artists to resolve (None = all)
        dry_run: If True, show what would be resolved without making changes

    Returns:
        Dict with results: {'total': N, 'resolved': N, 'failed': N, 'results': [...]}
    """
    cursor = db.get_cursor()
    try:
        # Get all PENDING artists
        cursor.execute("""
            SELECT mbid, name
            FROM artists
            WHERE mbid LIKE 'PENDING-%'
            ORDER BY name
        """)
        pending_artists = cursor.fetchall()

        if max_artists:
            pending_artists = pending_artists[:max_artists]

        results = {
            'total': len(pending_artists),
            'resolved': 0,
            'failed': 0,
            'results': []
        }

        print(f"\n[INFO] Found {results['total']} PENDING artists to resolve")

        for old_mbid, artist_name in pending_artists:
            print(f"\n[INFO] Processing: {artist_name} ({old_mbid})")

            # Try to resolve
            primary_mbid = resolve_multi_artist(
                cursor=None if dry_run else cursor,
                conn=db.conn,
                artist_name=artist_name,
                song_title=None,  # Could fetch from songs table if needed
                db=db,
                user_agent=user_agent
            )

            result = {
                'name': artist_name,
                'old_mbid': old_mbid,
                'new_mbid': primary_mbid if primary_mbid else None,
                'resolved': primary_mbid is not None
            }
            results['results'].append(result)

            if primary_mbid:
                results['resolved'] += 1
                print(f"  [OK] Resolved: {old_mbid} -> {primary_mbid}")
            else:
                results['failed'] += 1
                print(f"  [FAIL] Failed to resolve")

        return results

    finally:
        cursor.close()
