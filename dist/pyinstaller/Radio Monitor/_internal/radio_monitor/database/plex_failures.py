"""
Plex match failure tracking module for Radio Monitor 1.0

This module handles all operations related to tracking Plex matching failures:
- Logging failed Plex matches with reasons
- Retrieving failure history
- Generating failure statistics
- Marking failures as resolved

Failure Types:
- no_match: Song not found in Plex library
- multiple_matches: Multiple possible matches found (ambiguous)
- plex_error: Plex API/connection error
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def log_plex_failure(cursor, song_id: int, playlist_id: Optional[int],
                     failure_reason: str, search_attempts: int = 1,
                     search_terms: Optional[Dict[str, str]] = None) -> int:
    """Log a Plex matching failure

    Args:
        cursor: SQLite cursor object
        song_id: Song ID that failed to match
        playlist_id: Playlist ID (if applicable)
        failure_reason: Reason for failure (no_match, multiple_matches, plex_error)
        search_attempts: Number of search attempts made
        search_terms: Dictionary of search terms used

    Returns:
        int: ID of the inserted failure record
    """
    search_terms_json = json.dumps(search_terms) if search_terms else None

    cursor.execute("""
        INSERT INTO plex_match_failures
        (song_id, playlist_id, failure_reason, search_attempts, search_terms_used)
        VALUES (?, ?, ?, ?, ?)
    """, (song_id, playlist_id, failure_reason, search_attempts, search_terms_json))

    failure_id = cursor.lastrowid
    logger.debug(f"Logged Plex failure ID {failure_id} for song {song_id}: {failure_reason}")
    return failure_id


def get_failures(cursor, limit: int = 100, offset: int = 0,
                 resolved: Optional[bool] = None,
                 failure_reason: Optional[str] = None,
                 sort: str = 'failure_date',
                 direction: str = 'desc') -> List[Dict[str, Any]]:
    """Get Plex match failures with pagination and filtering

    Args:
        cursor: SQLite cursor object
        limit: Maximum number of failures to return
        offset: Number of failures to skip
        resolved: Filter by resolved status (None = all)
        failure_reason: Filter by failure reason (None = all)
        sort: Sort column (failure_date, song_title, artist_name, failure_reason, search_attempts)
        direction: Sort direction (asc or desc)

    Returns:
        List of failure records with song details
    """
    query = """
        SELECT
            f.id, f.song_id, f.playlist_id, f.failure_date,
            f.failure_reason, f.search_attempts, f.search_terms_used,
            f.resolved, f.resolved_at,
            s.id, s.artist_name, s.song_title,
            p.id as playlist_id_val, p.name as playlist_name
        FROM plex_match_failures f
        LEFT JOIN songs s ON f.song_id = s.id
        LEFT JOIN playlists p ON f.playlist_id = p.id
        WHERE 1=1
    """
    params = []

    if resolved is not None:
        query += " AND f.resolved = ?"
        params.append(1 if resolved else 0)

    if failure_reason:
        query += " AND f.failure_reason = ?"
        params.append(failure_reason)

    # Build ORDER BY clause dynamically based on sort and direction
    # Map sort parameter to database column
    sort_column_mapping = {
        'failure_date': 'f.failure_date',
        'song_title': 's.song_title',
        'artist_name': 's.artist_name',
        'failure_reason': 'f.failure_reason',
        'search_attempts': 'f.search_attempts'
    }

    # Get column name (default to failure_date)
    sort_column = sort_column_mapping.get(sort, 'f.failure_date')

    # Build ORDER BY clause with direction
    # Use COLLATE NOCASE for case-insensitive text sorting
    if sort in ['song_title', 'artist_name', 'failure_reason']:
        order_by = f"{sort_column} COLLATE NOCASE {direction.upper()}"
    else:
        order_by = f"{sort_column} {direction.upper()}"

    query += f" ORDER BY {order_by} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)

    failures = []
    for row in cursor.fetchall():
        (failure_id, song_id, playlist_id, failure_date, failure_reason,
         search_attempts, search_terms_json, resolved, resolved_at,
         sid, artist_name, song_title, pid_val, playlist_name) = row

        search_terms = json.loads(search_terms_json) if search_terms_json else None

        failures.append({
            'id': failure_id,
            'song_id': song_id,
            'playlist_id': playlist_id,
            'failure_date': failure_date,
            'failure_reason': failure_reason,
            'search_attempts': search_attempts,
            'search_terms': search_terms,
            'resolved': bool(resolved),
            'resolved_at': resolved_at,
            'song': {
                'id': sid,
                'artist_name': artist_name,
                'song_title': song_title
            } if sid else None,
            'playlist': {
                'id': pid_val,
                'name': playlist_name
            } if pid_val else None
        })

    return failures


def get_failure_count(cursor, resolved: Optional[bool] = None,
                      failure_reason: Optional[str] = None) -> int:
    """Get total count of Plex match failures

    Args:
        cursor: SQLite cursor object
        resolved: Filter by resolved status (None = all)
        failure_reason: Filter by failure reason (None = all)

    Returns:
        int: Total count of matching failures
    """
    query = "SELECT COUNT(*) FROM plex_match_failures WHERE 1=1"
    params = []

    if resolved is not None:
        query += " AND resolved = ?"
        params.append(1 if resolved else 0)

    if failure_reason:
        query += " AND failure_reason = ?"
        params.append(failure_reason)

    cursor.execute(query, params)
    return cursor.fetchone()[0]


def get_failure_by_id(cursor, failure_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific failure record by ID

    Args:
        cursor: SQLite cursor object
        failure_id: Failure record ID

    Returns:
        Dictionary with failure details or None
    """
    cursor.execute("""
        SELECT
            f.id, f.song_id, f.playlist_id, f.failure_date,
            f.failure_reason, f.search_attempts, f.search_terms_used,
            f.resolved, f.resolved_at,
            s.id, s.artist_name, s.song_title,
            p.id as playlist_id_val, p.name as playlist_name
        FROM plex_match_failures f
        LEFT JOIN songs s ON f.song_id = s.id
        LEFT JOIN playlists p ON f.playlist_id = p.id
        WHERE f.id = ?
    """, (failure_id,))

    row = cursor.fetchone()
    if not row:
        return None

    (failure_id, song_id, playlist_id, failure_date, failure_reason,
     search_attempts, search_terms_json, resolved, resolved_at,
     sid, artist_name, song_title, pid_val, playlist_name) = row

    search_terms = json.loads(search_terms_json) if search_terms_json else None

    return {
        'id': failure_id,
        'song_id': song_id,
        'playlist_id': playlist_id,
        'failure_date': failure_date,
        'failure_reason': failure_reason,
        'search_attempts': search_attempts,
        'search_terms': search_terms,
        'resolved': bool(resolved),
        'resolved_at': resolved_at,
        'song': {
            'id': sid,
            'artist_name': artist_name,
            'song_title': song_title
        } if sid else None,
        'playlist': {
            'id': pid_val,
            'name': playlist_name
        } if pid_val else None
    }


