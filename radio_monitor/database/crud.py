"""
Database CRUD operations for Radio Monitor 1.0

This module contains all INSERT/UPDATE/DELETE operations that modify the database.

CRUD Categories:
- Station CRUD: add_station, update_station, delete_station, disable_station, enable_station
- Artist CRUD: add_artist, update_artist_last_seen, mark_artists_imported_to_lidarr
- Song CRUD: add_song, update_song_play_count, add_or_update_song_play
- Playlist CRUD: add_playlist, update_playlist, delete_playlist, set_playlist_enabled
- Health tracking: record_scrape_success, record_scrape_failure, increment_station_failure_count
"""

import logging
import sqlite3
import threading
from datetime import datetime, timedelta

from radio_monitor.normalization import normalize_artist_name, normalize_song_title

logger = logging.getLogger(__name__)

# Thread-safe lock for MBID update operations to prevent race conditions
_mbid_update_lock = threading.Lock()


# ==================== STATION CRUD ====================

def add_station(cursor, conn, station_id, name, url, genre, market, has_mbid=False, scraper_type='iheart', wait_time=10):
    """Add a new station to the database

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        station_id: Unique station ID (e.g., 'us99', 'wls')
        name: Station name (e.g., 'US99 99.5fm Chicago')
        url: Station website/stream URL
        genre: Music genre (e.g., 'Pop', 'Rock')
        market: Market/location (e.g., 'Chicago')
        has_mbid: Whether station provides MBIDs (default: False)
        scraper_type: Type of scraper (ONLY 'iheart' supported as of v1.1.0, default: 'iheart')
                     Note: 'wtmx' type is NO LONGER SUPPORTED (Selenium removed)
        wait_time: Page load wait time in seconds (default: 10)

    Returns:
        True if added successfully, False if already exists

    Raises:
        ValueError: If scraper_type is not 'iheart'
        Exception: If database error occurs
    """
    try:
        # Validate scraper_type (v1.1.0: only iheart supported)
        if scraper_type != 'iheart':
            raise ValueError(
                f"Unsupported scraper_type: '{scraper_type}'. "
                f"Only 'iheart' is supported. "
                f"The 'wtmx' type is no longer supported (Selenium dependency removed in v1.1.0)."
            )

        # Check if station already exists
        cursor.execute("SELECT id FROM stations WHERE id = ?", (station_id,))
        if cursor.fetchone():
            logger.warning(f"Station {station_id} already exists")
            return False

        # Insert new station
        cursor.execute("""
            INSERT INTO stations (id, name, url, genre, market, has_mbid, scraper_type, wait_time, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (station_id, name, url, genre, market, 1 if has_mbid else 0, scraper_type, wait_time))

        conn.commit()
        logger.info(f"Added station: {station_id} - {name}")
        return True

    except ValueError:
        # Re-raise validation errors as-is
        raise
    except Exception as e:
        logger.error(f"Error adding station {station_id}: {e}")
        conn.rollback()
        raise


def update_station(cursor, conn, station_id, **kwargs):
    """Update station fields

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        station_id: Station ID
        **kwargs: Fields to update (name, url, genre, market, has_mbid, scraper_type, enabled)

    Returns:
        True if updated, False if not found
    """
    try:
        if not kwargs:
            return False

        # Build update query dynamically
        updates = []
        params = []

        for key, value in kwargs.items():
            if key in ['name', 'url', 'genre', 'market', 'scraper_type']:
                updates.append(f"{key} = ?")
                params.append(value)
            elif key in ['has_mbid', 'enabled']:
                updates.append(f"{key} = ?")
                params.append(1 if value else 0)

        if not updates:
            return False

        params.append(station_id)

        cursor.execute(f"""
            UPDATE stations
            SET {', '.join(updates)}
            WHERE id = ?
        """, params)

        conn.commit()
        return True

    except Exception as e:
        logger.error(f"Error updating station {station_id}: {e}")
        conn.rollback()
        raise


def delete_station(cursor, conn, station_id):
    """Delete a station from the database

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        station_id: Station ID to delete

    Returns:
        True if deleted successfully, False if station not found

    Raises:
        Exception: If database error occurs
    """
    try:
        # Check if station exists
        cursor.execute("SELECT id FROM stations WHERE id = ?", (station_id,))
        if not cursor.fetchone():
            logger.warning(f"Station {station_id} not found")
            return False

        # Delete station (cascade will handle song_plays_daily)
        cursor.execute("DELETE FROM stations WHERE id = ?", (station_id,))

        conn.commit()
        logger.info(f"Deleted station: {station_id}")
        return True

    except Exception as e:
        logger.error(f"Error deleting station {station_id}: {e}")
        conn.rollback()
        raise


def disable_station(cursor, conn, station_id):
    """Disable a station (after too many failures)

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        station_id: Station ID
    """
    cursor.execute("UPDATE stations SET enabled = 0 WHERE id = ?", (station_id,))
    conn.commit()


def enable_station(cursor, conn, station_id):
    """Enable a station

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        station_id: Station ID
    """
    cursor.execute("UPDATE stations SET enabled = 1 WHERE id = ?", (station_id,))
    conn.commit()


def increment_station_failure_count(cursor, conn, station_id):
    """Increment station failure count and update timestamp

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        station_id: Station ID

    Returns:
        True if station was auto-disabled, False otherwise
    """
    # Get current failure count
    cursor.execute("""
        SELECT consecutive_failures FROM stations WHERE id = ?
    """, (station_id,))
    result = cursor.fetchone()

    if not result:
        logger.warning(f"Station {station_id} not found in database")
        return False

    current_failures = result[0]
    new_failures = current_failures + 1

    # Check if we should auto-disable (144 failures = 24 hours at 10min intervals)
    auto_disabled = new_failures >= 144

    # Update station
    cursor.execute("""
        UPDATE stations
        SET consecutive_failures = ?,
            last_failure_at = ?,
            enabled = CASE WHEN ? >= 144 THEN 0 ELSE enabled END
        WHERE id = ?
    """, (new_failures, datetime.now(), new_failures, station_id))
    conn.commit()

    if auto_disabled:
        logger.error(f"Station {station_id} disabled after {new_failures} consecutive failures")

    return auto_disabled


# ==================== ARTIST CRUD ====================

def add_artist(cursor, conn, mbid, name, first_seen_station):
    """Add or update artist

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        mbid: MusicBrainz artist ID
        name: Artist name
        first_seen_station: Station where first heard

    Returns:
        True if new artist, False if existing
    """
    # Normalize name (consistent with database schema)
    normalized_name = normalize_artist_name(name)

    # Check if artist exists by MBID
    cursor.execute("SELECT mbid, name FROM artists WHERE mbid = ?", (mbid,))
    existing_by_mbid = cursor.fetchone()

    if existing_by_mbid:
        # Artist exists with this MBID - update last_seen
        now = datetime.now()
        cursor.execute("""
            UPDATE artists
            SET last_seen_at = ?
            WHERE mbid = ?
        """, (now, mbid))
        conn.commit()
        return False

    # Check if artist exists by name (UNIQUE constraint on name)
    cursor.execute("SELECT mbid, name FROM artists WHERE name = ?", (normalized_name,))
    existing_by_name = cursor.fetchone()

    if existing_by_name:
        existing_id, existing_name = existing_by_name
        # Artist with this name already exists but different MBID
        # Keep the existing record (first one wins) to avoid UNIQUE constraint violation
        logger.warning(f"Artist '{normalized_name}' already exists with MBID {existing_id}, "
                      f"ignoring new MBID {mbid}")
        # Update last_seen for the existing artist
        now = datetime.now()
        cursor.execute("""
            UPDATE artists
            SET last_seen_at = ?
            WHERE mbid = ?
        """, (now, existing_id))
        conn.commit()
        return False
    else:
        # Insert new artist
        now = datetime.now()
        cursor.execute("""
            INSERT INTO artists (mbid, name, first_seen_station, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?)
        """, (mbid, normalized_name, first_seen_station, now, now))
        conn.commit()
        return True


def update_artist_last_seen(cursor, conn, mbid):
    """Update artist's last_seen_at timestamp

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        mbid: Artist MBID
    """
    now = datetime.now()
    cursor.execute("""
        UPDATE artists
        SET last_seen_at = ?
        WHERE mbid = ?
    """, (now, mbid))
    conn.commit()


def mark_artists_imported_to_lidarr(cursor, conn, mbids):
    """Mark multiple artists as imported to Lidarr

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        mbids: List of MusicBrainz artist IDs

    Returns:
        Number of artists marked
    """
    try:
        marked = 0
        for mbid in mbids:
            cursor.execute("""
                UPDATE artists
                SET lidarr_imported_at = ?
                WHERE mbid = ?
            """, (datetime.now(), mbid))
            if cursor.rowcount > 0:
                marked += 1

        conn.commit()
        return marked
    except Exception as e:
        logger.error(f"Error marking artists as imported: {e}")
        conn.rollback()
        raise


def mark_single_artist_imported_to_lidarr(cursor, conn, mbid):
    """Mark single artist as imported to Lidarr

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        mbid: MusicBrainz artist ID

    Returns:
        True if updated, False if not found
    """
    try:
        cursor.execute("""
            UPDATE artists
            SET lidarr_imported_at = ?
            WHERE mbid = ?
        """, (datetime.now(), mbid))

        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error marking artist {mbid} as imported: {e}")
        conn.rollback()
        raise


def delete_artist(cursor, conn, mbid):
    """Delete an artist and all related data (cascade)

    This function performs a cascading delete:
    1. Deletes song_plays_daily records for all artist's songs
    2. Deletes plex_match_failures records for all artist's songs
    3. Deletes manual_mbid_overrides for this artist
    4. Deletes all songs belonging to the artist
    5. Deletes the artist record

    Uses transaction for atomicity - all deletions succeed or all fail.

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        mbid: Artist MBID (MusicBrainz ID) to delete

    Returns:
        dict: Deletion statistics
            {
                'success': True/False,
                'artist_name': str,
                'mbid': str,
                'songs_deleted': int,
                'plays_deleted': int,
                'plex_failures_deleted': int,
                'overrides_deleted': int,
                'error': str (if success=False)
            }
    """
    try:
        # Get artist name first (for logging/response)
        cursor.execute("SELECT name FROM artists WHERE mbid = ?", (mbid,))
        artist_result = cursor.fetchone()

        if not artist_result:
            logger.warning(f"Artist not found for deletion: {mbid}")
            return {
                'success': False,
                'error': f'Artist not found: {mbid}',
                'songs_deleted': 0,
                'plays_deleted': 0,
                'plex_failures_deleted': 0,
                'overrides_deleted': 0
            }

        artist_name = artist_result[0]

        # Begin transaction for atomicity
        cursor.execute("BEGIN IMMEDIATE TRANSACTION")

        # Step 1: Delete song_plays_daily records (using subquery - NO SQL INJECTION)
        cursor.execute("""
            DELETE FROM song_plays_daily
            WHERE song_id IN (
                SELECT id FROM songs WHERE artist_mbid = ?
            )
        """, (mbid,))
        plays_deleted = cursor.rowcount

        # Step 2: Delete plex_match_failures records (using subquery - NO SQL INJECTION)
        cursor.execute("""
            DELETE FROM plex_match_failures
            WHERE song_id IN (
                SELECT id FROM songs WHERE artist_mbid = ?
            )
        """, (mbid,))
        plex_failures_deleted = cursor.rowcount

        # Step 3: Delete manual MBID overrides for this artist
        cursor.execute("""
            DELETE FROM manual_mbid_overrides
            WHERE artist_name_normalized = ?
        """, (artist_name.lower(),))
        overrides_deleted = cursor.rowcount

        # Step 4: Delete all songs belonging to this artist
        cursor.execute("DELETE FROM songs WHERE artist_mbid = ?", (mbid,))
        songs_deleted = cursor.rowcount

        # Step 5: Delete the artist record
        cursor.execute("DELETE FROM artists WHERE mbid = ?", (mbid,))

        # Commit transaction
        conn.commit()

        logger.info(f"Deleted artist '{artist_name}' (MBID: {mbid}): "
                   f"{songs_deleted} songs, {plays_deleted} plays, "
                   f"{plex_failures_deleted} Plex failures, "
                   f"{overrides_deleted} MBID overrides")

        return {
            'success': True,
            'artist_name': artist_name,
            'mbid': mbid,
            'songs_deleted': songs_deleted,
            'plays_deleted': plays_deleted,
            'plex_failures_deleted': plex_failures_deleted,
            'overrides_deleted': overrides_deleted
        }

    except Exception as e:
        # Rollback on any error
        conn.rollback()
        logger.error(f"Error deleting artist {mbid}: {e}")
        return {
            'success': False,
            'error': str(e),
            'songs_deleted': 0,
            'plays_deleted': 0,
            'plex_failures_deleted': 0,
            'overrides_deleted': 0
        }


def reset_all_lidarr_import_status(cursor, conn):
    """Reset all artists to "Needs Import" status

    Sets all artists to:
    - needs_lidarr_import = 1
    - lidarr_imported_at = NULL

    Useful when sharing databases with friends or re-importing to Lidarr.

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object

    Returns:
        Number of artists reset
    """
    try:
        cursor.execute("""
            UPDATE artists
            SET needs_lidarr_import = 1,
                lidarr_imported_at = NULL
        """)

        count = cursor.rowcount
        conn.commit()
        logger.info(f"Reset import status for {count} artists")
        return count
    except Exception as e:
        logger.error(f"Error resetting import status: {e}")
        conn.rollback()
        raise


def update_artist_mbid_from_pending(cursor, conn, artist_name, mbid):
    """Update artist MBID (for resolving NULL or PENDING MBIDs)

    This method updates artists with NULL or PENDING- MBIDs to real MBIDs.
    For PENDING MBIDs, this requires a special approach because mbid is PRIMARY KEY
    and songs table has foreign key references.

    Thread-safe: Uses application-level lock (_mbid_update_lock) to prevent race
    conditions when multiple threads try to update MBIDs concurrently.

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        artist_name: Artist name (for lookup)
        mbid: MusicBrainz ID to set (or None to clear PENDING status)

    Returns:
        True if updated, False if not found
    """
    with _mbid_update_lock:
        logger.debug(f"Acquired MBID update lock for {artist_name}")

        try:
            if mbid:
                # For PENDING MBIDs, we need to use a transaction to avoid FK constraint issues
                # because mbid is PRIMARY KEY and songs have FK references to it

                # First, get the old PENDING MBID
                cursor.execute("""
                    SELECT mbid FROM artists WHERE name = ? AND mbid LIKE 'PENDING-%'
                """, (artist_name,))
                result = cursor.fetchone()

                if not result:
                    # Try NULL MBID case
                    cursor.execute("""
                        UPDATE artists
                        SET mbid = ?
                        WHERE name = ? AND mbid IS NULL
                    """, (mbid, artist_name))
                    conn.commit()
                    return cursor.rowcount > 0

                old_mbid = result[0]

                # Check if the target MBID already exists in the database
                # (This happens when an artist is in collaborations but also solo)
                cursor.execute("""
                    SELECT name FROM artists WHERE mbid = ?
                """, (mbid,))
                existing_artist = cursor.fetchone()

                if existing_artist:
                    # MBID already exists - just delete PENDING artist (songs already tracked under collaboration)
                    logger.info(f"MBID {mbid} already exists as '{existing_artist[0]}' - deleting PENDING {artist_name}")

                    try:
                        # Disable foreign keys BEFORE starting transaction
                        cursor.execute("PRAGMA foreign_keys = OFF")
                        cursor.execute("BEGIN IMMEDIATE TRANSACTION")

                        # Delete all PENDING songs (they're duplicates of songs under collaboration)
                        logger.debug(f"Deleting PENDING songs (already tracked under collaboration)")
                        cursor.execute("""
                            DELETE FROM songs
                            WHERE artist_mbid = ?
                        """, (old_mbid,))

                        # Delete the PENDING artist entry
                        logger.debug(f"Deleting PENDING artist {artist_name}")
                        cursor.execute("""
                            DELETE FROM artists WHERE mbid = ?
                        """, (old_mbid,))

                        # Re-enable foreign keys
                        cursor.execute("PRAGMA foreign_keys = ON")

                        conn.commit()
                        logger.debug(f"Successfully merged {artist_name} into {existing_artist[0]}")
                        return True

                    except sqlite3.IntegrityError:
                        # Race condition - artist was already merged by another thread
                        logger.info(f"PENDING artist {artist_name} was already merged by another thread")
                        conn.rollback()
                        cursor.execute("PRAGMA foreign_keys = ON")  # Ensure FKs are re-enabled
                        return True

                    except Exception as e:
                        logger.error(f"Database error merging {artist_name}: {e}")
                        conn.rollback()
                        # Make sure FKs are re-enabled even on error
                        cursor.execute("PRAGMA foreign_keys = ON")
                        raise e

                # Use transaction to safely replace PENDING MBID with real MBID
                # Complex approach: Insert with temp name, update songs, delete old, fix name
                try:
                    cursor.execute("BEGIN IMMEDIATE TRANSACTION")

                    # Get artist data from old record
                    cursor.execute("""
                        SELECT first_seen_station, first_seen_at, last_seen_at,
                               needs_lidarr_import, lidarr_imported_at
                        FROM artists WHERE mbid = ?
                    """, (old_mbid,))
                    artist_data = cursor.fetchone()

                    if artist_data:
                        logger.debug(f"Updating {artist_name}: {old_mbid} → {mbid}")

                        # Step 1: Insert new artist with temporary unique name
                        temp_name = f"{artist_name}-{mbid[:8]}"
                        logger.debug(f"Step 1: Inserting new artist with temp name: {temp_name}")

                        try:
                            cursor.execute("""
                                INSERT INTO artists
                                (mbid, name, first_seen_station, first_seen_at, last_seen_at,
                                 needs_lidarr_import, lidarr_imported_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (mbid, temp_name, *artist_data))
                        except sqlite3.IntegrityError:
                            # MBID was inserted by another thread between our check and insert
                            # Treat it as "MBID already exists" case
                            logger.info(f"MBID {mbid} was just created by another process - merging {artist_name}")
                            conn.rollback()

                            try:
                                # Use the "MBID already exists" logic
                                cursor.execute("PRAGMA foreign_keys = OFF")
                                cursor.execute("BEGIN IMMEDIATE TRANSACTION")

                                # Update all PENDING songs to use the existing MBID
                                cursor.execute("""
                                    UPDATE songs
                                    SET artist_mbid = ?
                                    WHERE artist_mbid = ?
                                """, (mbid, old_mbid))

                                # Delete the PENDING artist entry
                                cursor.execute("""
                                    DELETE FROM artists WHERE mbid = ?
                                """, (old_mbid,))

                                # Re-enable foreign keys
                                cursor.execute("PRAGMA foreign_keys = ON")

                                conn.commit()
                                logger.debug(f"Successfully merged {artist_name} into existing MBID {mbid}")
                                return True

                            except sqlite3.IntegrityError:
                                # Another race condition - MBID might have been merged already
                                # Just log and return True (artist is already in database with correct MBID)
                                logger.info(f"MBID {mbid} for {artist_name} was already merged by another thread")
                                conn.rollback()
                                cursor.execute("PRAGMA foreign_keys = ON")  # Ensure FKs are re-enabled
                                return True

                        # Step 2: Update all songs to use new MBID (now valid FK)
                        logger.debug(f"Step 2: Updating songs")
                        cursor.execute("""
                            UPDATE songs
                            SET artist_mbid = ?
                            WHERE artist_mbid = ?
                        """, (mbid, old_mbid))

                        # Step 3: Delete old artist (no longer referenced)
                        logger.debug(f"Step 3: Deleting old artist {old_mbid}")
                        cursor.execute("""
                            DELETE FROM artists WHERE mbid = ?
                        """, (old_mbid,))

                        # Step 4: Update new artist name back to original
                        logger.debug(f"Step 4: Updating artist name back to {artist_name}")
                        cursor.execute("""
                            UPDATE artists
                            SET name = ?
                            WHERE mbid = ?
                        """, (artist_name, mbid))

                    conn.commit()
                    logger.debug(f"Successfully updated {artist_name}")
                    return True

                except Exception as e:
                    logger.error(f"Database error updating {artist_name}: {e}")
                    conn.rollback()
                    raise e
            else:
                # Clear PENDING MBID (set to NULL for retry)
                cursor.execute("""
                    UPDATE artists
                    SET mbid = NULL
                    WHERE name = ? AND mbid LIKE 'PENDING-%'
                """, (artist_name,))

            conn.commit()
            return cursor.rowcount > 0

        finally:
            logger.debug(f"Releasing MBID update lock for {artist_name}")


# ==================== SONG CRUD ====================

def add_song(cursor, conn, artist_mbid, artist_name, song_title, station_id=None):
    """Add or update song

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        artist_mbid: Artist MBID (can be NULL temporarily)
        artist_name: Artist name
        song_title: Song title
        station_id: Station ID (for play tracking)

    Returns:
        Tuple: (is_new, song_id, play_count)
    """
    # Check if song exists
    cursor.execute("""
        SELECT id, play_count FROM songs
        WHERE artist_name = ? AND song_title = ?
    """, (artist_name, song_title))

    existing = cursor.fetchone()

    if existing:
        # Update existing song
        song_id, play_count = existing
        new_count = play_count + 1
        now = datetime.now()
        cursor.execute("""
            UPDATE songs
            SET last_seen_at = ?,
                play_count = ?
            WHERE id = ?
        """, (now, new_count, song_id))
        conn.commit()
        return (False, song_id, new_count)
    else:
        # Insert new song
        cursor.execute("""
            INSERT INTO songs (artist_mbid, artist_name, song_title)
            VALUES (?, ?, ?)
        """, (artist_mbid, artist_name, song_title))
        conn.commit()

        song_id = cursor.lastrowid

        # If we have a station_id, record the play in song_plays_daily
        if station_id:
            # CRITICAL: Must call datetime.now() ONCE to avoid midnight rollover bugs
            now = datetime.now()
            increment_play_count(cursor, conn,
                               now.strftime('%Y-%m-%d'),
                               now.hour,
                               song_id,
                               station_id
                               )

        return (True, song_id, 1)


def update_song_play_count(cursor, conn, song_id, increment=1):
    """Update song play count

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        song_id: Song ID
        increment: Amount to increment (default: 1)
    """
    now = datetime.now()
    cursor.execute("""
        UPDATE songs
        SET play_count = play_count + ?,
            last_seen_at = ?
        WHERE id = ?
    """, (increment, now, song_id))
    conn.commit()


def add_or_update_song_play(cursor, conn, date, hour, song_id, station_id, play_count=1):
    """Add or update a play record in song_plays_daily

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        date: Date string (YYYY-MM-DD)
        hour: Hour (0-23)
        song_id: Song ID
        station_id: Station ID
        play_count: Number of plays to record (default: 1)
    """
    cursor.execute("""
        INSERT INTO song_plays_daily (date, hour, song_id, station_id, play_count)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (date, hour, song_id, station_id)
        DO UPDATE SET play_count = play_count + ?
    """, (date, hour, song_id, station_id, play_count))

    conn.commit()


def increment_play_count(cursor, conn, date, hour, song_id, station_id):
    """Increment play count for a song on a specific date/hour/station

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        date: Date string (YYYY-MM-DD)
        hour: Hour (0-23)
        song_id: Song ID
        station_id: Station ID
    """
    cursor.execute("""
        INSERT INTO song_plays_daily (date, hour, song_id, station_id, play_count)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT (date, hour, song_id, station_id)
        DO UPDATE SET play_count = play_count + 1
    """, (date, hour, song_id, station_id))

    conn.commit()


# ==================== PLAYLIST CRUD ====================

def add_playlist(cursor, conn, name, is_auto, interval_minutes=None, station_ids=None, max_songs=None, mode=None,
                 min_plays=1, max_plays=None, days=None, enabled=True):
    """Add a new playlist (manual or auto)

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        name: Playlist name
        is_auto: TRUE for auto playlist, FALSE for manual
        interval_minutes: Update interval (required if is_auto=TRUE, NULL otherwise)
        station_ids: List of station IDs
        max_songs: Maximum number of songs
        mode: Playlist mode (merge, replace, append, create, snapshot, recent, random)
        min_plays: Minimum plays per song (default: 1)
        max_plays: Maximum plays per song (optional, NULL = no maximum)
        days: Only include songs from last N days (optional)
        enabled: Whether playlist is active (default: TRUE)

    Returns:
        playlist_id (int)
    """
    try:
        import json

        # Calculate next update time (only for auto playlists)
        next_update = None
        if is_auto and interval_minutes:
            now = datetime.now()
            next_update = now + timedelta(minutes=interval_minutes)

        # Use local time for created_at timestamp
        created_at = datetime.now()

        cursor.execute("""
            INSERT INTO playlists (
                name, is_auto, interval_minutes, station_ids, max_songs, mode,
                min_plays, max_plays, days, enabled,
                last_updated, next_update, plex_playlist_name, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
        """, (
            name,
            is_auto,
            interval_minutes,
            json.dumps(station_ids) if station_ids else '[]',
            max_songs,
            mode,
            min_plays,
            max_plays,
            days,
            enabled,
            next_update,
            name,  # plex_playlist_name same as playlist name
            created_at
        ))

        conn.commit()
        return cursor.lastrowid

    except Exception as e:
        logger.error(f"Error adding playlist: {e}")
        conn.rollback()
        raise


def update_playlist(cursor, conn, playlist_id, name=None, is_auto=None, interval_minutes=None,
                   station_ids=None, max_songs=None, mode=None,
                   min_plays=None, max_plays=None, days=None):
    """Update playlist (manual or auto)

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        playlist_id: Playlist ID
        name: New name (optional)
        is_auto: New auto status (optional)
        interval_minutes: New interval (optional)
        station_ids: New station list (optional)
        max_songs: New max songs (optional)
        mode: New mode (optional)
        min_plays: New min plays (optional)
        max_plays: New max plays filter (optional)
        days: New days filter (optional)

    Returns:
        True if updated, False if not found
    """
    try:
        import json

        # Build update query dynamically
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)

        if is_auto is not None:
            updates.append("is_auto = ?")
            params.append(is_auto)

        if interval_minutes is not None:
            updates.append("interval_minutes = ?")
            params.append(interval_minutes)
            # Recalculate next update
            next_update = datetime.now() + timedelta(minutes=interval_minutes)
            updates.append("next_update = ?")
            params.append(next_update)

        if station_ids is not None:
            updates.append("station_ids = ?")
            params.append(json.dumps(station_ids))

        if max_songs is not None:
            updates.append("max_songs = ?")
            params.append(max_songs)

        if mode is not None:
            updates.append("mode = ?")
            params.append(mode)

        if min_plays is not None:
            updates.append("min_plays = ?")
            params.append(min_plays)

        if max_plays is not None:
            updates.append("max_plays = ?")
            params.append(max_plays)

        if days is not None:
            updates.append("days = ?")
            params.append(days)

        if not updates:
            return False

        params.append(playlist_id)

        cursor.execute(f"""
            UPDATE playlists
            SET {', '.join(updates)}
            WHERE id = ?
        """, params)

        conn.commit()
        return True

    except Exception as e:
        logger.error(f"Error updating playlist {playlist_id}: {e}")
        conn.rollback()
        raise


