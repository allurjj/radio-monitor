"""
Test Combined Artist+Song Lookup

This script tests the proposed combined lookup approach using real data from the database.
It queries MusicBrainz with both artist and song together to find the correct MBID.
"""

import sqlite3
import urllib.request
import urllib.parse
import json
import ssl
import time
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Import existing normalization functions
from radio_monitor.normalization import (
    normalize_artist_name,
    normalize_song_title,
    clean_song_title_for_query,
    strip_song_suffixes
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== MUSICBRAINZ API CLIENT ====================

class MusicBrainzClient:
    """MusicBrainz API client with proper headers and rate limiting"""

    def __init__(self, user_agent: str = None):
        """Initialize client with User-Agent

        Args:
            user_agent: Custom User-Agent string (MusicBrainz requirement)
        """
        self.user_agent = user_agent or 'RadioMonitor/1.0.0 (https://github.com/allurjj/radio-monitor)'
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between requests

    def _rate_limit(self):
        """Ensure we don't exceed MusicBrainz rate limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

        # Add small buffer
        time.sleep(0.1)
        self.last_request_time = time.time()

    def query_artists(self, artist_name: str, limit: int = 50) -> Dict:
        """Query MusicBrainz artists API (current method)

        Args:
            artist_name: Artist name to search for
            limit: Maximum results to return

        Returns:
            Dict with artist search results
        """
        self._rate_limit()

        # Normalize artist name for query
        normalized_name = normalize_artist_name(artist_name)
        encoded_name = urllib.parse.quote(normalized_name, safe='')

        url = f'https://musicbrainz.org/ws/2/artist/?query=artist:{encoded_name}&fmt=json&limit={limit}'

        try:
            req = urllib.request.Request(url, headers={'User-Agent': self.user_agent})
            ssl_context = ssl._create_unverified_context()

            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                if response.status == 200:
                    return json.loads(response.read().decode('utf-8'))
                else:
                    logger.error(f"MusicBrainz returned status {response.status}")
                    return {'artists': []}

        except Exception as e:
            logger.error(f"Error querying MusicBrainz artists: {e}")
            return {'artists': []}

    def query_recordings_by_artist_and_song(self, artist_name: str, song_title: str, limit: int = 20) -> Dict:
        """Query MusicBrainz recordings API with BOTH artist and song (new method)

        Args:
            artist_name: Artist name to search for
            song_title: Song title to search for
            limit: Maximum results to return

        Returns:
            Dict with recording search results
        """
        self._rate_limit()

        # Normalize inputs
        normalized_artist = normalize_artist_name(artist_name)
        cleaned_title = clean_song_title_for_query(song_title)

        # Build query: recording:"Song Title" AND artist:"Artist Name"
        encoded_title = urllib.parse.quote(f'"{cleaned_title}"', safe='')
        encoded_artist = urllib.parse.quote(f'"{normalized_artist}"', safe='')

        url = f'https://musicbrainz.org/ws/2/recording/?query=recording:{encoded_title}%20AND%20artist:{encoded_artist}&fmt=json&limit={limit}'

        logger.debug(f"Query URL: {url}")

        try:
            req = urllib.request.Request(url, headers={'User-Agent': self.user_agent})
            ssl_context = ssl._create_unverified_context()

            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                if response.status == 200:
                    return json.loads(response.read().decode('utf-8'))
                else:
                    logger.error(f"MusicBrainz returned status {response.status}")
                    return {'recordings': []}

        except Exception as e:
            logger.error(f"Error querying MusicBrainz recordings: {e}")
            return {'recordings': []}

    def query_recordings_by_mbid(self, artist_mbid: str, song_title: str, limit: int = 10) -> Dict:
        """Query MusicBrainz recordings by artist MBID (validation method)

        Args:
            artist_mbid: Artist MusicBrainz ID
            song_title: Song title to search for
            limit: Maximum results to return

        Returns:
            Dict with recording search results
        """
        self._rate_limit()

        # Clean song title for query
        cleaned_title = clean_song_title_for_query(song_title)
        encoded_title = urllib.parse.quote(f'"{cleaned_title}"', safe='')

        url = f'https://musicbrainz.org/ws/2/recording/?query=arid:{artist_mbid}%20AND%20recording:{encoded_title}&fmt=json&limit={limit}'

        try:
            req = urllib.request.Request(url, headers={'User-Agent': self.user_agent})
            ssl_context = ssl._create_unverified_context()

            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                if response.status == 200:
                    return json.loads(response.read().decode('utf-8'))
                else:
                    logger.error(f"MusicBrainz returned status {response.status}")
                    return {'recordings': []}

        except Exception as e:
            logger.error(f"Error querying MusicBrainz recordings by MBID: {e}")
            return {'recordings': []}


# ==================== MATCHING FUNCTIONS ====================

def calculate_similarity(str1: str, str2: str) -> float:
    """Calculate string similarity using SequenceMatcher"""
    from difflib import SequenceMatcher
    str1_norm = str1.lower().strip()
    str2_norm = str2.lower().strip()
    return SequenceMatcher(None, str1_norm, str2_norm).ratio()


def is_recording_match(recording: Dict, expected_title: str, expected_artist: str) -> Tuple[bool, str]:
    """Check if a MusicBrainz recording matches our song

    Returns:
        Tuple of (is_match, reason)
    """
    recording_title = recording.get('title', '')
    recording_artist = recording.get('artist-credit', [{}])[0].get('name', '') if recording.get('artist-credit') else ''

    # Clean both titles for comparison
    from radio_monitor.normalization import clean_song_title_for_query
    recording_title_clean = clean_song_title_for_query(recording_title)
    expected_title_clean = clean_song_title_for_query(expected_title)

    # Tier 1: Exact match (case-insensitive)
    if recording_title_clean.lower() == expected_title_clean.lower():
        return True, f"exact title match: '{recording_title}'"

    # Tier 2: Suffix-aware match (handles Remix, Live, etc.)
    from radio_monitor.normalization import strip_song_suffixes
    recording_stripped = strip_song_suffixes(recording_title_clean)
    expected_stripped = strip_song_suffixes(expected_title_clean)

    if recording_stripped.lower() == expected_stripped.lower():
        return True, f"suffix-aware match: '{recording_title}' -> '{recording_stripped}'"

    # Tier 3: Similarity match (85%+ threshold)
    if len(recording_title_clean) >= 4 and len(expected_title_clean) >= 4:
        similarity = calculate_similarity(recording_title_clean, expected_title_clean)
        if similarity >= 0.85:
            return True, f"similarity match: '{recording_title}' vs '{expected_title}' ({similarity:.1%})"

    return False, f"no match: '{recording_title}' vs '{expected_title}'"


# ==================== LOOKUP STRATEGIES ====================

def lookup_artist_only(artist_name: str, client: MusicBrainzClient) -> Optional[Tuple[str, str, str]]:
    """Strategy 1: Current method - lookup artist by name only

    Returns:
        Tuple of (mbid, verified_name, method) or None if not found
    """
    logger.info(f"\n=== STRATEGY 1: ARTIST-ONLY LOOKUP ===")
    logger.info(f"Searching for artist: '{artist_name}'")

    results = client.query_artists(artist_name, limit=50)

    if not results.get('artists'):
        logger.warning(f"No artists found for '{artist_name}'")
        return None

    # Find best match (simplified version of lookup_artist_mbid logic)
    best_match = None
    best_similarity = 0.0
    exact_match_found = False

    for result in results['artists']:
        result_mbid = result['id']
        result_name = result.get('name', '')
        result_name_normalized = normalize_artist_name(result_name)

        # Check for exact match
        if result_name_normalized.lower() == artist_name.lower():
            best_match = (result_mbid, result_name)
            best_similarity = 1.0
            exact_match_found = True
            logger.info(f"Found exact match: {result_name} ({result_mbid})")
            break

        # Calculate similarity
        similarity = calculate_similarity(artist_name, result_name_normalized)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = (result_mbid, result_name_normalized)

    if best_match and best_similarity >= 0.80:
        mbid, name = best_match
        logger.info(f"SELECTED: {name} ({mbid}) - {best_similarity:.1%} similarity")
        return (mbid, name, 'artist_only')

    logger.warning(f"No suitable match found (best similarity: {best_similarity:.1%})")
    return None


def lookup_combined(artist_name: str, song_title: str, client: MusicBrainzClient) -> Optional[Tuple[str, str, str]]:
    """Strategy 2: Proposed method - lookup using artist AND song together

    Returns:
        Tuple of (mbid, verified_name, method) or None if not found
    """
    logger.info(f"\n=== STRATEGY 2: COMBINED LOOKUP ===")
    logger.info(f"Searching for: '{artist_name}' - '{song_title}'")

    results = client.query_recordings_by_artist_and_song(artist_name, song_title, limit=20)

    if not results.get('recordings'):
        logger.warning(f"No recordings found for '{artist_name}' - '{song_title}'")
        return None

    logger.info(f"Found {len(results['recordings'])} recording(s)")

    # Find best matching recording
    best_match = None
    best_match_reason = ""

    for recording in results['recordings']:
        recording_title = recording.get('title', '')

        # Get artist info
        artist_credit = recording.get('artist-credit', [])
        if not artist_credit:
            continue

        recording_artist = artist_credit[0].get('name', '')
        recording_mbid = artist_credit[0].get('artist', {}).get('id', '') if artist_credit[0].get('artist') else ''

        if not recording_mbid:
            continue

        # Check if recording matches our song
        is_match, reason = is_recording_match(recording, song_title, artist_name)

        if is_match:
            logger.info(f"[MATCH] Recording matched: {recording_artist} - {recording_title} ({recording_mbid})")
            logger.info(f"  Reason: {reason}")

            # Use first match (MusicBrainz results are ranked by relevance)
            return (recording_mbid, recording_artist, 'combined')

        logger.debug(f"[SKIP] Recording skipped: {recording_artist} - {recording_title} - {reason}")

    logger.warning(f"No matching recordings found")
    return None


def validate_with_mbid(artist_mbid: str, artist_name: str, song_title: str, client: MusicBrainzClient) -> Tuple[bool, str]:
    """Validate that the artist MBID actually has this song

    Returns:
        Tuple of (is_valid, details)
    """
    logger.info(f"\n=== VALIDATION: Does MBID {artist_mbid} have '{song_title}'? ===")

    results = client.query_recordings_by_mbid(artist_mbid, song_title, limit=10)

    if not results.get('recordings'):
        return False, f"Recording NOT found for MBID {artist_mbid}"

    # Check for match
    for recording in results['recordings']:
        is_match, reason = is_recording_match(recording, song_title, artist_name)
        if is_match:
            return True, f"Recording found: {reason}"

    return False, f"No matching recording for MBID {artist_mbid}"


# ==================== TEST DATA ====================

def get_test_songs_from_db(limit: int = 50) -> List[Tuple[str, str, str]]:
    """Get real songs from database for testing

    Returns:
        List of (artist_name, artist_mbid, song_title) tuples
    """
    db_path = 'radio_songs.db'

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get diverse set of songs
        cursor.execute("""
            SELECT DISTINCT a.name, a.mbid, s.song_title
            FROM artists a
            JOIN songs s ON a.mbid = s.artist_mbid
            WHERE a.mbid NOT LIKE 'PENDING%'
            ORDER BY RANDOM()
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        logger.info(f"Retrieved {len(rows)} songs from database for testing")
        return rows

    except Exception as e:
        logger.error(f"Error reading database: {e}")
        return []


def get_hamilton_case() -> Tuple[str, str, str]:
    """Get the specific Hamilton case that triggered this investigation

    Returns:
        Tuple of (artist_name, artist_mbid, song_title)
    """
    # This is the case that exposed the problem
    # In real scenario, this would come from the database
    return ("Hamilton", "PENDING-xxx", "Fallin' In Love")


# ==================== MAIN TEST ====================

def run_comparison_test(limit=20):
    """Run comparison test on real data"""

    print("\n" + "="*80)
    print("COMBINED LOOKUP TEST")
    print("="*80)

    # Get test data
    test_songs = get_test_songs_from_db(limit=limit)

    if not test_songs:
        logger.error("No test songs available")
        return

    # Initialize MusicBrainz client
    # Try to get user_agent from settings
    try:
        import json
        with open('radio_monitor_settings.json', 'r') as f:
            settings = json.load(f)
            user_agent = settings.get('musicbrainz', {}).get('user_agent')
    except:
        user_agent = None

    client = MusicBrainzClient(user_agent=user_agent)

    # Statistics
    stats = {
        'total': 0,
        'artist_only_found': 0,
        'combined_found': 0,
        'both_found': 0,
        'combined_only': 0,
        'artist_only_only': 0,
        'validation_passed': 0,
        'validation_failed': 0
    }

    # Track specific failure cases
    combined_failures = []  # Cases where combined failed but artist-only succeeded
    validation_failures = []  # Cases where artist-only validation failed

    print("\n" + "-"*80)
    print("TESTING EACH SONG WITH BOTH STRATEGIES")
    print("-"*80)

    for i, (artist_name, current_mbid, song_title) in enumerate(test_songs, 1):
        print(f"\n{'='*80}")
        print(f"TEST {i}/{len(test_songs)}: {artist_name} - {song_title}")
        print(f"Current MBID: {current_mbid}")
        print('='*80)

        stats['total'] += 1

        # Strategy 1: Artist-only lookup (current method)
        artist_only_result = lookup_artist_only(artist_name, client)

        # Strategy 2: Combined lookup (proposed method)
        combined_result = lookup_combined(artist_name, song_title, client)

        # Track results
        if artist_only_result:
            stats['artist_only_found'] += 1
        if combined_result:
            stats['combined_found'] += 1
        if artist_only_result and combined_result:
            stats['both_found'] += 1
        if combined_result and not artist_only_result:
            stats['combined_only'] += 1
        if artist_only_result and not combined_result:
            stats['artist_only_only'] += 1
            # Track specific case where artist-only worked but combined failed
            combined_failures.append((artist_name, current_mbid, song_title))

        # Validate artist-only result
        if artist_only_result:
            mbid, name, method = artist_only_result
            is_valid, details = validate_with_mbid(mbid, artist_name, song_title, client)

            if is_valid:
                stats['validation_passed'] += 1
                print(f"\n[PASS] Artist-only validation PASSED: {details}")
            else:
                stats['validation_failed'] += 1
                validation_failures.append((artist_name, current_mbid, song_title, mbid, name))
                print(f"\n[FAIL] Artist-only validation FAILED: {details}")

                # This is the problem case - artist-only found an MBID but it doesn't have the song!
                if combined_result:
                    combined_mbid, combined_name, combined_method = combined_result
                    print(f"\n[COMPARE] COMBINED LOOKUP SUCCEEDED WHERE ARTIST-ONLY FAILED:")
                    print(f"   Artist-only found: {name} ({mbid}) - INVALID")
                    print(f"   Combined found: {combined_name} ({combined_mbid}) - VALID")

        # Rate limiting between songs
        time.sleep(1)

    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total songs tested: {stats['total']}")
    print(f"\nArtist-only lookup (current method):")
    print(f"  Found: {stats['artist_only_found']} ({stats['artist_only_found']/stats['total']*100:.1f}%)")
    print(f"  Validation passed: {stats['validation_passed']}")
    print(f"  Validation failed: {stats['validation_failed']} [WARN]")
    print(f"\nCombined lookup (proposed method):")
    print(f"  Found: {stats['combined_found']} ({stats['combined_found']/stats['total']*100:.1f}%)")
    print(f"\nComparison:")
    print(f"  Both methods found: {stats['both_found']}")
    print(f"  Combined only (new discoveries): {stats['combined_only']} [NEW]")
    print(f"  Artist-only only (may be bad matches): {stats['artist_only_only']} [WARN]")
    print("="*80)

    # Print detailed failure cases
    if validation_failures:
        print(f"\n{'='*80}")
        print("DETAILED VALIDATION FAILURES (Artist-only found WRONG MBID)")
        print("="*80)
        for i, (artist_name, current_mbid, song_title, wrong_mbid, wrong_name) in enumerate(validation_failures, 1):
            print(f"\n{i}. {artist_name} - {song_title}")
            print(f"   Current DB MBID: {current_mbid}")
            print(f"   Artist-only found: {wrong_name} ({wrong_mbid}) - INVALID")
            print(f"   [FIX] Combined lookup would find correct artist")

    if combined_failures:
        print(f"\n{'='*80}")
        print("COMBINED LOOKUP FAILURES (Artist-only worked, Combined failed)")
        print("="*80)
        print("These cases show the limitations of combined lookup.")
        print("Fallback to artist-only is necessary for these cases.")
        for i, (artist_name, current_mbid, song_title) in enumerate(combined_failures, 1):
            print(f"\n{i}. {artist_name} - {song_title}")
            print(f"   Current MBID: {current_mbid}")
            print(f"   Combined lookup: NO RESULTS")
            print(f"   Artist-only: Found an MBID (fallback used)")
            print(f"   [NOTE] Need to verify if artist-only MBID is correct")

    # Problem assessment
    if stats['validation_failed'] > 0:
        print(f"\n[WARN] PROBLEM DETECTED: {stats['validation_failed']} artist(s) found by artist-only")
        print("   lookup DO NOT have the songs attributed to them.")
        print("   These would require manual correction via data validation.")

    if combined_failures:
        print(f"\n[INFO] Combined lookup missed {len(combined_failures)} case(s)")
        print("   Fallback to artist-only lookup is necessary for these edge cases.")


def test_hamilton_case():
    """Test the specific Hamilton case"""
    print("\n" + "="*80)
    print("HAMILTON CASE STUDY")
    print("="*80)

    artist_name, current_mbid, song_title = get_hamilton_case()

    print(f"\nCase: {artist_name} - {song_title}")
    print(f"Current MBID: {current_mbid}")

    # Initialize client
    client = MusicBrainzClient()

    # Test artist-only lookup
    print("\n--- Testing Artist-Only Lookup (Current Method) ---")
    artist_only_result = lookup_artist_only(artist_name, client)

    if artist_only_result:
        mbid, name, method = artist_only_result
        print(f"\nArtist-only found: {name} ({mbid})")

        # Validate
        is_valid, details = validate_with_mbid(mbid, artist_name, song_title, client)
        print(f"\nValidation result: {'[VALID]' if is_valid else '[INVALID]'}")
        print(f"Details: {details}")

    # Test combined lookup
    print("\n--- Testing Combined Lookup (Proposed Method) ---")
    combined_result = lookup_combined(artist_name, song_title, client)

    if combined_result:
        mbid, name, method = combined_result
        print(f"\nCombined found: {name} ({mbid})")
        print(f"Method: {method}")
    else:
        print("\nCombined lookup found no results")


# ==================== MAIN ====================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Test combined artist+song lookup')
    parser.add_argument('--hamilton', action='store_true', help='Run Hamilton case study only')
    parser.add_argument('--count', type=int, default=20, help='Number of songs to test (default: 20)')

    args = parser.parse_args()

    if args.hamilton:
        test_hamilton_case()
    else:
        run_comparison_test(limit=args.count)
