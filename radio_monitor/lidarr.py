"""
Lidarr Import module for Radio Monitor 1.0

This module handles importing artists to Lidarr using lookup-first approach:
- Lidarr API client (lookup-first)
- Error handling (continue on failure)
- Track imported artists
- CLI command --import-lidarr

Key Principle: Radio artists are already radio-friendly, so no scoring needed.
Just import them directly to Lidarr.

Lookup-First Approach:
1. Lookup artist in Lidarr by MBID (validates MBID, gets metadata)
2. Configure (root folder, quality profile, etc.)
3. Add to Lidarr
4. Handle 409 (already exists) as success
"""

import requests
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


def load_api_key(settings):
    """Load Lidarr API key from settings

    Args:
        settings: Settings dict with lidarr.api_key

    Returns:
        API key string or None
    """
    api_key = settings.get('lidarr', {}).get('api_key', '')

    if not api_key:
        logger.error("Lidarr API key not found in settings")
        return None

    return api_key


def import_artist_to_lidarr(mbid, name, settings):
    """Import artist to Lidarr using lookup-first approach

    This implements Lidarr's recommended flow:
    1. Lookup (validates MBID, gets metadata from MusicBrainz)
    2. Configure (set root folder, quality profile, monitored flag)
    3. Add (POST to Lidarr)

    Args:
        mbid: MusicBrainz artist ID
        name: Artist name (for logging)
        settings: Settings dict with lidarr configuration

    Returns:
        (success, message) tuple where:
        - success: True if imported or already exists, False otherwise
        - message: Human-readable result message
    """
    # Load API key
    api_key = load_api_key(settings)
    if not api_key:
        return False, "API key not found"

    # Get Lidarr URL
    lidarr_url = settings.get('lidarr', {}).get('url', 'http://localhost:8686')

    # Step 1: Lookup (validates MBID, gets metadata)
    lookup_url = f"{lidarr_url}/api/v1/artist/lookup?term=lidarr:{mbid}"

    try:
        response = requests.get(
            lookup_url,
            headers={"X-Api-Key": api_key},
            timeout=30
        )

        if response.status_code != 200:
            logger.warning(f"Lidarr lookup failed for {name}: HTTP {response.status_code}")
            return False, f"Lookup failed: HTTP {response.status_code}"

        artists = response.json()

        if not artists:
            logger.warning(f"MBID {mbid} not found in Lidarr: {name}")
            return False, f"MBID not found in Lidarr"

        artist_data = artists[0]
        logger.info(f"Lookup result for {name} (MBID: {mbid}): has_id = {'id' in artist_data}")

        # If artist has an 'id', they're already in Lidarr
        if 'id' in artist_data:
            logger.info(f"{name} already exists in Lidarr (ID: {artist_data['id']})")
            return True, "Already exists in Lidarr"

        # Step 2: Configure (update fields we want to control)
        payload = artist_data.copy()
        payload['qualityProfileId'] = settings.get('lidarr', {}).get('quality_profile_id', 1)
        payload['metadataProfileId'] = settings.get('lidarr', {}).get('metadata_profile_id', 1)
        payload['monitored'] = settings.get('lidarr', {}).get('monitor_new_artists', True)
        payload['addOptions'] = {
            'monitor': 'all',
            'searchForMissingAlbums': settings.get('lidarr', {}).get('search_for_missing_albums', True)
        }

        # Step 3: Add new artist - need to include root folder path
        payload['rootFolderPath'] = settings.get('lidarr', {}).get('root_folder_path', '/data/music/')
        add_url = f"{lidarr_url}/api/v1/artist"
        response = requests.post(
            add_url,
            json=payload,
            headers={"X-Api-Key": api_key},
            timeout=30
        )

        if response.status_code in [200, 201, 202]:
            logger.info(f"Imported {name} to Lidarr")
            return True, "Imported successfully"
        elif response.status_code == 409:
            logger.info(f"{name} already exists in Lidarr")
            return True, "Already exists in Lidarr"
        else:
            logger.warning(f"Failed to import {name}: HTTP {response.status_code}")
            try:
                error_data = response.json()
                error_msg = error_data[0].get('errorMessage', 'Unknown error') if isinstance(error_data, list) else error_data.get('message', 'Unknown error')
                return False, f"Failed: {error_msg}"
            except:
                return False, f"Failed: HTTP {response.status_code}"

    except requests.exceptions.Timeout:
        logger.warning(f"Lidarr timeout for {name}")
        return False, "Timeout"
    except requests.exceptions.ConnectionError:
        logger.warning(f"Lidarr connection error for {name}")
        return False, "Connection error"
    except requests.exceptions.RequestException as e:
        logger.warning(f"Lidarr request failed for {name}: {e}")
        return False, f"Request error: {e}"
    except Exception as e:
        logger.error(f"Unexpected error importing {name}: {e}")
        return False, f"Unexpected error: {e}"