def delete_playlist(cursor, conn, playlist_id):
    """Delete playlist (manual or auto)

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        playlist_id: Playlist ID

    Returns:
        True if deleted, False if not found
    """
    try:
        cursor.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted

    except Exception as e:
        logger.error(f"Error deleting playlist {playlist_id}: {e}")
        conn.rollback()
        raise


def set_playlist_enabled(cursor, conn, playlist_id, enabled):
    """Enable or disable playlist

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        playlist_id: Playlist ID
        enabled: True to enable, False to disable

    Returns:
        True if updated, False if not found
    """
    try:
        cursor.execute("""
            UPDATE playlists
            SET enabled = ?
            WHERE id = ?
        """, (enabled, playlist_id))

        conn.commit()
        return cursor.rowcount > 0

    except Exception as e:
        logger.error(f"Error setting enabled for playlist {playlist_id}: {e}")
        conn.rollback()
        raise


def update_playlist_next_run(cursor, conn, playlist_id, interval_minutes=None):
    """Update the next_run time for a playlist

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        playlist_id: Playlist ID
        interval_minutes: New interval (optional, uses current if not specified)

    Returns:
        True if updated, False if not found
    """
    try:
        # Get current interval if not specified
        if interval_minutes is None:
            cursor.execute("SELECT interval_minutes FROM playlists WHERE id = ?", (playlist_id,))
            row = cursor.fetchone()
            if not row:
                return False
            interval_minutes = row[0]

        # Calculate next update
        next_update = datetime.now() + timedelta(minutes=interval_minutes)

        cursor.execute("""
            UPDATE playlists
            SET next_update = ?
            WHERE id = ?
        """, (next_update, playlist_id))

        conn.commit()
        return True

    except Exception as e:
        logger.error(f"Error updating next run for playlist {playlist_id}: {e}")
        conn.rollback()
        raise


