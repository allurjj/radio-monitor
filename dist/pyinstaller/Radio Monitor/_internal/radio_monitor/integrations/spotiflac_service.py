"""
SpotiFLAC Service Layer for Radio Monitor

This module provides a wrapper around SpotiFLAC for Radio Monitor integration,
including Lidarr naming convention support and automatic file movement.
"""

import os
import re
import shutil
import logging
import requests
import uuid
import time
import asyncio
import glob
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field

from radio_monitor.integrations.spotiflac import (
    get_filtered_data,
    parse_uri,
    SpotifyInvalidUrlException,
    DownloadManager,
    DownloadStatus,
)
from radio_monitor.integrations.spotiflac.tidalDL import TidalDownloader
from radio_monitor.integrations.spotiflac.qobuzDL import QobuzDownloader
from radio_monitor.integrations.spotiflac.amazonDL import AmazonDownloader
from radio_monitor.integrations.spotiflac.deezerDL import DeezerDownloader
from radio_monitor.integrations.spotiflac.youtubeDL import YouTubeDownloader
from radio_monitor.integrations.spotiflac.spotidownloaderDL import SpotiDownloader
from radio_monitor.gui import load_settings

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    """Result of a SpotiFLAC download operation"""
    success: bool
    job_id: str
    file_path: str = ""
    service_used: str = ""
    file_size_mb: float = 0.0
    error: str = ""
    tracks_downloaded: List[str] = field(default_factory=list)
    total_tracks: int = 0


def get_lidarr_naming_convention(settings: Dict, url_type: str = 'track') -> str:
    """
    Query Lidarr for user's current naming convention

    Args:
        settings: Radio Monitor settings dictionary
        url_type: 'track' or 'album'

    Returns:
        SpotiFLAC-compatible filename format string
    """
    lidarr_url = settings.get('lidarr', {}).get('url')
    api_key = settings.get('lidarr', {}).get('api_key')

    if not lidarr_url or not api_key:
        raise ValueError("Lidarr URL or API key not configured")

    try:
        # Get Lidarr naming config
        response = requests.get(
            f"{lidarr_url}/api/v1/config/naming",
            headers={"X-Api-Key": api_key},
            timeout=10
        )

        if response.status_code != 200:
            raise ValueError(f"Lidarr API returned status {response.status_code}")

        naming_config = response.json()

        if url_type == 'track':
            # Lidarr format example: "{Artist Name} - {Album Name} - {Track Number} - {Track Title}"
            # Convert to SpotiFLAC format: "{artist} - {album} - {track} - {title}"
            lidarr_pattern = naming_config.get('standardTrackFormat', '')
            return convert_lidarr_to_spotiflac_format(lidarr_pattern)

        elif url_type == 'album':
            # For albums, we use both track and folder formats
            lidarr_pattern = naming_config.get('standardTrackFormat', '')
            folder_pattern = naming_config.get('albumFolderFormat', '')

            return {
                'filename': convert_lidarr_to_spotiflac_format(lidarr_pattern),
                'folder': convert_lidarr_to_spotiflac_format(folder_pattern)
            }

    except Exception as e:
        logger.warning(f"Failed to get Lidarr naming convention: {e}")
        raise


def convert_lidarr_to_spotiflac_format(lidarr_format: str) -> str:
    """
    Convert Lidarr naming tokens to SpotiFLAC format tokens

    Lidarr tokens → SpotiFLAC tokens:
    {Artist Name} → {artist}
    {Album Name} → {album}
    {Track Title} → {title}
    {Track Number} → {track}
    {Release Year} → {year}
    {Medium Number} → {disc}
    {MusicBrainz Id} → {isrc}
    """
    conversion_map = {
        'Artist Name': 'artist',
        'Album Name': 'album',
        'Album Title': 'album',
        'Track Title': 'title',
        'Track Number': 'track',
        'Release Year': 'year',
        'Medium Number': 'disc',
        'MusicBrainz Id': 'isrc',
        'Artist Name-': 'artist',  # Handle Lidarr's artist sorting
    }

    result = lidarr_format
    for lidarr_token, spotiflac_token in conversion_map.items():
        result = result.replace('{%s}' % lidarr_token, '{%s}' % spotiflac_token)

    return result


def sanitize_filename_component(value: str) -> str:
    """Sanitize filename component by removing invalid characters"""
    if not value:
        return ""
    sanitized = re.sub(r'[<>:"/\\|?*]', lambda m: "'" if m.group() == '"' else '_', value)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized


