"""
Song Verification Module - Phase 1
Verifies artists actually recorded the songs they're matched to.

Sources:
- MusicBrainz Recording API (always available)
- Lidarr API (optional, if configured)
"""

import logging
import json
import ssl
import time
import urllib.request
import urllib.error
from urllib.parse import quote
from datetime import datetime
from difflib import SequenceMatcher
import requests

logger = logging.getLogger(__name__)

# Constants
VERIFIED_MB = 'VERIFIED_MB'
VERIFIED_LIDARR = 'VERIFIED_LIDARR'
NOT_FOUND = 'NOT_FOUND'
UNVERIFIED = 'UNVERIFIED'
PENDING = 'PENDING'

# Thresholds
SONG_SIMILARITY_THRESHOLD = 0.85

# Rate limiting (respect MusicBrainz rules)
MUSICBRAINZ_RATE_LIMIT = 1.0  # 1 second between requests
_last_musicbrainz_request = 0

# ============================================================================
# MUSICBRAINZ VERIFICATION
# ============================================================================

def verify_artist_song_musicbrainz(artist_name, song_title, artist_mbid, user_agent=None):
    """
    Verify artist-song relationship using MusicBrainz Recording API.

    This searches MusicBrainz for the recording using arid: query (artist MBID)
    which is the same method used during scraping. This ensures consistency
    between scraping validation and manual verification.

    Args:
        artist_name: Artist name to verify
        song_title: Song title to verify
        artist_mbid: MusicBrainz artist ID to match
        user_agent: User-Agent string for API requests

    Returns:
        Dict with verification result:
        {
            'is_verified': bool,
            'status': str,
            'recording_mbid': str,
            'artist_credit': str,
            'song_similarity': float,
            'reason': str,
            'verified_at': str
        }
    """
    global _last_musicbrainz_request

    if not song_title or not artist_mbid:
        return {
            'is_verified': False,
            'status': NOT_FOUND,
            'reason': 'Missing song_title or artist_mbid'
        }

    logger.info(f"[MusicBrainz] Verifying: {artist_name} - {song_title}")

    try:
        # Import clean function for query (same as scraping validation)
        from radio_monitor.normalization import clean_song_title_for_query

        # Clean title for query (removes features, etc.)
        cleaned_title = clean_song_title_for_query(song_title)

        # Rate limiting
        time_since_last = time.time() - _last_musicbrainz_request
        if time_since_last < MUSICBRAINZ_RATE_LIMIT:
            time.sleep(MUSICBRAINZ_RATE_LIMIT - time_since_last)

        # Use arid: query (same method as scraping validation)
        # This queries by artist MBID directly, which is more precise
        query = f'arid:{artist_mbid} AND recording:"{cleaned_title}"'
        encoded_query = quote(query, safe='')
        url = f"https://musicbrainz.org/ws/2/recording/?query={encoded_query}&fmt=json&limit=100"

        headers = {
            'User-Agent': user_agent or 'RadioMonitor/1.0.0 (https://github.com/allurjj/radio-monitor)'
        }

        req = urllib.request.Request(url, headers=headers)

        # Create SSL context (verification disabled for Windows compatibility)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            _last_musicbrainz_request = time.time()

            if response.status != 200:
                logger.warning(f"MusicBrainz API returned HTTP {response.status}")
                return {
                    'is_verified': False,
                    'status': NOT_FOUND,
                    'reason': f'API error: HTTP {response.status}'
                }

            data = json.loads(response.read().decode('utf-8'))
            recordings = data.get('recordings', [])

            if not recordings:
                logger.warning(f"No recordings found for '{song_title}' with arid:{artist_mbid}")
                return {
                    'is_verified': False,
                    'status': NOT_FOUND,
                    'reason': f'No recordings found for song'
                }

            logger.info(f"Found {len(recordings)} recordings for '{song_title}' (arid:{artist_mbid})")

            # Results are already filtered to our artist (arid: query)
            # Just need to check song similarity and get the first match
            for recording in recordings:
                recording_title = recording.get('title', '')
                recording_mbid = recording.get('id', '')

                # Check song similarity (clean both titles for fair comparison)
                recording_title_clean = clean_song_title_for_query(recording_title)
                song_title_clean = clean_song_title_for_query(song_title)

                song_similarity = SequenceMatcher(
                    None,
                    song_title_clean.lower(),
                    recording_title_clean.lower()
                ).ratio()

                if song_similarity >= SONG_SIMILARITY_THRESHOLD:
                    # Get artist name from first artist credit (for display)
                    artist_credits = recording.get('artist-credit', [])
                    artist_credit_name = artist_credits[0].get('name', artist_name) if artist_credits else artist_name

                    logger.info(
                        f"✅ VERIFIED_MB: {artist_name} - {song_title} "
                        f"(recording: {recording_title}, similarity: {song_similarity:.1%})"
                    )
                    return {
                        'is_verified': True,
                        'status': VERIFIED_MB,
                        'recording_mbid': recording_mbid,
                        'artist_credit': artist_credit_name,
                        'song_similarity': song_similarity,
                        'verified_at': datetime.now().isoformat()
                    }

            # No similarity match found
            logger.warning(f"No recordings met similarity threshold for '{song_title}'")
            return {
                'is_verified': False,
                'status': NOT_FOUND,
                'reason': f'No recordings met {SONG_SIMILARITY_THRESHOLD:.0%} similarity threshold'
            }

    except urllib.error.URLError as e:
        logger.error(f"MusicBrainz verification failed (network error): {e}")
        return {
            'is_verified': False,
            'status': NOT_FOUND,
            'reason': f'Network error: {e}'
        }
    except Exception as e:
        logger.error(f"MusicBrainz verification failed (unexpected error): {e}")
        return {
            'is_verified': False,
            'status': NOT_FOUND,
            'reason': f'Unexpected error: {e}'
        }