def record_playlist_update(cursor, conn, playlist_id, success=True, last_updated=None, next_update=None):
    """Record a playlist update attempt

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        playlist_id: Playlist ID
        success: True if update succeeded, False if failed
        last_updated: Optional datetime for last_updated field (default: datetime.now())
        next_update: Optional datetime for next_update field (default: calculated from interval)

    Returns:
        True if updated, False if not found
    """
    try:
        if success:
            # Use provided values or defaults
            if last_updated is None:
                last_updated = datetime.now()

            if next_update is None:
                # Calculate next_update from interval_minutes
                cursor.execute("SELECT interval_minutes FROM playlists WHERE id = ?", (playlist_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    interval_minutes = row[0]
                    from datetime import timedelta
                    next_update = last_updated + timedelta(minutes=interval_minutes)
                else:
                    next_update = last_updated

            # Update last_updated and reset failures
            cursor.execute("""
                UPDATE playlists
                SET last_updated = ?,
                    consecutive_failures = 0,
                    next_update = ?
                WHERE id = ?
            """, (last_updated, next_update, playlist_id))
        else:
            # Increment failures
            cursor.execute("""
                UPDATE playlists
                SET consecutive_failures = consecutive_failures + 1
                WHERE id = ?
            """, (playlist_id,))

        conn.commit()
        return True

    except Exception as e:
        logger.error(f"Error recording update for playlist {playlist_id}: {e}")
        conn.rollback()
        raise


# ==================== MANUAL MBID OVERRIDE CRUD ====================

def add_manual_mbid_override(cursor, artist_name_original, mbid, notes=None):
    """Add or update a manual MBID override

    Args:
        cursor: Database cursor
        artist_name_original: Artist display name (e.g., "Billy Joel")
        mbid: MusicBrainz ID (UUID format)
        notes: Optional user notes

    Returns:
        int: ID of inserted/updated record
    """
    from radio_monitor.normalization import normalize_artist_name

    # Normalize for display (title case)
    artist_name_display = normalize_artist_name(artist_name_original)
    # Normalize for matching (lowercase for case-insensitive lookups)
    artist_name_normalized = artist_name_display.lower()
    now = datetime.now()

    # UPSERT: Insert if not exists, update if exists
    cursor.execute("""
        INSERT INTO manual_mbid_overrides
            (artist_name_normalized, artist_name_original, mbid, created_at, updated_at, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(artist_name_normalized) DO UPDATE SET
            mbid = excluded.mbid,
            artist_name_original = excluded.artist_name_original,
            updated_at = excluded.updated_at,
            notes = excluded.notes
        RETURNING id
    """, (artist_name_normalized, artist_name_display, mbid, now, now, notes))

    return cursor.fetchone()[0]


def get_manual_mbid_override(cursor, artist_name):
    """Look up manual MBID override by artist name

    Args:
        cursor: Database cursor
        artist_name: Artist name to look up

    Returns:
        str or None: MBID if override exists, None otherwise
    """
    from radio_monitor.normalization import normalize_artist_name

    # Normalize for matching (lowercase for case-insensitive lookups)
    artist_name_normalized = normalize_artist_name(artist_name).lower()

    cursor.execute("""
        SELECT mbid
        FROM manual_mbid_overrides
        WHERE artist_name_normalized = ?
        LIMIT 1
    """, (artist_name_normalized,))

    result = cursor.fetchone()
    return result[0] if result else None


def get_all_manual_mbid_overrides(cursor, limit=None, offset=None):
    """Get all manual MBID overrides with pagination

    Args:
        cursor: Database cursor
        limit: Maximum number of records (optional)
        offset: Number of records to skip (optional)

    Returns:
        list: Dicts with override data
    """
    query = """
        SELECT
            id,
            artist_name_original,
            mbid,
            created_at,
            updated_at,
            notes
        FROM manual_mbid_overrides
        ORDER BY artist_name_original COLLATE NOCASE
    """

    if limit:
        query += f" LIMIT {limit}"
    if offset:
        query += f" OFFSET {offset}"

    cursor.execute(query)

    results = []
    for row in cursor.fetchall():
        results.append({
            'id': row[0],
            'artist_name': row[1],
            'mbid': row[2],
            'created_at': row[3],
            'updated_at': row[4],
            'notes': row[5]
        })

    return results


def delete_manual_mbid_override(cursor, artist_name):
    """Delete a manual MBID override

    Args:
        cursor: Database cursor
        artist_name: Artist name to delete override for

    Returns:
        bool: True if deleted, False if not found
    """
    from radio_monitor.normalization import normalize_artist_name

    # Normalize for matching (lowercase for case-insensitive lookups)
    artist_name_normalized = normalize_artist_name(artist_name).lower()

    cursor.execute("""
        DELETE FROM manual_mbid_overrides
        WHERE artist_name_normalized = ?
    """, (artist_name_normalized,))

    return cursor.rowcount > 0


# ==================== HEALTH TRACKING ====================

def record_scrape_success(cursor, conn, station_id):
    """Record successful scrape for a station

    Resets consecutive_failures to 0 and ensures station is enabled.

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        station_id: Station ID (e.g., 'wtmx')
    """
    cursor.execute("""
        UPDATE stations
        SET consecutive_failures = 0,
            enabled = 1
        WHERE id = ?
    """, (station_id,))
    conn.commit()


def record_scrape_failure(cursor, conn, station_id):
    """Record failed scrape for a station

    Increments consecutive_failures, sets last_failure_at.
    Auto-disables station after 144 consecutive failures (~24 hours at 10min intervals).

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        station_id: Station ID (e.g., 'wtmx')

    Returns:
        True if station was auto-disabled, False otherwise
    """
    return increment_station_failure_count(cursor, conn, station_id)


# ==================== SCRAPING HELPERS ====================

def add_artist_if_new(cursor, conn, mbid, name):
    """Add artist to database if not already present

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        mbid: MusicBrainz ID (primary key)
        name: Artist name

    Returns:
        True if added, False if already existed
    """
    try:
        # Normalize artist name before storage
        normalized_name = normalize_artist_name(name)

        # Try to insert the artist (handle race condition where another thread inserts first)
        try:
            now = datetime.now()
            cursor.execute("""
                INSERT INTO artists (mbid, name, first_seen_at, last_seen_at, needs_lidarr_import)
                VALUES (?, ?, ?, ?, 1)
            """, (mbid, normalized_name, now, now))

            conn.commit()
            return True

        except sqlite3.IntegrityError:
            # MBID already exists (race condition - another thread inserted it between our check and insert)
            # Just verify the artist exists and return False
            logger.debug(f"Artist {mbid} ({name}) already exists (added by another thread)")
            conn.rollback()
            return False

    except Exception as e:
        logger.error(f"Error adding artist {mbid}: {e}")
        conn.rollback()
        raise


def add_song_if_new(cursor, conn, artist_mbid, song_title):
    """Add song to database if not already present

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        artist_mbid: Artist's MusicBrainz ID
        song_title: Song title

    Returns:
        Tuple of (added: bool, song_id: int)
    """
    try:
        # Normalize song title before storage
        normalized_title = normalize_song_title(song_title)

        # Check if song exists (check against normalized title in song_title column)
        cursor.execute("""
            SELECT id FROM songs
            WHERE artist_mbid = ? AND song_title = ?
        """, (artist_mbid, normalized_title))

        existing = cursor.fetchone()
        if existing:
            return (False, existing[0])

        # Get artist name from artists table (already normalized)
        cursor.execute("SELECT name FROM artists WHERE mbid = ?", (artist_mbid,))
        artist_row = cursor.fetchone()
        if not artist_row:
            logger.error(f"Artist MBID {artist_mbid} not found in artists table")
            return (False, None)

        artist_name = artist_row[0]

        # Add new song with normalized title (stored in song_title column)
        cursor.execute("""
            INSERT INTO songs (artist_mbid, artist_name, song_title, play_count)
            VALUES (?, ?, ?, 0)
        """, (artist_mbid, artist_name, normalized_title))

        conn.commit()
        return (True, cursor.lastrowid)

    except Exception as e:
        logger.error(f"Error adding song '{song_title}': {e}")
        conn.rollback()
        raise


def record_play(cursor, conn, song_id, station_id, play_count=1):
    """Record a play for a song on a station

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        song_id: Song ID from songs table
        station_id: Station ID from stations table
        play_count: Number of plays to record (default: 1)

    Returns:
        True if successful, False if skipped (duplicate)
    """
    try:
        from datetime import datetime
        from radio_monitor.gui import load_settings

        # Get settings for duplicate detection window
        settings = load_settings() or {}
        duplicate_window_min = settings.get('duplicate_detection_window_minutes', 20)

        # Get current date, hour, and minute from a SINGLE timestamp
        # CRITICAL: Must call datetime.now() ONCE to avoid midnight rollover bugs
        now = datetime.now()
        today = now.date().isoformat()
        current_hour = now.hour
        current_minute = now.minute

        # Step 1: Check for recent play within time window (duplicate detection)
        # Check current hour, previous hour, and next hour for cross-hour duplicates
        cursor.execute("""
            SELECT hour, minute, play_count
            FROM song_plays_daily
            WHERE song_id = ? AND station_id = ? AND date = ?
            AND hour IN (?, ?, ?)
        """, (song_id, station_id, today, current_hour - 1, current_hour, current_hour + 1))

        all_plays = cursor.fetchall()
        duplicate_found = False

        for existing_hour, existing_minute, existing_count in all_plays:
            if existing_minute is not None:
                # Calculate time difference in minutes (cross-hour aware)
                existing_total_min = existing_hour * 60 + existing_minute
                current_total_min = current_hour * 60 + current_minute
                time_diff_min = abs(current_total_min - existing_total_min)

                # If play was recorded recently (within time window), skip
                # Use <= to catch exact hourly scraping (60 min) plus buffer (5 min = 65 min)
                if time_diff_min <= duplicate_window_min:
                    logger.debug(f"Skipping duplicate play: song_id={song_id}, station_id={station_id}, "
                               f"time_diff={time_diff_min}min <= window={duplicate_window_min}min")
                    duplicate_found = True
                    break  # Found duplicate, stop checking

        if duplicate_found:
            return False  # Skip recording

        # Step 2: Check if there's already a record in the current hour (to update vs insert)
        cursor.execute("""
            SELECT play_count
            FROM song_plays_daily
            WHERE song_id = ? AND station_id = ? AND date = ? AND hour = ?
        """, (song_id, station_id, today, current_hour))

        current_hour_record = cursor.fetchone()

        if current_hour_record:
            # Update existing record in current hour
            cursor.execute("""
                UPDATE song_plays_daily
                SET play_count = play_count + ?, minute = ?
                WHERE song_id = ? AND station_id = ? AND date = ? AND hour = ?
            """, (play_count, current_minute, song_id, station_id, today, current_hour))
        else:
            # Create new record
            cursor.execute("""
                INSERT INTO song_plays_daily (song_id, station_id, date, hour, minute, play_count)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (song_id, station_id, today, current_hour, current_minute, play_count))

        # Also update song's total play count and last_seen_at
        cursor.execute("""
            UPDATE songs
            SET play_count = play_count + ?,
                last_seen_at = ?
            WHERE id = ?
        """, (play_count, now, song_id))

        # Update artist last_seen_at
        cursor.execute("""
            UPDATE artists
            SET last_seen_at = ?
            WHERE mbid = (SELECT artist_mbid FROM songs WHERE id = ?)
        """, (now, song_id))

        conn.commit()
        return True

    except Exception as e:
        logger.error(f"Error recording play for song_id {song_id}: {e}")
        conn.rollback()
        raise


def delete_pending_artists_older_than(cursor, conn, days=30):
    """Delete PENDING artists older than specified days

    This function cleans up old PENDING artists that were never resolved.
    Also deletes orphaned songs (songs whose artist was deleted).

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        days: Delete artists older than this many days (default: 30)

    Returns:
        Number of artists deleted
    """
    try:
        # Delete PENDING artists older than specified days
        cursor.execute("""
            DELETE FROM artists
            WHERE mbid LIKE 'PENDING-%'
              AND first_seen_at < datetime('now', '-' || ? || ' days')
        """, (days,))

        artists_deleted = cursor.rowcount
        logger.info(f"Deleted {artists_deleted} PENDING artists older than {days} days")

        # Delete orphaned songs (songs whose PENDING artist was deleted)
        cursor.execute("""
            DELETE FROM songs
            WHERE artist_mbid LIKE 'PENDING-%'
              AND artist_mbid NOT IN (SELECT mbid FROM artists)
        """)

        songs_deleted = cursor.rowcount
        logger.info(f"Deleted {songs_deleted} orphaned songs from deleted PENDING artists")

        conn.commit()
        return artists_deleted

    except Exception as e:
        logger.error(f"Error deleting old PENDING artists: {e}")
        conn.rollback()
        raise