def format_custom_filename(template: str, track_info: Dict, position: int = 1, ext: str = ".flac") -> str:
    """Format filename using template and track metadata"""
    year = ""
    if track_info.get('release_date'):
        year = track_info['release_date'].split("-")[0] if "-" in track_info['release_date'] else track_info['release_date']

    duration = ""
    if track_info.get('duration_ms'):
        total_seconds = track_info['duration_ms'] // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        duration = f"{minutes:02d}:{seconds:02d}"

    replacements = {
        "title": sanitize_filename_component(track_info.get('title', 'Unknown Title')),
        "artist": sanitize_filename_component(track_info.get('artists', 'Unknown Artist')),
        "album": sanitize_filename_component(track_info.get('album', 'Unknown Album')),
        "track_number": f"{track_info.get('track_number', position):02d}",
        "track": f"{track_info.get('track_number', position):02d}",
        "date": sanitize_filename_component(track_info.get('release_date', '')),
        "year": year,
        "position": f"{position:02d}",
        "isrc": sanitize_filename_component(track_info.get('isrc', '')),
        "duration": duration,
    }

    result = template
    for key, value in replacements.items():
        result = result.replace(f"{{{key}}}", value)

    if not result.lower().endswith(ext):
        result += ext
    return re.sub(r'\s+', ' ', result).strip()