# ============================================================================
# LIDARR VERIFICATION
# ============================================================================

def verify_artist_song_lidarr(artist_name, song_title, artist_mbid, settings):
    """
    Verify artist-song relationship using Lidarr API.

    This queries Lidarr for the artist's track list and checks if the song exists.

    Args:
        artist_name: Artist name to verify
        song_title: Song title to verify
        artist_mbid: MusicBrainz artist ID
        settings: Application settings dict

    Returns:
        Dict with verification result
    """
    # Check if Lidarr is configured
    lidarr_url = settings.get('lidarr', {}).get('url')
    lidarr_api_key = settings.get('lidarr', {}).get('api_key')

    if not lidarr_url or not lidarr_api_key:
        return {
            'is_verified': False,
            'status': NOT_FOUND,
            'reason': 'Lidarr not configured'
        }

    logger.info(f"[Lidarr] Verifying: {artist_name} - {song_title}")

    try:
        # Get artist from Lidarr by MBID
        lookup_url = f"{lidarr_url}/api/v1/artist/lookup?term=lidarr:{artist_mbid}"
        response = requests.get(
            lookup_url,
            headers={"X-Api-Key": lidarr_api_key},
            timeout=10
        )

        if response.status_code != 200:
            logger.warning(f"Lidarr lookup failed: HTTP {response.status_code}")
            return {
                'is_verified': False,
                'status': NOT_FOUND,
                'reason': f'Lidarr API error: HTTP {response.status_code}'
            }

        artists = response.json()

        if not artists:
            logger.info(f"Artist '{artist_name}' (MBID: {artist_mbid}) not found in Lidarr")
            return {
                'is_verified': False,
                'status': NOT_FOUND,
                'reason': 'Artist not in Lidarr'
            }

        artist_data = artists[0]
        artist_id = artist_data.get('id')
        logger.info(f"[Lidarr] Found artist '{artist_name}' with ID: {artist_id}")

        # If artist has an ID, they're in Lidarr - get their tracks
        if artist_id:
            # Use track endpoint instead of album endpoint (tracks are included by default)
            tracks_url = f"{lidarr_url}/api/v1/track?artistId={artist_id}&includeAllArtistAlbums=true"
            tracks_response = requests.get(
                tracks_url,
                headers={"X-Api-Key": lidarr_api_key},
                timeout=15
            )

            if tracks_response.status_code == 200:
                tracks = tracks_response.json()
                logger.info(f"[Lidarr] Found {len(tracks)} tracks for '{artist_name}'")

                # Log first track structure to debug
                if tracks:
                    logger.info(f"[Lidarr] Sample track keys: {list(tracks[0].keys())}")
                    logger.info(f"[Lidarr] Sample track data: {tracks[0]}")

                # Search through all tracks
                for track in tracks:
                    track_title = track.get('title', '')
                    track_similarity = SequenceMatcher(
                        None,
                        song_title.lower(),
                        track_title.lower()
                    ).ratio()

                    logger.debug(f"[Lidarr] Checking track: '{track_title}' vs '{song_title}' (similarity: {track_similarity:.1%})")

                    if track_similarity >= SONG_SIMILARITY_THRESHOLD:
                        # Found a match! Now fetch album details using albumId
                        album_title = None
                        album_id = track.get('albumId')

                        if album_id:
                            try:
                                album_url = f"{lidarr_url}/api/v1/album/{album_id}"
                                album_response = requests.get(
                                    album_url,
                                    headers={"X-Api-Key": lidarr_api_key},
                                    timeout=10
                                )
                                if album_response.status_code == 200:
                                    album_data = album_response.json()
                                    album_title = album_data.get('title')
                                    logger.info(f"[Lidarr] Fetched album: {album_title} (ID: {album_id})")
                            except Exception as e:
                                logger.warning(f"[Lidarr] Failed to fetch album {album_id}: {e}")

                        logger.info(
                            f"✅ VERIFIED_LIDARR: {artist_name} - {song_title} "
                            f"(track: {track_title}, album: {album_title}, similarity: {track_similarity:.1%})"
                        )
                        return {
                            'is_verified': True,
                            'status': VERIFIED_LIDARR,
                            'track_title': track_title,
                            'album_title': album_title,
                            'track_similarity': track_similarity,
                            'lidarr_artist_id': artist_id,  # Include for marking as imported
                            'verified_at': datetime.now().isoformat()
                        }

                logger.info(f"[Lidarr] Checked {len(tracks)} tracks, no match found for '{song_title}'")
            else:
                logger.warning(f"[Lidarr] Failed to get tracks: HTTP {tracks_response.status_code}")
        else:
            logger.warning(f"[Lidarr] Artist '{artist_name}' has no ID in Lidarr")

        # Song not found in artist's Lidarr catalog
        logger.info(f"Song '{song_title}' not found in {artist_name}'s Lidarr catalog")
        return {
            'is_verified': False,
            'status': NOT_FOUND,
            'reason': 'Song not found in artist catalog'
        }

    except requests.exceptions.Timeout:
        logger.error(f"Lidarr verification timed out")
        return {
            'is_verified': False,
            'status': NOT_FOUND,
            'reason': 'Request timeout'
        }
    except requests.exceptions.ConnectionError:
        logger.error(f"Lidarr connection error")
        return {
            'is_verified': False,
            'status': NOT_FOUND,
            'reason': 'Connection error'
        }
    except Exception as e:
        logger.error(f"Lidarr verification failed: {e}")
        return {
            'is_verified': False,
            'status': NOT_FOUND,
            'reason': f'Unexpected error: {e}'
        }


