"""
Database export functions for Radio Monitor 1.0

This module contains functions for exporting data to external systems:
- Lidarr export: Artist data for import
- Plex export: Song data for playlists

Export functions prepare data in the format required by external APIs.
"""

import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


def get_artists_for_lidarr_export(cursor, station_id=None):
    """Get artists for Lidarr export

    Args:
        cursor: SQLite cursor object
        station_id: Filter by station (None = all)

    Returns:
        List of dicts with artist data suitable for Lidarr import
    """
    if station_id:
        cursor.execute("""
            SELECT DISTINCT a.mbid, a.name
            FROM artists a
            JOIN songs s ON a.mbid = s.artist_mbid
            WHERE a.mbid IS NOT NULL
              AND a.mbid NOT LIKE 'PENDING-%'
              AND a.first_seen_station = ?
            ORDER BY a.name
        """, (station_id,))
    else:
        cursor.execute("""
            SELECT DISTINCT mbid, name
            FROM artists
            WHERE mbid IS NOT NULL
              AND mbid NOT LIKE 'PENDING-%'
            ORDER BY name
        """)

    columns = ['mbid', 'name']
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_songs_for_plex_export(cursor, station_ids=None, min_plays=1, max_plays=None, days=None,
                              mode='merge', limit=None):
    """Get songs for Plex playlist export

    Args:
        cursor: SQLite cursor object
        station_ids: Filter by stations (None = all)
        min_plays: Minimum play count (default: 1)
        max_plays: Maximum play count (NULL = no maximum)
        days: Only include songs from last N days (NULL = all time)
        mode: Playlist mode (merge, replace, append, create, snapshot, recent, random)
        limit: Maximum songs to return (NULL = no limit)

    Returns:
        List of dicts with song data suitable for Plex playlist creation
    """
    # Build query components
    conditions = []
    params = []

    # Station filter
    if station_ids:
        placeholders = ','.join(['?' for _ in station_ids])
        conditions.append(f"d.station_id IN ({placeholders})")
        params.extend(station_ids)

    # Days filter
    if days:
        conditions.append("s.last_seen_at >= datetime('now', '-' || ? || ' days')")
        params.append(days)

    # Build WHERE clause
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Build HAVING clause for play count range
    having_clause = "HAVING total_plays >= ?"
    params.append(min_plays)

    if max_plays is not None:
        having_clause += " AND total_plays <= ?"
        params.append(max_plays)

    # Determine ORDER BY based on mode
    if mode == 'recent':
        order_by = "ORDER BY s.last_seen_at DESC"
    elif mode == 'random':
        order_by = "ORDER BY RANDOM()"
    else:
        order_by = "ORDER BY total_plays DESC"

    # Add LIMIT if specified
    limit_clause = f"LIMIT {limit}" if limit else ""

    # Build complete query
    query = f"""
        SELECT
            s.song_title,
            s.artist_name,
            s.play_count,
            SUM(d.play_count) as total_plays
        FROM song_plays_daily d
        JOIN songs s ON d.song_id = s.id
        WHERE {where_clause}
        GROUP BY s.id
        {having_clause}
        {order_by}
        {limit_clause}
    """

    cursor.execute(query, params)

    columns = ['song_title', 'artist_name', 'play_count', 'total_plays']
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def export_to_json(cursor, output_file, station_id=None):
    """Export database to JSON

    Args:
        cursor: SQLite cursor object
        output_file: Output file path
        station_id: Filter by station (None = all)

    Returns:
        Number of songs exported
    """
    # Import queries module for get_all_songs
    from .queries import get_all_songs

    songs = get_all_songs(cursor, station_id)

    export_data = {
        'export_timestamp': datetime.now().isoformat(),
        'station': station_id or 'all',
        'total_songs': len(songs),
        'songs': [
            {
                'artist': row[0],
                'song': row[1],
                'artist_mbid': row[2],
                'play_count': row[3],
                'first_seen': row[4],
                'last_seen': row[5]
            }
            for row in songs
        ]
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    return len(songs)


def export_database_for_sharing(source_db_path, output_path):
    """Export database for sharing with friends

    Creates a clean copy of the database with:
    - Playlists removed (user-specific)
    - Lidarr import status reset (all artists need import)
    - All discovery data preserved (first_seen, last_seen, play counts)

    Args:
        source_db_path: Path to source database
        output_path: Path for exported database

    Returns:
        True if successful, False otherwise
    """
    import shutil
    import sqlite3

    try:
        logger.info(f"Exporting database for sharing: {source_db_path} -> {output_path}")

        # Step 1: Copy database to new location
        shutil.copy2(source_db_path, output_path)
        logger.info(f"Database copied to {output_path}")

        # Step 2: Connect to exported database and clean it
        conn = sqlite3.connect(output_path)
        cursor = conn.cursor()

        # Step 3: Delete user-specific tables
        # Delete playlists (user-specific)
        cursor.execute("DELETE FROM playlists")
        deleted_playlists = cursor.rowcount
        logger.info(f"Deleted {deleted_playlists} playlists")

        # Delete activity log (user-specific activity history)
        cursor.execute("DELETE FROM activity_log")
        deleted_activity = cursor.rowcount
        logger.info(f"Deleted {deleted_activity} activity log entries")

        # Delete Plex match failures (user-specific)
        cursor.execute("DELETE FROM plex_match_failures")
        deleted_failures = cursor.rowcount
        logger.info(f"Deleted {deleted_failures} Plex match failures")

        # Delete notifications (user-specific notification configs)
        cursor.execute("DELETE FROM notifications")
        deleted_notifications = cursor.rowcount
        logger.info(f"Deleted {deleted_notifications} notification configs")

        # Delete notification history (user-specific notification history)
        cursor.execute("DELETE FROM notification_history")
        deleted_history = cursor.rowcount
        logger.info(f"Deleted {deleted_history} notification history entries")

        # Step 4: Reset Lidarr import status for all artists
        cursor.execute("""
            UPDATE artists
            SET needs_lidarr_import = 1,
                lidarr_imported_at = NULL
        """)
        reset_artists = cursor.rowcount
        logger.info(f"Reset import status for {reset_artists} artists")

        # Step 5: Verify schema version
        cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        result = cursor.fetchone()
        if result:
            schema_version = result[0]
            logger.info(f"Schema version: {schema_version}")
        else:
            logger.warning("No schema version found")

        # Step 6: Commit changes
        conn.commit()
        conn.close()

        logger.info(f"Database export complete: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error exporting database for sharing: {e}")
        # Clean up failed export
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
        return False