def get_failures_by_song(cursor, song_id: int) -> List[Dict[str, Any]]:
    """Get all failures for a specific song

    Args:
        cursor: SQLite cursor object
        song_id: Song ID

    Returns:
        List of failure records
    """
    cursor.execute("""
        SELECT
            id, playlist_id, failure_date, failure_reason,
            search_attempts, search_terms_used, resolved, resolved_at
        FROM plex_match_failures
        WHERE song_id = ?
        ORDER BY failure_date DESC
    """, (song_id,))

    failures = []
    for row in cursor.fetchall():
        (failure_id, playlist_id, failure_date, failure_reason,
         search_attempts, search_terms_json, resolved, resolved_at) = row

        search_terms = json.loads(search_terms_json) if search_terms_json else None

        failures.append({
            'id': failure_id,
            'song_id': song_id,
            'playlist_id': playlist_id,
            'failure_date': failure_date,
            'failure_reason': failure_reason,
            'search_attempts': search_attempts,
            'search_terms': search_terms,
            'resolved': bool(resolved),
            'resolved_at': resolved_at
        })

    return failures


def mark_resolved(cursor, failure_id: int) -> bool:
    """Mark a failure as resolved

    Args:
        cursor: SQLite cursor object
        failure_id: Failure record ID

    Returns:
        bool: True if marked as resolved, False if not found
    """
    # Use local time for resolved_at timestamp
    now = datetime.now()
    cursor.execute("""
        UPDATE plex_match_failures
        SET resolved = 1, resolved_at = ?
        WHERE id = ?
    """, (now, failure_id,))

    return cursor.rowcount > 0


