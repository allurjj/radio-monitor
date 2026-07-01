"""
SpotiFLAC Download Database Operations

This module handles database operations for the spotiflac_downloads table,
which tracks download jobs for the SpotiFLAC integration.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def log_download(cursor, plex_match_failure_id: int, song_id: int,
                 song_title: str, artist_name: str, album_name: str = None,
                 spotify_url: str = None, download_status: str = 'starting',
                 service_used: str = None, file_path: str = None,
                 file_size_mb: float = None, error_message: str = None,
                 started_at: datetime = None, completed_at: datetime = None) -> int:
    """
    Log a SpotiFLAC download job to the database.

    Args:
        cursor: Database cursor
        plex_match_failure_id: ID of the Plex match failure (optional)
        song_id: ID of the song being downloaded
        song_title: Title of the song
        artist_name: Name of the artist
        album_name: Album name (optional)
        spotify_url: Spotify URL used for download (optional)
        download_status: Status of the download (starting, in_progress, completed, failed)
        service_used: Service used for download (tidal, youtube, etc.)
        file_path: Path to downloaded file
        file_size_mb: File size in MB
        error_message: Error message if download failed
        started_at: When the download started
        completed_at: When the download completed

    Returns:
        ID of the created download record
    """
    try:
        if started_at is None:
            started_at = datetime.now()

        cursor.execute("""
            INSERT INTO spotiflac_downloads (
                plex_match_failure_id, song_title, artist_name, album_name,
                spotify_url, download_status, service_used, file_path,
                file_size_mb, error_message, started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            plex_match_failure_id, song_title, artist_name, album_name,
            spotify_url, download_status, service_used, file_path,
            file_size_mb, error_message,
            started_at.isoformat() if started_at else None,
            completed_at.isoformat() if completed_at else None
        ))

        download_id = cursor.lastrowid
        logger.info(f"Logged SpotiFLAC download {download_id}: {download_status}")
        return download_id

    except Exception as e:
        logger.error(f"Failed to log SpotiFLAC download: {e}")
        raise


def update_download_status(cursor, download_id: int, download_status: str,
                          service_used: str = None, file_path: str = None,
                          file_size_mb: float = None, error_message: str = None,
                          completed_at: datetime = None) -> bool:
    """
    Update the status of an existing SpotiFLAC download record.

    Args:
        cursor: Database cursor
        download_id: ID of the download record to update
        download_status: New status (in_progress, completed, failed)
        service_used: Service used for download
        file_path: Path to downloaded file
        file_size_mb: File size in MB
        error_message: Error message if download failed
        completed_at: When the download completed

    Returns:
        True if update was successful
    """
    try:
        updates = ["download_status = ?"]
        params = [download_status]

        if service_used is not None:
            updates.append("service_used = ?")
            params.append(service_used)

        if file_path is not None:
            updates.append("file_path = ?")
            params.append(file_path)

        if file_size_mb is not None:
            updates.append("file_size_mb = ?")
            params.append(file_size_mb)

        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)

        if completed_at is not None:
            updates.append("completed_at = ?")
            params.append(completed_at.isoformat())

        params.append(download_id)

        cursor.execute(f"""
            UPDATE spotiflac_downloads
            SET {', '.join(updates)}
            WHERE id = ?
        """, params)

        logger.info(f"Updated SpotiFLAC download {download_id}: {download_status}")
        return True

    except Exception as e:
        logger.error(f"Failed to update SpotiFLAC download: {e}")
        return False


def get_download_by_id(cursor, download_id: int) -> Optional[Dict]:
    """
    Get a SpotiFLAC download record by ID.

    Args:
        cursor: Database cursor
        download_id: ID of the download record

    Returns:
        Dictionary with download data or None
    """
    try:
        cursor.execute("""
            SELECT * FROM spotiflac_downloads WHERE id = ?
        """, (download_id,))

        row = cursor.fetchone()

        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))

        return None

    except Exception as e:
        logger.error(f"Failed to get SpotiFLAC download: {e}")
        return None


def get_downloads_by_song(cursor, song_id: int, limit: int = 50) -> List[Dict]:
    """
    Get all SpotiFLAC downloads for a specific song.

    Args:
        cursor: Database cursor
        song_id: ID of the song
        limit: Maximum number of records to return

    Returns:
        List of download dictionaries
    """
    try:
        cursor.execute("""
            SELECT * FROM spotiflac_downloads
            WHERE plex_match_failure_id IN (
                SELECT id FROM plex_match_failures WHERE song_id = ?
            )
            ORDER BY started_at DESC
            LIMIT ?
        """, (song_id, limit))

        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        return [dict(zip(columns, row)) for row in rows]

    except Exception as e:
        logger.error(f"Failed to get SpotiFLAC downloads for song: {e}")
        return []


def get_recent_downloads(cursor, limit: int = 50, status: str = None) -> List[Dict]:
    """
    Get recent SpotiFLAC downloads, optionally filtered by status.

    Args:
        cursor: Database cursor
        limit: Maximum number of records to return
        status: Filter by status (optional)

    Returns:
        List of download dictionaries
    """
    try:
        if status:
            cursor.execute("""
                SELECT * FROM spotiflac_downloads
                WHERE download_status = ?
                ORDER BY started_at DESC
                LIMIT ?
            """, (status, limit))
        else:
            cursor.execute("""
                SELECT * FROM spotiflac_downloads
                ORDER BY started_at DESC
                LIMIT ?
            """, (limit,))

        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        return [dict(zip(columns, row)) for row in rows]

    except Exception as e:
        logger.error(f"Failed to get recent SpotiFLAC downloads: {e}")
        return []


def get_download_count(cursor, status: str = None) -> int:
    """
    Get the total count of SpotiFLAC downloads, optionally filtered by status.

    Args:
        cursor: Database cursor
        status: Filter by status (optional)

    Returns:
        Count of downloads
    """
    try:
        if status:
            cursor.execute("""
                SELECT COUNT(*) FROM spotiflac_downloads
                WHERE download_status = ?
            """, (status,))
        else:
            cursor.execute("SELECT COUNT(*) FROM spotiflac_downloads")

        return cursor.fetchone()[0]

    except Exception as e:
        logger.error(f"Failed to get SpotiFLAC download count: {e}")
        return 0


def delete_download(cursor, download_id: int) -> bool:
    """
    Delete a SpotiFLAC download record.

    Args:
        cursor: Database cursor
        download_id: ID of the download record to delete

    Returns:
        True if deletion was successful
    """
    try:
        cursor.execute("DELETE FROM spotiflac_downloads WHERE id = ?", (download_id,))
        logger.info(f"Deleted SpotiFLAC download {download_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to delete SpotiFLAC download: {e}")
        return False


def cleanup_old_downloads(cursor, days: int = 30) -> int:
    """
    Clean up old SpotiFLAC download records.

    Args:
        cursor: Database cursor
        days: Delete records older than this many days

    Returns:
        Number of records deleted
    """
    try:
        cursor.execute("""
            DELETE FROM spotiflac_downloads
            WHERE started_at < datetime('now', '-' || ? || ' days')
        """, (days,))

        deleted_count = cursor.rowcount
        logger.info(f"Cleaned up {deleted_count} old SpotiFLAC downloads")
        return deleted_count

    except Exception as e:
        logger.error(f"Failed to cleanup old SpotiFLAC downloads: {e}")
        return 0