class SpotiFLACService:
    """
    Service layer for SpotiFLAC integration in Radio Monitor

    This class provides high-level methods for downloading music
    with automatic integration with Lidarr naming conventions and file organization.
    """

    def __init__(self, settings: Dict = None):
        """
        Initialize SpotiFLAC service

        Args:
            settings: Radio Monitor settings dictionary
        """
        self.settings = settings or load_settings() or {}
        self.spotiflac_config = self.settings.get('spotiflac', {})

        # Configuration
        self.temp_download_dir = self.spotiflac_config.get('temp_download_dir', './temp_downloads')
        self.auto_move = self.spotiflac_config.get('auto_move_to_lidarr', True)
        self.preferred_quality = self.spotiflac_config.get('preferred_quality', 'flac')
        self.use_lidarr_naming = self.spotiflac_config.get('use_lidarr_naming_convention', True)
        self.download_timeout = self.spotiflac_config.get('download_timeout', 300)

        # Track active downloads
        self._active_jobs = {}
        self._download_managers = {}

        # Ensure temp directory exists
        os.makedirs(self.temp_download_dir, exist_ok=True)

        logger.info(f"SpotiFLAC Service initialized with auto_move={self.auto_move}")

    def get_filename_format(self, url_type: str = 'track') -> str:
        """
        Get filename format from Lidarr or settings

        Args:
            url_type: 'track' or 'album'

        Returns:
            Format string or dict with 'filename' and 'folder' keys
        """
        if self.use_lidarr_naming:
            try:
                return get_lidarr_naming_convention(self.settings, url_type)
            except Exception as e:
                logger.warning(f"Failed to get Lidarr naming convention: {e}, using fallback")

        # Fallback to custom format or default
        custom_format = self.spotiflac_config.get('custom_filename_format', '{title} - {artist}')

        if url_type == 'album':
            return {
                'filename': custom_format,
                'folder': '{album}'  # Simple album folder
            }

        return custom_format

    def search_spotify(self, song_title: str, artist_name: str) -> List[Dict]:
        """
        Search Spotify for matching tracks using Spotify Web API

        Args:
            song_title: Song title to search for
            artist_name: Artist name to search for

        Returns:
            List of track dictionaries with keys: url, title, artist, album, year, duration, isrc
        """
        query = f"track:{song_title} artist:{artist_name}"

        try:
            # Get access token using SpotiFLAC's method (has proper credentials)
            access_token = self._get_spotify_access_token()

            if not access_token:
                logger.warning("Could not get Spotify access token for search")
                return []

            # Search for tracks using Spotify Web API
            search_url = "https://api.spotify.com/v1/search"
            params = {
                'q': query,
                'type': 'track',
                'limit': 10
            }

            headers = {
                'Authorization': f'Bearer {access_token}',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(search_url, params=params, headers=headers, timeout=10)

            if response.status_code != 200:
                logger.warning(f"Spotify API returned status {response.status_code}")
                if response.status_code == 400:
                    logger.warning("Bad request - check query format and access token")
                return []

            data = response.json()
            tracks = data.get('tracks', {}).get('items', [])

            results = []
            for track in tracks:
                # Format duration
                duration_ms = track.get('duration_ms', 0)
                minutes = duration_ms // 60000
                seconds = (duration_ms % 60000) // 1000
                duration = f"{minutes}:{seconds:02d}"

                # Get album and year
                album = track.get('album', {})
                album_name = album.get('name', 'Unknown Album')
                release_date = album.get('release_date', '')
                year = release_date.split('-')[0] if release_date else ''

                # Format artists
                artists = track.get('artists', [])
                artist_names = ", ".join([a.get('name', '') for a in artists])

                results.append({
                    'url': track.get('external_urls', {}).get('spotify', ''),
                    'title': track.get('name', ''),
                    'artist': artist_names,
                    'album': album_name,
                    'year': year,
                    'duration': duration,
                    'isrc': track.get('external_ids', {}).get('isrc', '')
                })

            logger.info(f"Found {len(results)} tracks on Spotify for query: {query}")
            return results

        except Exception as e:
            logger.error(f"Error searching Spotify: {e}")
            return []

    def _get_spotify_access_token(self) -> Optional[str]:
        """
        Get Spotify access token using SpotiFLAC's credentials

        Returns:
            Access token string or None
        """
        try:
            # Use SpotiFLAC's get_access_token function which has proper credentials
            from radio_monitor.integrations.spotiflac.getMetadata import get_access_token

            token_response = get_access_token()

            if isinstance(token_response, dict):
                if "error" in token_response:
                    logger.warning(f"Failed to get Spotify token: {token_response['error']}")
                    return None

                token = token_response.get("accessToken", token_response.get("access_token"))
                if token:
                    logger.debug("Successfully obtained Spotify access token")
                    return token

            elif isinstance(token_response, str):
                return token_response

        except Exception as e:
            logger.warning(f"Failed to get Spotify access token: {e}")

        return None

    def _interpret_download_error(self, error_str: str) -> str:
        """
        Interpret SpotiFLAC errors into user-friendly messages

        Args:
            error_str: Raw error message from SpotiFLAC

        Returns:
            User-friendly error message
        """
        error_lower = error_str.lower()

        # External API failures
        if 'tidal link not found in html' in error_lower or 'amazon link not found in html' in error_lower:
            return ("External API issue: song.link service is not responding properly. "
                    "This is a third-party service that SpotiFLAC relies on to find music links. "
                    "Try again later, or use YouTube as the download source (most reliable).")

        if 'user authentication is required' in error_lower:
            return ("Service authentication error: The download service requires a login. "
                    "This is a temporary issue with the external API. Try using YouTube instead.")

        if 'rate limit' in error_lower or 'too many requests' in error_lower:
            return ("Rate limited: The song.link API is limiting requests. This is a temporary restriction. "
                    "Wait 1-2 minutes and try again, or use YouTube as the download source (no rate limits).")

        if 'dns' in error_lower or 'connection' in error_lower or 'timeout' in error_lower:
            return ("Network error: Could not connect to external download services. "
                    "Check your internet connection and try again.")

        if 'token' in error_lower and 'spotify' in error_lower:
            return ("Spotify API error: Could not authenticate with Spotify. "
                    "This is usually temporary. Try again in a few minutes.")

        # Default error
        return f"Download failed: {error_str}"

    def _check_external_api_health(self) -> Dict:
        """
        Check if external APIs used by SpotiFLAC are reachable

        Returns:
            Dict with keys: all_healthy (bool), issues (list of str)

        Note: This is a basic DNS check only. Making actual API calls causes rate limiting.
        """
        import socket
        issues = []

        # Check DNS resolution for key domains (no actual API calls to avoid rate limiting)
        domains_to_check = [
            ('api.song.link', 'song.link API (Tidal, Amazon)'),
            ('tidal.kinoplus.online', 'Tidal API'),
        ]

        for domain, description in domains_to_check:
            try:
                socket.gethostbyname(domain)
            except socket.gaierror:
                issues.append(f"{description} DNS resolution failed (domain: {domain})")
            except Exception as e:
                issues.append(f"{description} unreachable: {e}")

        # Add Qobuz to DNS check
        domains_to_check.append(('qbz.afkarxyz.fun', 'Qobuz API'))

        for domain, description in domains_to_check:
            try:
                socket.gethostbyname(domain)
            except socket.gaierror:
                issues.append(f"{description} DNS resolution failed (domain: {domain})")
            except Exception as e:
                issues.append(f"{description} unreachable: {e}")

        return {
            'all_healthy': len(issues) == 0,
            'issues': issues
        }

    def get_spotify_metadata(self, spotify_url: str) -> Dict:
        """
        Get metadata from Spotify URL

        Args:
            spotify_url: Spotify track/album URL

        Returns:
            Dictionary with metadata including tracks list
        """
        try:
            metadata = get_filtered_data(spotify_url)

            if "error" in metadata:
                raise ValueError(f"Error fetching Spotify metadata: {metadata['error']}")

            return metadata

        except SpotifyInvalidUrlException as e:
            raise ValueError(f"Invalid Spotify URL: {str(e)}")
        except Exception as e:
            logger.error(f"Error fetching Spotify metadata: {e}")
            raise

    def download_track(self, spotify_url: str, song_title: str, artist_name: str,
                      services: List[str] = None) -> Dict:
        """
        Download track using SpotiFLAC (blocks until complete)

        Args:
            spotify_url: Spotify track URL
            song_title: Song title (for fallback)
            artist_name: Artist name (for fallback)
            services: List of services to try (default: from settings)

        Returns:
            Dict with keys: success, job_id, file_path, service_used, file_size_mb, error
        """
        logger.info(f"Starting SpotiFLAC download for: {song_title} by {artist_name}")
        logger.info(f"Spotify URL: {spotify_url}")

        # Use default services if not specified
        if services is None:
            services = self.spotiflac_config.get('default_services', ['tidal', 'youtube'])

        logger.info(f"Services to try (in priority order): {services}")

        # Create output directory if it doesn't exist
        os.makedirs(self.temp_download_dir, exist_ok=True)

        # Generate job ID for tracking
        job_id = str(uuid.uuid4())
        logger.info(f"Job ID: {job_id}")

        try:
            # Use SpotiFLAC's native download function
            import sys
            from io import StringIO

            logger.info("Calling SpotiFLAC function...")

            # Import and call SpotiFLAC's main function
            from radio_monitor.integrations.spotiflac.spotiflac import SpotiFLAC

            # Get filename format
            filename_format = self.get_filename_format('track')
            logger.info(f"Filename format: {filename_format}")

            # Call SpotiFLAC (this blocks until complete)
            # NOTE: NOT suppressing output so we can see what SpotiFLAC is doing
            logger.info("Starting SpotiFLAC download (this may take a while)...")
            SpotiFLAC(
                url=spotify_url,
                output_dir=self.temp_download_dir,
                services=services,
                filename_format=filename_format,
                use_track_numbers=True,
                use_artist_subfolders=False,
                use_album_subfolders=False
            )
            logger.info("SpotiFLAC function completed")

            logger.info("Checking for downloaded files...")

            # Check if file was downloaded
            # IMPORTANT: SpotiFLAC creates subdirectories for albums/playlists
            # We need to scan recursively and find the most recently modified file
            downloaded_files = []
            for root, dirs, files in os.walk(self.temp_download_dir):
                for file in files:
                    if file.endswith(('.mp3', '.flac', '.m4a', '.ogg')):
                        full_path = os.path.join(root, file)
                        # Check all files (not just recent ones) and sort by modification time
                        downloaded_files.append(full_path)
                        logger.info(f"Found audio file: {full_path} (modified: {datetime.fromtimestamp(os.path.getmtime(full_path))})")

            if downloaded_files:
                # Get the most recent file
                downloaded_file = max(downloaded_files, key=os.path.getmtime)
                file_size_mb = os.path.getsize(downloaded_file) / (1024 * 1024)

                # Determine service from file extension
                ext = os.path.splitext(downloaded_file)[1].lower()

                # Map extensions to services
                extension_to_service = {
                    '.flac': 'tidal',      # Tidal, Qobuz, Deezer, and Spotify provide FLAC
                    '.m4a': 'amazon',      # Amazon provides M4A
                    '.mp3': 'youtube'      # YouTube provides MP3
                }

                service_used = extension_to_service.get(ext, services[0] if services else 'unknown')

                logger.info(f"Download successful: {downloaded_file} ({file_size_mb:.2f} MB) via {service_used} (ext: {ext})")

                self._active_jobs[job_id] = {
                    'status': 'completed',
                    'service': service_used,
                    'file_path': downloaded_file,
                    'error': None
                }

                return {
                    'success': True,
                    'job_id': job_id,
                    'file_path': downloaded_file,
                    'service_used': service_used,
                    'file_size_mb': file_size_mb
                }
            else:
                error_msg = "Download completed but no file found"
                logger.warning(error_msg)
                self._active_jobs[job_id] = {
                    'status': 'failed',
                    'error': error_msg,
                    'service': services[-1] if services else 'unknown'
                }

                return {
                    'success': False,
                    'job_id': job_id,
                    'error': error_msg
                }

        except Exception as e:
            error_str = str(e)
            logger.error(f"Error downloading track: {e}", exc_info=True)

            # Provide user-friendly error messages
            friendly_error = self._interpret_download_error(error_str)

            self._active_jobs[job_id] = {
                'status': 'failed',
                'error': friendly_error,
                'service': 'unknown'
            }

            return {
                'success': False,
                'job_id': job_id,
                'error': friendly_error
            }

    def download_album(self, spotify_url: str, artist_name: str, album_name: str,
                      services: List[str] = None) -> Dict:
        """
        Download entire album using SpotiFLAC (blocks until complete)

        Args:
            spotify_url: Spotify album URL
            artist_name: Artist name
            album_name: Album name
            services: List of services to try (default: from settings)

        Returns:
            Dict with keys: success, job_id, tracks_downloaded, total_tracks, service_used, error
        """
        # Use default services if not specified
        if services is None:
            services = self.spotiflac_config.get('default_services', ['tidal', 'youtube'])

        logger.info(f"Services to try (in priority order): {services}")
        if not api_health['all_healthy']:
            logger.warning(f"External API issues detected: {api_health['issues']}")
            logger.info("Will attempt download anyway, but some services may fail")

        # Create output directory if it doesn't exist
        os.makedirs(self.temp_download_dir, exist_ok=True)

        # Generate job ID for tracking
        job_id = str(uuid.uuid4())

        try:
            # Use SpotiFLAC's native download function
            import sys
            from io import StringIO

            # Capture stdout to suppress SpotiFLAC's print statements
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = StringIO()
            sys.stderr = StringIO()

            try:
                # Import and call SpotiFLAC's main function
                from radio_monitor.integrations.spotiflac.spotiflac import SpotiFLAC

                # Get filename format
                format_config = self.get_filename_format('album')
                if isinstance(format_config, dict):
                    filename_format = format_config.get('filename', '{title} - {artist}')
                else:
                    filename_format = format_config

                # Call SpotiFLAC (this blocks until complete)
                SpotiFLAC(
                    url=spotify_url,
                    output_dir=self.temp_download_dir,
                    services=services,
                    filename_format=filename_format,
                    use_track_numbers=True,
                    use_artist_subfolders=False,
                    use_album_subfolders=False
                )

            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

            # Check if files were downloaded
            downloaded_files = []
            for root, dirs, files in os.walk(self.temp_download_dir):
                for file in files:
                    if file.endswith(('.mp3', '.flac', '.m4a')):
                        full_path = os.path.join(root, file)
                        # Check if it's recent (created in last 10 minutes for albums)
                        if os.path.getmtime(full_path) > time.time() - 600:
                            downloaded_files.append(full_path)

            if downloaded_files:
                # Get the most recent file to determine service
                most_recent_file = max(downloaded_files, key=os.path.getmtime)
                ext = os.path.splitext(most_recent_file)[1].lower()
                if ext == '.flac':
                    service_used = 'tidal'
                elif ext == '.m4a':
                    service_used = 'amazon'
                elif ext == '.mp3':
                    service_used = 'youtube'
                else:
                    service_used = services[0] if services else 'unknown'

                self._active_jobs[job_id] = {
                    'status': 'completed',
                    'type': 'album',
                    'total_tracks': len(downloaded_files),
                    'files_downloaded': downloaded_files,
                    'service_used': service_used,
                    'errors': []
                }

                return {
                    'success': True,
                    'job_id': job_id,
                    'tracks_downloaded': downloaded_files,
                    'total_tracks': len(downloaded_files),
                    'service_used': service_used
                }
            else:
                error_msg = "Album download completed but no files found"
                self._active_jobs[job_id] = {
                    'status': 'failed',
                    'type': 'album',
                    'errors': [error_msg]
                }

                return {
                    'success': False,
                    'job_id': job_id,
                    'error': error_msg,
                    'total_tracks': 0
                }

        except Exception as e:
            error_str = str(e)
            logger.error(f"Error downloading album: {e}", exc_info=True)

            # Provide user-friendly error messages
            friendly_error = self._interpret_download_error(error_str)

            self._active_jobs[job_id] = {
                'status': 'failed',
                'type': 'album',
                'errors': [friendly_error]
            }

            return {
                'success': False,
                'job_id': job_id,
                'error': friendly_error,
                'total_tracks': 0
            }

    def _download_from_service(self, service: str, track_info: Dict, output_dir: str,
                               filename_format: str, position: int = None) -> Optional[str]:
        """Download track from specific service"""
        track_number = position or track_info.get('track_number', 1)

        if service == 'tidal':
            downloader = TidalDownloader()
            return downloader.download_by_spotify_id(
                spotify_track_id=track_info['id'],
                isrc=track_info.get('isrc'),
                output_dir=output_dir,
                filename_format=filename_format,
                include_track_number=True,
                position=track_number,
                spotify_track_name=track_info['title'],
                spotify_artist_name=track_info['artists'],
                spotify_album_name=track_info['album'],
                spotify_album_artist=track_info['album_artist'],
                spotify_release_date=track_info.get('release_date'),
                use_album_track_number=True,
                spotify_cover_url=track_info.get('cover_url')
            )

        elif service == 'deezer':
            if not track_info.get('isrc'):
                raise ValueError("No ISRC available for Deezer download")
            downloader = DeezerDownloader()
            result = asyncio.run(downloader.download_by_isrc(track_info['isrc'], output_dir))
            if result:
                flac_files = glob.glob(os.path.join(output_dir, "*.flac"))
                if flac_files:
                    return max(flac_files, key=os.path.getctime)
            raise ValueError("Deezer download failed")

        elif service == 'qobuz':
            if not track_info.get('isrc'):
                raise ValueError("No ISRC available for Qobuz download")
            downloader = QobuzDownloader()
            return downloader.download_by_isrc(
                isrc=track_info['isrc'],
                output_dir=output_dir,
                quality="6",
                filename_format=filename_format,
                include_track_number=True,
                position=track_number,
                spotify_track_name=track_info['title'],
                spotify_artist_name=track_info['artists'],
                spotify_album_name=track_info['album'],
                spotify_album_artist=track_info['album_artist'],
                spotify_release_date=track_info.get('release_date'),
                use_album_track_number=True,
                spotify_cover_url=track_info.get('cover_url')
            )

        elif service == 'amazon':
            downloader = AmazonDownloader()
            return downloader.download_by_spotify_id(
                spotify_track_id=track_info['id'],
                output_dir=output_dir,
                isrc=track_info.get('isrc'),
                filename_format=filename_format,
                include_track_number=True,
                position=track_number,
                spotify_track_name=track_info['title'],
                spotify_artist_name=track_info['artists'],
                spotify_album_name=track_info['album'],
                spotify_album_artist=track_info['album_artist'],
                spotify_release_date=track_info.get('release_date'),
                use_album_track_number=True,
                spotify_cover_url=track_info.get('cover_url')
            )

        elif service == 'youtube':
            downloader = YouTubeDownloader()
            return downloader.download_by_spotify_id(
                spotify_track_id=track_info['id'],
                output_dir=output_dir,
                spotify_track_name=track_info['title'],
                spotify_artist_name=track_info['artists'],
                spotify_album_name=track_info['album'],
                spotify_album_artist=track_info['album_artist'],
                spotify_release_date=track_info.get('release_date'),
                spotify_track_number=track_number,
                spotify_total_tracks=1,
                spotify_disc_number=1,
                spotify_total_discs=1,
                spotify_cover_url=track_info.get('cover_url')
            )

        elif service == 'spoti':
            downloader = SpotiDownloader()
            return downloader.download_by_spotify_id(
                spotify_track_id=track_info['id'],
                output_dir=output_dir,
                spotify_track_name=track_info['title'],
                spotify_artist_name=track_info['artists'],
                spotify_album_name=track_info['album'],
                spotify_album_artist=track_info['album_artist'],
                spotify_release_date=track_info.get('release_date'),
                spotify_track_number=track_number,
                spotify_total_tracks=1,
                spotify_disc_number=1,
                spotify_total_discs=1,
                spotify_cover_url=track_info.get('cover_url')
            )

        else:
            raise ValueError(f"Unknown service: {service}")

    def _format_artists(self, artists_list) -> str:
        """Format list of artist dicts to string"""
        if isinstance(artists_list, list):
            return ", ".join([a.get("name", "Unknown") if isinstance(a, dict) else str(a) for a in artists_list])
        return str(artists_list) if artists_list else "Unknown Artist"

    def _extract_cover_art(self, data: Dict, key_primary: str = "images", key_secondary: str = "album") -> str:
        """Extract cover art URL from metadata"""
        img_data = data.get(key_primary)

        if img_data and isinstance(img_data, str):
            return img_data

        if img_data and isinstance(img_data, list) and len(img_data) > 0:
            if isinstance(img_data[0], dict):
                return img_data[0].get("url", "")
            if isinstance(img_data[0], str):
                return img_data[0]

        if key_secondary and key_secondary in data:
            album_data = data[key_secondary]
            if isinstance(album_data, dict):
                return self._extract_cover_art(album_data, "images", None)

        return ""

    def get_download_url_type(self, url: str) -> str:
        """Determine if URL is track, album, or playlist"""
        try:
            url_info = parse_uri(url)
            return url_info.get("type", "unknown")
        except Exception:
            return "unknown"

    def auto_move_to_lidarr_folder(self, source_file: str, artist_name: str, lidarr_path: str,
                                   url_type: str = 'track') -> str:
        """Automatically move downloaded file to artist's Lidarr folder"""
        try:
            # Validate source file exists
            if not os.path.exists(source_file):
                raise FileNotFoundError(f"Source file not found: {source_file}")

            # Clean up artist name (remove extra spaces)
            artist_name_clean = ' '.join(artist_name.split())

            logger.info(f"Auto-moving file: {source_file}")
            logger.info(f"Artist name (cleaned): {artist_name_clean}")

            # First, try to get the actual artist folder path from Lidarr API
            # This handles accented characters correctly (e.g., "Céline Dion" vs "Celine Dion")
            artist_folder = None
            try:
                from radio_monitor.lidarr import lookup_artist_by_name

                result = lookup_artist_by_name(artist_name, self.settings)

                if result['found'] and result['artist']:
                    artist_data = result['artist']

                    # Lidarr returns the actual folder path in the 'path' field
                    # This path has the correct accents and matches what's on disk
                    lidarr_artist_path = artist_data.get('path')

                    if lidarr_artist_path:
                        # Normalize the path for platform compatibility
                        artist_folder = self._normalize_path_for_platform(lidarr_artist_path)
                        logger.info(f"Using actual Lidarr artist path: {repr(artist_folder)}")

            except Exception as e:
                logger.warning(f"Failed to lookup artist folder from Lidarr API: {e}")

            # Fallback: Use the provided lidarr_path
            if artist_folder is None:
                # Normalize Lidarr path for Windows/Docker compatibility
                # When running as Windows .exe with Docker Lidarr, paths might mismatch
                normalized_lidarr_path = self._normalize_path_for_platform(lidarr_path)

                logger.info(f"Lidarr path (original): {repr(lidarr_path)}")
                logger.info(f"Lidarr path (normalized): {repr(normalized_lidarr_path)}")

                # Get filename format
                filename_format = self.get_filename_format(url_type)

                # IMPORTANT: Don't duplicate artist name in path
                # Check if lidarr_path already includes artist name
                if artist_name_clean in normalized_lidarr_path:
                    # Artist name already in path, use it directly
                    artist_folder = normalized_lidarr_path
                    logger.info(f"Artist name already in Lidarr path, using as-is")
                else:
                    # Artist name not in path, add it
                    artist_folder = os.path.join(normalized_lidarr_path, artist_name_clean)
                    logger.info(f"Adding artist name to Lidarr path")

            logger.info(f"Artist folder: {artist_folder}")

            # Create artist folder if it doesn't exist
            os.makedirs(artist_folder, exist_ok=True)

            # Get file extension
            _, ext = os.path.splitext(source_file)

            # Use original filename
            base_name = os.path.basename(source_file)
            dest_filename = base_name

            destination_path = os.path.join(artist_folder, dest_filename)

            logger.info(f"Destination path: {destination_path}")

            # Handle filename collisions
            if os.path.exists(destination_path):
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                name, ext = os.path.splitext(dest_filename)
                dest_filename = f"{name}_{timestamp}{ext}"
                destination_path = os.path.join(artist_folder, dest_filename)

                logger.info(f"File exists, using new filename: {dest_filename}")

            # Move file
            shutil.move(source_file, destination_path)

            logger.info(f"Successfully moved file from {source_file} to {destination_path}")

            return destination_path

        except Exception as e:
            logger.error(f"Error auto-moving file: {e}", exc_info=True)
            raise

    def _normalize_path_for_platform(self, path: str) -> str:
        """
        Normalize file paths for Windows/Docker compatibility

        When running as Windows .exe with Docker Lidarr:
        - Docker paths like /music/Garth Brooks need to map to Windows paths like M:\\music\\Garth Brooks
        - Forward slashes need to be converted to backslashes on Windows
        - Mixed separators need to be fixed
        """
        import platform

        original_path = path
        logger.debug(f"Normalizing path: {repr(original_path)}")

        # First, fix any mixed separators by converting everything to the platform default
        if platform.system() == 'Windows':
            # On Windows, convert ALL forward slashes to backslashes
            normalized = path.replace('/', '\\')

            # Handle Docker volume mounts (common pattern: /volume1/music -> M:\\music)
            # Users can configure path mappings in settings
            path_mappings = self.spotiflac_config.get('docker_path_mappings', {})

            if path_mappings:
                logger.debug(f"Checking {len(path_mappings)} Docker path mappings")

            for docker_path, windows_path in path_mappings.items():
                # Ensure docker_path also uses backslashes for comparison
                docker_path_normalized = docker_path.replace('/', '\\')

                if normalized.startswith(docker_path_normalized):
                    old_normalized = normalized
                    normalized = normalized.replace(docker_path_normalized, windows_path, 1)
                    logger.info(f"Applied Docker path mapping: {repr(docker_path)} -> {repr(windows_path)}")
                    logger.debug(f"Path changed from {repr(old_normalized)} to {repr(normalized)}")
                    break
            else:
                # No mapping found - log warning if path looks like a Docker path
                if normalized.startswith('\\') and ':' not in normalized:
                    logger.warning(f"Path {repr(normalized)} looks like a Linux Docker path but no mapping configured. "
                                 f"Add Docker path mappings in SpotiFLAC settings: docker_path_mappings")

            # Remove any duplicate backslashes
            normalized = normalized.replace('\\\\', '\\')

            logger.debug(f"Final normalized path: {repr(normalized)}")
            return normalized
        else:
            # On Linux/Mac, ensure forward slashes
            normalized = path.replace('\\', '/')
            # Remove any duplicate forward slashes (but not from //)
            normalized = normalized.replace('//', '/')
            logger.debug(f"Final normalized path (Linux/Mac): {repr(normalized)}")
            return normalized

    def validate_lidarr_path(self, lidarr_path: str) -> Dict:
        """Validate Lidarr path is accessible and writable"""
        try:
            import stat

            # Check if path exists
            if not os.path.exists(lidarr_path):
                # Try to create it
                os.makedirs(lidarr_path, exist_ok=True)
                logger.info(f"Created Lidarr path: {lidarr_path}")

            # Check if path is a directory
            if not os.path.isdir(lidarr_path):
                raise ValueError(f"Path is not a directory: {lidarr_path}")

            # Check write permissions
            if not os.access(lidarr_path, os.W_OK):
                raise PermissionError(f"No write permission for path: {lidarr_path}")

            # Check disk space (at least 100 MB free)
            try:
                statvfs = os.statvfs(lidarr_path)
                free_space = statvfs.f_frsize * statvfs.f_bavail
                min_space = 100 * 1024 * 1024  # 100 MB

                if free_space < min_space:
                    raise IOError(f"Insufficient disk space: {free_space / (1024*1024):.1f} MB free, 100 MB required")

                logger.info(f"Validated Lidarr path: {lidarr_path} ({free_space / (1024*1024):.1f} MB free)")
            except AttributeError:
                # statvfs not available on Windows
                logger.warning("Cannot check disk space on this platform")

            return {'valid': True, 'path': lidarr_path}

        except Exception as e:
            logger.error(f"Error validating Lidarr path: {e}")
            return {'valid': False, 'error': str(e)}

    def get_download_progress(self, job_id: str) -> Dict:
        """Get download progress for a job"""
        return self._active_jobs.get(job_id, {
            'status': 'unknown',
            'error': 'Job not found'
        })

    def get_lidarr_artist_path(self, artist_name: str, url_type: str = 'track') -> Dict:
        """
        Get the Lidarr folder path for an artist

        Args:
            artist_name: Artist name
            url_type: 'track' or 'album'

        Returns:
            Dict with path, exists, naming_convention keys
        """
        # First, try to get the actual path from Lidarr API
        # This handles accented characters correctly (e.g., "Céline Dion" vs "Celine Dion")
        try:
            from radio_monitor.lidarr import lookup_artist_by_name

            result = lookup_artist_by_name(artist_name, self.settings)

            if result['found'] and result['artist']:
                artist_data = result['artist']

                # Lidarr returns the actual folder path in the 'path' field
                # This path has the correct accents and matches what's on disk
                lidarr_path = artist_data.get('path')

                if lidarr_path:
                    # Normalize the path for platform compatibility
                    normalized_path = self._normalize_path_for_platform(lidarr_path)

                    logger.info(f"Using actual Lidarr path for '{artist_name}': {repr(normalized_path)}")

                    # Check if exists
                    path_exists = os.path.exists(normalized_path)

                    # Get naming convention from Lidarr
                    naming_convention = None
                    try:
                        if self.use_lidarr_naming:
                            naming_convention = get_lidarr_naming_convention(self.settings, url_type)
                    except Exception as e:
                        logger.warning(f"Failed to fetch Lidarr naming: {e}")

                    return {
                        'path': normalized_path,
                        'exists': path_exists,
                        'naming_convention': naming_convention
                    }

        except Exception as e:
            logger.warning(f"Failed to lookup artist path from Lidarr API: {e}")

        # Fallback: Construct path from root folder and artist name
        # This is the old behavior if Lidarr API lookup fails
        logger.info(f"Fallback: Constructing path for '{artist_name}' from root folder")

        # Get root folder from settings
        root_folder = self.settings.get('lidarr', {}).get('root_folder_path', '/data/music')

        # Normalize root folder path first
        normalized_root = self._normalize_path_for_platform(root_folder)

        # Clean up artist name (remove extra spaces)
        artist_name_clean = ' '.join(artist_name.split())

        # Construct artist path
        artist_path = os.path.join(normalized_root, artist_name_clean)

        # Normalize the entire path again to ensure consistency
        artist_path = self._normalize_path_for_platform(artist_path)

        # Check if exists
        path_exists = os.path.exists(artist_path)

        # Get naming convention from Lidarr
        naming_convention = None
        try:
            if self.use_lidarr_naming:
                naming_convention = get_lidarr_naming_convention(self.settings, url_type)
        except Exception as e:
            logger.warning(f"Failed to fetch Lidarr naming: {e}")

        return {
            'path': artist_path,
            'exists': path_exists,
            'naming_convention': naming_convention
        }
