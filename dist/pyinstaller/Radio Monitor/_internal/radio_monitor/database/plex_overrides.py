"""
Plex manual override management functions
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


def add_plex_override(cursor, song_id: int, plex_track_key: str,
                      plex_track_title: str, plex_artist_name: str,
                      plex_album_title: Optional[str] = None,
                      plex_year: Optional[int] = None,
                      plex_duration_ms: Optional[int] = None,
                      notes: Optional[str] = None) -> Optional[int]:
    """Add a manual Plex mapping override

    Args:
        cursor: SQLite cursor
        song_id: Radio Monitor song ID
        plex_track_key: Plex ratingKey (permanent identifier)
        plex_track_title: Track title from Plex
        plex_artist_name: Artist name from Plex
        plex_album_title: Album title from Plex (optional)
        plex_year: Album year from Plex (optional)
        plex_duration_ms: Track duration in milliseconds (optional)
        notes: User notes (optional)

    Returns:
        Override ID if successful, None if failed
    """
    try:
        now = datetime.now()

        cursor.execute("""
            INSERT INTO plex_manual_overrides
            (song_id, plex_track_key, plex_track_title, plex_artist_name,
             plex_album_title, plex_year, plex_duration_ms, created_at, updated_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (song_id, plex_track_key, plex_track_title, plex_artist_name,
              plex_album_title, plex_year, plex_duration_ms, now, now, notes))

        override_id = cursor.lastrowid
        logger.info(f"Added Plex override ID {override_id}: song {song_id} → Plex {plex_track_key}")

        return override_id

    except Exception as e:
        logger.error(f"Failed to add Plex override: {e}")
        return None


def get_plex_override(cursor, song_id: int, active_only: bool = True) -> Optional[Dict[str, Any]]:
    """Get Plex override for a specific song

    Args:
        cursor: SQLite cursor
        song_id: Radio Monitor song ID
        active_only: Only return active overrides

    Returns:
        Override dict if found, None otherwise
    """
    query = """
        SELECT id, song_id, plex_track_key, plex_track_title, plex_artist_name,
               plex_album_title, plex_year, plex_duration_ms, created_at, updated_at,
               is_active, notes
        FROM plex_manual_overrides
        WHERE song_id = ?
    """

    if active_only:
        query += " AND is_active = 1"

    cursor.execute(query, (song_id,))
    row = cursor.fetchone()

    if not row:
        return None

    return {
        'id': row[0],
        'song_id': row[1],
        'plex_track_key': row[2],
        'plex_track_title': row[3],
        'plex_artist_name': row[4],
        'plex_album_title': row[5],
        'plex_year': row[6],
        'plex_duration_ms': row[7],
        'created_at': row[8],
        'updated_at': row[9],
        'is_active': bool(row[10]),
        'notes': row[11]
    }


def get_all_overrides(cursor, active_only: bool = True,
                      limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Get all Plex overrides with pagination

    Args:
        cursor: SQLite cursor
        active_only: Only return active overrides
        limit: Maximum number of overrides to return
        offset: Number of overrides to skip

    Returns:
        List of override dicts with song details
    """
    query = """
        SELECT
            o.id, o.song_id, o.plex_track_key, o.plex_track_title,
            o.plex_artist_name, o.plex_album_title, o.plex_year, o.plex_duration_ms,
            o.created_at, o.updated_at, o.is_active, o.notes,
            s.song_title, s.artist_name
        FROM plex_manual_overrides o
        JOIN songs s ON o.song_id = s.id
        WHERE 1=1
    """

    params = []

    if active_only:
        query += " AND o.is_active = 1"

    query += " ORDER BY o.updated_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)

    overrides = []
    for row in cursor.fetchall():
        (override_id, song_id, plex_key, plex_title, plex_artist, plex_album,
         plex_year, plex_duration_ms, created_at, updated_at, is_active, notes,
         song_title, artist_name) = row

        overrides.append({
            'id': override_id,
            'song_id': song_id,
            'plex_track_key': plex_key,
            'plex_track_title': plex_title,
            'plex_artist_name': plex_artist,
            'plex_album_title': plex_album,
            'plex_year': plex_year,
            'plex_duration_ms': plex_duration_ms,
            'created_at': created_at,
            'updated_at': updated_at,
            'is_active': bool(is_active),
            'notes': notes,
            'song': {
                'title': song_title,
                'artist': artist_name
            }
        })

    return overrides


def delete_override(cursor, override_id: int) -> bool:
    """Delete a Plex override

    Args:
        cursor: SQLite cursor
        override_id: Override ID to delete

    Returns:
        True if deleted, False otherwise
    """
    try:
        cursor.execute("DELETE FROM plex_manual_overrides WHERE id = ?", (override_id,))
        deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Deleted Plex override ID {override_id}")

        return deleted

    except Exception as e:
        logger.error(f"Failed to delete override: {e}")
        return False


def toggle_override_active(cursor, override_id: int, is_active: bool) -> bool:
    """Enable or disable an override without deleting it

    Args:
        cursor: SQLite cursor
        override_id: Override ID to update
        is_active: True to enable, False to disable

    Returns:
        True if successful, False otherwise
    """
    try:
        cursor.execute("""
            UPDATE plex_manual_overrides
            SET is_active = ?, updated_at = ?
            WHERE id = ?
        """, (1 if is_active else 0, datetime.now(), override_id))

        return cursor.rowcount > 0

    except Exception as e:
        logger.error(f"Failed to toggle override: {e}")
        return False


def update_override(cursor, override_id: int, plex_track_key: str = None,
                    plex_track_title: str = None, plex_artist_name: str = None,
                    plex_album_title: str = None, plex_year: int = None,
                    plex_duration_ms: int = None, notes: str = None) -> bool:
    """Update an existing Plex override

    Args:
        cursor: SQLite cursor
        override_id: Override ID to update
        plex_track_key: New Plex ratingKey (optional)
        plex_track_title: New track title (optional)
        plex_artist_name: New artist name (optional)
        plex_album_title: New album title (optional)
        plex_year: New year (optional)
        plex_duration_ms: New duration in ms (optional)
        notes: New notes (optional)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Build dynamic UPDATE statement based on provided fields
        update_fields = []
        params = []

        if plex_track_key is not None:
            update_fields.append("plex_track_key = ?")
            params.append(plex_track_key)
        if plex_track_title is not None:
            update_fields.append("plex_track_title = ?")
            params.append(plex_track_title)
        if plex_artist_name is not None:
            update_fields.append("plex_artist_name = ?")
            params.append(plex_artist_name)
        if plex_album_title is not None:
            update_fields.append("plex_album_title = ?")
            params.append(plex_album_title)
        if plex_year is not None:
            update_fields.append("plex_year = ?")
            params.append(plex_year)
        if plex_duration_ms is not None:
            update_fields.append("plex_duration_ms = ?")
            params.append(plex_duration_ms)
        if notes is not None:
            update_fields.append("notes = ?")
            params.append(notes)

        if not update_fields:
            # No fields to update
            return False

        # Always update updated_at
        update_fields.append("updated_at = ?")
        params.append(datetime.now())

        # Add override_id to params
        params.append(override_id)

        query = f"UPDATE plex_manual_overrides SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, params)

        success = cursor.rowcount > 0
        if success:
            logger.info(f"Updated Plex override ID {override_id}")

        return success

    except Exception as e:
        logger.error(f"Failed to update override: {e}")
        return False