def import_artists_to_lidarr(db, settings, min_plays=5, dry_run=False):
    """Import multiple artists to Lidarr

    Args:
        db: RadioDatabase instance
        settings: Settings dict
        min_plays: Minimum play count to import
        dry_run: If True, don't actually import (just show what would be imported)

    Returns:
        dict with:
        - total: Number of artists eligible for import
        - imported: Number successfully imported
        - already_exists: Number already in Lidarr
        - failed: Number that failed
        - failed_artists: List of (name, reason) tuples for failures
    """
    # Get artists needing import
    artists = db.get_artists_for_import(min_plays=min_plays)

    if not artists:
        return {
            'total': 0,
            'imported': 0,
            'already_exists': 0,
            'failed': 0,
            'failed_artists': []
        }

    logger.info(f"Found {len(artists)} artists needing import (min_plays={min_plays})")

    imported = 0
    already_exists = 0
    failed = 0
    failed_artists = []
    imported_mbids = []

    for artist in artists:
        mbid = artist['mbid']
        name = artist['name']
        total_plays = artist['total_plays']

        print(f"\nProcessing: {name.encode('ascii', 'ignore').decode('ascii')} ({total_plays} plays)")

        if dry_run:
            print(f"  [DRY RUN] Would import {name} (MBID: {mbid})")
            imported += 1
            imported_mbids.append(mbid)
            continue

        # Import to Lidarr
        success, message = import_artist_to_lidarr(mbid, name, settings)

        if success:
            if "already exists" in message.lower():
                already_exists += 1
                print(f"  [OK] {message}")
            else:
                imported += 1
                print(f"  [OK] {message}")

            # Track successfully imported artists
            imported_mbids.append(mbid)
        else:
            failed += 1
            failed_artists.append((name, message))
            print(f"  [FAIL] {message}")

    # Mark imported artists in database
    if imported_mbids and not dry_run:
        db.mark_artists_imported(imported_mbids)
        print(f"\nMarked {len(imported_mbids)} artists as imported in database")

    result = {
        'total': len(artists),
        'imported': imported,
        'already_exists': already_exists,
        'failed': failed,
        'failed_artists': failed_artists
    }

    # Log activity
    if not dry_run:
        try:
            from radio_monitor.database.activity import log_activity
            severity = 'success' if failed == 0 else 'warning' if failed < len(artists) else 'error'
            log_activity(
                db.get_cursor(),
                event_type='import',
                title=f"Lidarr import complete: {imported} artists",
                description=f"Imported {imported} new artists, {already_exists} already existed, {failed} failed",
                metadata={
                    'total': len(artists),
                    'imported': imported,
                    'already_exists': already_exists,
                    'failed': failed,
                    'failed_artists': failed_artists[:10]  # First 10 failures
                },
                severity=severity,
                source='user'
            )
        except Exception as e:
            logger.error(f"Failed to log import activity: {e}")

    # Send notifications
    if not dry_run:
        try:
            from radio_monitor.notifications import send_notifications
            if result['total'] > 0:
                send_notifications(
                    db,
                    'on_import_complete',
                    'Lidarr Import Complete',
                    f"Imported {result['imported']} artists, {result['already_exists']} already existed, {result['failed']} failed",
                    'success' if result['failed'] == 0 else 'warning',
                    {
                        'total': result['total'],
                        'imported': result['imported'],
                        'already_exists': result['already_exists'],
                        'failed': result['failed']
                    }
                )
        except Exception as e:
            logger.error(f"Failed to send import notifications: {e}")

    return result


