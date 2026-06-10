"""
SpotiFLAC Integration for Radio Monitor

This module provides SpotiFLAC functionality for downloading music
from various streaming services (Tidal, Qobuz, Amazon, Deezer, YouTube, Spotify).
"""

# Re-export main classes and functions from the SpotiFLAC module
from .spotiflac import (
    Config,
    Track,
    extract_cover_art,
    format_artists,
    get_metadata,
    fetch_tracks,
)

from .progress import (
    DownloadManager,
    DownloadStatus,
    RichProgressCallback,
)

from .getMetadata import (
    get_filtered_data,
    parse_uri,
    SpotifyInvalidUrlException,
)

# Downloader classes
from .tidalDL import TidalDownloader
from .qobuzDL import QobuzDownloader
from .amazonDL import AmazonDownloader
from .deezerDL import DeezerDownloader
from .youtubeDL import YouTubeDownloader
from .spotidownloaderDL import SpotiDownloader

__all__ = [
    # Main classes
    "Config",
    "Track",
    "DownloadManager",
    "DownloadStatus",
    "RichProgressCallback",

    # Metadata functions
    "get_metadata",
    "get_filtered_data",
    "fetch_tracks",
    "parse_uri",
    "extract_cover_art",
    "format_artists",

    # Exceptions
    "SpotifyInvalidUrlException",

    # Downloaders
    "TidalDownloader",
    "QobuzDownloader",
    "AmazonDownloader",
    "DeezerDownloader",
    "YouTubeDownloader",
    "SpotiDownloader",
]