# ============================================================================
# ORCHESTRATION
# ============================================================================

def verify_artist_song(artist_name, song_title, artist_mbid, settings, sources=None):
    """
    Verify artist-song relationship using multiple sources.

    Args:
        artist_name: Artist name to verify
        song_title: Song title to verify
        artist_mbid: MusicBrainz artist ID
        settings: Application settings dict
        sources: List of sources to use ['musicbrainz', 'lidarr']

    Returns:
        Dict with verification results from all sources
    """
    if sources is None:
        sources = ['musicbrainz', 'lidarr']

    logger.info(f"Verifying: {artist_name} - {song_title} (sources: {sources})")

    results = {}
    overall_status = UNVERIFIED

    # MusicBrainz verification (always first)
    if 'musicbrainz' in sources:
        user_agent = settings.get('musicbrainz', {}).get('user_agent') if settings else None
        results['musicbrainz'] = verify_artist_song_musicbrainz(
            artist_name, song_title, artist_mbid, user_agent
        )

        if results['musicbrainz']['is_verified']:
            overall_status = VERIFIED_MB

    # Lidarr verification (optional)
    if 'lidarr' in sources:
        results['lidarr'] = verify_artist_song_lidarr(
            artist_name, song_title, artist_mbid, settings
        )

        if results['lidarr']['is_verified']:
            overall_status = VERIFIED_LIDARR

    # If neither verified, check if we got a "not found" result
    if overall_status == UNVERIFIED:
        if 'musicbrainz' in results and not results['musicbrainz']['is_verified']:
            overall_status = NOT_FOUND

    return {
        'overall_status': overall_status,
        'sources': results,
        'verified_at': datetime.now().isoformat()
    }