def get_failure_stats(cursor, days: int = 30) -> Dict[str, Any]:
    """Get failure statistics for the specified time period

    Args:
        cursor: SQLite cursor object
        days: Number of days to look back (default 30)

    Returns:
        Dictionary with failure statistics
    """
    since_date = datetime.now() - timedelta(days=days)

    # Total failures
    cursor.execute("""
        SELECT COUNT(*) FROM plex_match_failures
        WHERE failure_date >= ?
    """, (since_date,))
    total_failures = cursor.fetchone()[0]

    # Unresolved failures
    cursor.execute("""
        SELECT COUNT(*) FROM plex_match_failures
        WHERE failure_date >= ? AND resolved = 0
    """, (since_date,))
    unresolved_failures = cursor.fetchone()[0]

    # Resolved failures
    cursor.execute("""
        SELECT COUNT(*) FROM plex_match_failures
        WHERE failure_date >= ? AND resolved = 1
    """, (since_date,))
    resolved_failures = cursor.fetchone()[0]

    # Failures by reason
    cursor.execute("""
        SELECT failure_reason, COUNT(*) as count
        FROM plex_match_failures
        WHERE failure_date >= ?
        GROUP BY failure_reason
        ORDER BY count DESC
    """, (since_date,))
    by_reason = {row[0]: row[1] for row in cursor.fetchall()}

    # Top songs with most failures (LEFT JOIN to handle orphaned records)
    cursor.execute("""
        SELECT
            s.song_title, s.artist_name, COUNT(f.id) as failure_count
        FROM plex_match_failures f
        LEFT JOIN songs s ON f.song_id = s.id
        WHERE f.failure_date >= ?
        GROUP BY s.id
        ORDER BY failure_count DESC
        LIMIT 10
    """, (since_date,))
    top_songs = [
        {
            'song_title': row[0] if row[0] else 'Unknown (Deleted)',
            'artist_name': row[1] if row[1] else 'Unknown (Deleted)',
            'failure_count': row[2]
        }
        for row in cursor.fetchall()
    ]

    # Recent failures (last 10) - LEFT JOIN to handle orphaned records
    cursor.execute("""
        SELECT
            f.id, s.song_title, s.artist_name, f.failure_reason, f.failure_date
        FROM plex_match_failures f
        LEFT JOIN songs s ON f.song_id = s.id
        WHERE f.failure_date >= ?
        ORDER BY f.failure_date DESC
        LIMIT 10
    """, (since_date,))
    recent_failures = [
        {
            'id': row[0],
            'song_title': row[1] if row[1] else 'Unknown (Deleted)',
            'artist_name': row[2] if row[2] else 'Unknown (Deleted)',
            'failure_reason': row[3],
            'failure_date': row[4]
        }
        for row in cursor.fetchall()
    ]

    return {
        'period_days': days,
        'total_failures': total_failures,
        'unresolved_failures': unresolved_failures,
        'resolved_failures': resolved_failures,
        'by_reason': by_reason,
        'top_songs': top_songs,
        'recent_failures': recent_failures
    }


def delete_old_failures(cursor, days: int = 7) -> int:
    """Delete ALL failures older than specified days (regardless of resolved status)

    This is used for auto-purge to keep the Plex failures table focused on recent issues.
    Failed songs will be re-logged if they fail again in future playlist runs.

    Args:
        cursor: SQLite cursor object
        days: Days to retain (default 7)

    Returns:
        int: Number of failures deleted
    """
    cutoff_date = datetime.now() - timedelta(days=days)

    cursor.execute("""
        DELETE FROM plex_match_failures
        WHERE failure_date < ?
    """, (cutoff_date,))

    deleted = cursor.rowcount
    logger.info(f"Deleted {deleted} old Plex failure records (older than {days} days)")
    return deleted


def export_failures_to_csv(cursor, output_path: str,
                           resolved: Optional[bool] = None,
                           days: int = 30) -> int:
    """Export failures to CSV file

    Args:
        cursor: SQLite cursor object
        output_path: Path to output CSV file
        resolved: Filter by resolved status (None = all)
        days: Number of days to include (default 30)

    Returns:
        int: Number of failures exported
    """
    import csv

    since_date = datetime.now() - timedelta(days=days)

    query = """
        SELECT
            f.id, s.artist_name, s.song_title, f.failure_date,
            f.failure_reason, f.search_attempts, f.search_terms_used,
            f.resolved, f.resolved_at, p.name as playlist_name
        FROM plex_match_failures f
        LEFT JOIN songs s ON f.song_id = s.id
        LEFT JOIN playlists p ON f.playlist_id = p.id
        WHERE f.failure_date >= ?
    """
    params = [since_date]

    if resolved is not None:
        query += " AND f.resolved = ?"
        params.append(1 if resolved else 0)

    query += " ORDER BY f.failure_date DESC"

    cursor.execute(query, params)

    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            'Failure ID', 'Artist', 'Song Title', 'Failure Date',
            'Failure Reason', 'Search Attempts', 'Search Terms',
            'Resolved', 'Resolved At', 'Playlist'
        ])

        for row in cursor.fetchall():
            (failure_id, artist_name, song_title, failure_date,
             failure_reason, search_attempts, search_terms_json,
             resolved, resolved_at, playlist_name) = row

            writer.writerow([
                failure_id,
                artist_name or '',
                song_title or '',
                failure_date,
                failure_reason,
                search_attempts,
                search_terms_json or '',
                'Yes' if resolved else 'No',
                resolved_at or '',
                playlist_name or ''
            ])

    logger.info(f"Exported {cursor.rowcount} failures to {output_path}")
    return cursor.rowcount


def cleanup_old_failures(db, days: int = 7) -> int:
    """Clean up old Plex failure records (non-critical maintenance task)

    This wrapper function provides error handling for the auto-purge process.
    It's designed to be called from the scheduler or backup jobs.

    Args:
        db: RadioDatabase instance
        days: Days to retain (default 7)

    Returns:
        int: Number of failures deleted, or -1 on error
    """
    try:
        cursor = db.get_cursor()
        try:
            deleted = delete_old_failures(cursor, days=days)
            db.conn.commit()
            if deleted > 0:
                logger.info(f"Auto-purge: Cleaned up {deleted} old Plex failure records (older than {days} days)")
            return deleted
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Failed to cleanup Plex failures: {e}", exc_info=True)
        # Non-critical - don't crash the backup/scheduler
        return -1
