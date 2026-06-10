"""
Recording-level validation for Radio Monitor

This module provides recording-level validation to detect artist/song
mismatches that artist-level validation misses.

Key Functions:
- validate_recording_exists(): Check if artist+song combo exists in MusicBrainz
- validate_with_fallback(): Try MBID query, fall back to text query
- is_recording_match(): Check if MusicBrainz result matches our song

Usage:
    from radio_monitor.recording_validation import validate_recording_exists

    if validate_recording_exists(artist_mbid, song_title):
        logger.info(f"Recording validated: {artist_name} - {song_title}")
"""

import urllib.request
import urllib.parse
import json
import ssl
import logging
import re
import unicodedata
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


def query_musicbrainzRecording(query: str, limit: int = 10) -> Dict:
    """Query MusicBrainz recording API

    Args:
        query: URL-encoded search query
        limit: Maximum number of results (default: 10)

    Returns:
        Dict with recording search results
    """
    url = f'https://musicbrainz.org/ws/2/recording/?query={query}&fmt=json&limit={limit}'

    headers = {
        'User-Agent': 'RadioMonitor/1.0.0 (https://github.com/allurjj/radio-monitor)'
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        ssl_context = ssl._create_unverified_context()

        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
            else:
                logger.error(f"MusicBrainz returned status {response.status}")
                return {'recordings': []}

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {'recordings': []}
        logger.error(f"HTTP error: {e.code} - {e.reason}")
        return {'recordings': []}
    except Exception as e:
        logger.error(f"Error querying MusicBrainz: {e}")
        return {'recordings': []}


def is_recording_match(recording: Dict, expected_title: str, expected_artist: str) -> bool:
    """Check if a MusicBrainz recording matches our song

    Args:
        recording: MusicBrainz recording dict
        expected_title: Our song title
        expected_artist: Our artist name (empty for MBID queries)

    Returns:
        True if recording matches our song
    """
    recording_title = recording.get('title', '')

    # Clean both titles the same way for fair comparison
    # This handles parentheticals, features, etc. that may differ
    from radio_monitor.normalization import clean_song_title_for_query
    recording_title = clean_song_title_for_query(recording_title)
    expected_title = clean_song_title_for_query(expected_title)

    # Normalize Unicode apostrophes to ASCII apostrophe
    # MusicBrainz sometimes returns U+2019/U+2018 instead of U+0027
    # Also handle corrupted control characters (U+0019)
    recording_title = unicodedata.normalize('NFKC', recording_title)
    recording_title = re.sub(r"[’‘‛❜❛❝❞]", "'", recording_title)
    recording_title = re.sub(r'[\x00-\x1F\x7F-\x9F]', "'", recording_title)

    expected_title = unicodedata.normalize('NFKC', expected_title)
    expected_title = re.sub(r"[’‘‛❜❛❝❞]", "'", expected_title)
    expected_title = re.sub(r'[\x00-\x1F\x7F-\x9F]', "'", expected_title)

    # Case-insensitive title comparison
    if recording_title.lower() != expected_title.lower():
        return False

    # If no artist expected (MBID query), title match is sufficient
    if not expected_artist:
        return True

    # Check artist credits
    artist_credits = recording.get('artist-credit', [])
    for credit in artist_credits:
        artist_name = credit.get('name', '')
        if artist_name.lower() == expected_artist.lower():
            return True

    return False


def validate_recording_by_mbid(artist_mbid: str, song_title: str, clean_title: bool = False) -> Tuple[bool, str]:
    """Validate recording using artist MBID (most precise)

    Args:
        artist_mbid: MusicBrainz artist ID
        song_title: Song title to validate
        clean_title: Whether to clean title before query (default: False)

    Returns:
        Tuple of (found: bool, method: str)
    """
    # Import clean function
    from radio_monitor.normalization import clean_song_title_for_query

    # Clean title for query
    query_title = clean_title and clean_song_title_for_query(song_title) or song_title

    # Build MBID query
    query = f'arid:{artist_mbid} AND recording:"{query_title}"'
    encoded_query = urllib.parse.quote(query, safe='')

    results = query_musicbrainzRecording(encoded_query, limit=10)
    recordings = results.get('recordings', [])

    # Check for exact match
    for recording in recordings:
        if is_recording_match(recording, song_title, ""):  # Artist implied by MBID
            logger.debug(f"Recording validated by MBID: {song_title}")
            return True, 'mbid'

    return False, 'mbid_not_found'


def validate_recording_by_text(artist_name: str, song_title: str, clean_title: bool = False) -> Tuple[bool, str]:
    """Validate recording using artist name and song title (fallback)

    Args:
        artist_name: Artist name
        song_title: Song title to validate
        clean_title: Whether to clean title before query (default: False)

    Returns:
        Tuple of (found: bool, method: str)
    """
    # Import clean function
    from radio_monitor.normalization import clean_song_title_for_query

    # Clean title for query
    query_title = clean_title and clean_song_title_for_query(song_title) or song_title

    # Build text query
    query = f'recording of:"{query_title}" by:"{artist_name}"'
    encoded_query = urllib.parse.quote(query, safe='')

    results = query_musicbrainzRecording(encoded_query, limit=10)
    recordings = results.get('recordings', [])

    # Check for exact match
    for recording in recordings:
        if is_recording_match(recording, song_title, artist_name):
            logger.debug(f"Recording validated by text query: {artist_name} - {song_title}")
            return True, 'text'

    return False, 'text_not_found'


def validate_recording_with_fallback(artist_mbid: Optional[str], artist_name: str,
                                     song_title: str) -> Tuple[bool, str]:
    """Validate recording with MBID fallback to text query

    This addresses MusicBrainz API inconsistencies where some recordings
    are found via text query but not via MBID query.

    Args:
        artist_mbid: MusicBrainz artist ID (optional)
        artist_name: Artist name (for fallback)
        song_title: Song title to validate

    Returns:
        Tuple of (found: bool, method: str)
        method can be: 'mbid', 'text', 'not_found'
    """
    # Try MBID query first (most precise)
    if artist_mbid and not artist_mbid.startswith('PENDING-'):
        found, method = validate_recording_by_mbid(artist_mbid, song_title, clean_title=False)
        if found:
            return True, 'mbid'

        logger.debug(f"MBID query failed, trying text query for {artist_name} - {song_title}")

    # Fallback to text query
    found, method = validate_recording_by_text(artist_name, song_title, clean_title=False)
    if found:
        return True, 'text_fallback'

    return False, 'not_found'


def validate_recording_exists(artist_mbid: Optional[str], artist_name: str,
                             song_title: str) -> bool:
    """Convenience function to check if recording exists

    Args:
        artist_mbid: MusicBrainz artist ID (optional)
        artist_name: Artist name (required)
        song_title: Song title (required)

    Returns:
        True if recording exists in MusicBrainz
    """
    found, _ = validate_recording_with_fallback(artist_mbid, artist_name, song_title)
    return found