def test_lidarr_connection(settings):
    """Test connection to Lidarr

    Args:
        settings: Settings dict with lidarr configuration

    Returns:
        (success, message) tuple
    """
    # Load API key
    api_key = load_api_key(settings)
    if not api_key:
        return False, "API key not found"

    # Get Lidarr URL
    lidarr_url = settings.get('lidarr', {}).get('url', 'http://localhost:8686')

    # Test system/status endpoint
    try:
        # Add explicit timeout for connect and read
        response = requests.get(
            f"{lidarr_url}/api/v1/system/status",
            headers={"X-Api-Key": api_key},
            timeout=(5, 10)  # (connect timeout, read timeout)
        )

        if response.status_code == 200:
            data = response.json()
            version = data.get('version', 'unknown')
            return True, f"Connected (Lidarr {version})"
        else:
            return False, f"HTTP {response.status_code}"

    except requests.exceptions.ConnectionError:
        return False, "Connection refused - Is Lidarr running?"
    except requests.exceptions.Timeout:
        return False, "Connection timeout - Is Lidarr responding?"
    except requests.exceptions.RequestException as e:
        logger.error(f"Lidarr connection error: {e}")
        return False, f"Connection failed: {str(e)}"
    except Exception as e:
        logger.error(f"Lidarr test error: {e}")
        return False, str(e)


def get_lidarr_root_folders(settings):
    """Get available root folders from Lidarr

    Args:
        settings: Settings dict with lidarr configuration

    Returns:
        List of root folder dicts or None
    """
    # Load API key
    api_key = load_api_key(settings)
    if not api_key:
        return None

    # Get Lidarr URL
    lidarr_url = settings.get('lidarr', {}).get('url', 'http://localhost:8686')

    try:
        response = requests.get(
            f"{lidarr_url}/api/v1/rootfolder",
            headers={"X-Api-Key": api_key},
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get root folders: HTTP {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Error getting root folders: {e}")
        return None


def get_lidarr_quality_profiles(settings):
    """Get available quality profiles from Lidarr

    Args:
        settings: Settings dict with lidarr configuration

    Returns:
        List of quality profile dicts or None
    """
    # Load API key
    api_key = load_api_key(settings)
    if not api_key:
        return None

    # Get Lidarr URL
    lidarr_url = settings.get('lidarr', {}).get('url', 'http://localhost:8686')

    try:
        response = requests.get(
            f"{lidarr_url}/api/v1/qualityprofile",
            headers={"X-Api-Key": api_key},
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get quality profiles: HTTP {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Error getting quality profiles: {e}")
        return None


def get_lidarr_metadata_profiles(settings):
    """Get available metadata profiles from Lidarr

    Args:
        settings: Settings dict with lidarr configuration

    Returns:
        List of metadata profile dicts or None
    """
    # Load API key
    api_key = load_api_key(settings)
    if not api_key:
        return None

    # Get Lidarr URL
    lidarr_url = settings.get('lidarr', {}).get('url', 'http://localhost:8686')

    try:
        response = requests.get(
            f"{lidarr_url}/api/v1/metadataprofile",
            headers={"X-Api-Key": api_key},
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get metadata profiles: HTTP {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Error getting metadata profiles: {e}")
        return None
