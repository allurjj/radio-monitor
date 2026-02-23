"""
Database package for Radio Monitor 1.0

This package provides a modular database interface with:
- schema.py: Database table definitions
- migrations.py: Schema migration functions
- queries.py: SELECT query methods
- crud.py: INSERT/UPDATE/DELETE operations
- exports.py: Lidarr/Plex export functions
- activity.py: Activity logging functions

The main RadioDatabase class (below) provides a unified interface
to all database operations with backward compatibility.

Schema Version: 12 (Manual Playlist Support)
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Import schema functions
from .schema import create_tables, populate_stations
# Import migration functions
from .migrations import _initialize_schema
# Import query functions
from . import queries
# Import CRUD functions
from . import crud
# Import export functions
from . import exports


class RadioDatabase:
    """SQLite database with 14-table schema

    This is the main database interface that provides backward compatibility
    with the original database.py module while using the refactored submodules.

    Tables:
    - stations: Radio station metadata
    - artists: Artist information (MBID as primary key)
    - songs: Song catalog
    - song_plays_daily: Daily play tracking
    - schema_version: Schema version tracking
    - playlists: Unified playlists (manual + auto)
    - activity_log: System activity and event tracking
    - plex_match_failures: Plex matching failure tracking
    - notifications: Notification configurations
    - notification_history: Notification send history
    - manual_mbid_overrides: User-specified MBID mappings (v9)
    - ai_playlist_generations: AI playlist generation tracking (v10)
    - manual_playlists: Manual playlist definitions (v12)
    - manual_playlist_songs: Manual playlist song associations (v12)
    - playlist_builder_state: In-progress playlist builder state (v12)
    """

    # Current schema version
    SCHEMA_VERSION = 12

    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

    def connect(self):
        """Connect to database and create/update schema if needed"""
        # Allow connection to be used across threads (required for Flask multi-threading)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()

        # Enable foreign keys
        self.cursor.execute("PRAGMA foreign_keys = ON")

        # Check if we need to migrate or create schema
        _initialize_schema(self.cursor, self.conn, self.db_path, self.SCHEMA_VERSION)

    def get_cursor(self):
        """Get a new cursor for the current request

        This creates a fresh cursor for each request to avoid 'Recursive use of cursors' errors
        when multiple Flask requests use the database simultaneously.
        """
        return self.conn.cursor()

    # ==================== STATION METHODS ====================

    def get_all_stations(self):
        """Get all stations with health status"""
        cursor = self.conn.cursor()
        try:
            return queries.get_all_stations(cursor)
        finally:
            cursor.close()

    def get_station(self, station_id):
        """Get station by ID"""
        cursor = self.conn.cursor()
        try:
            return queries.get_station_by_id(cursor, station_id)
        finally:
            cursor.close()

    def get_all_stations_with_health(self):
        """Get all stations with health status"""
        cursor = self.conn.cursor()
        try:
            return queries.get_all_stations_with_health(cursor)
        finally:
            cursor.close()

    def get_station_health(self, station_id):
        """Get health status for a single station"""
        cursor = self.conn.cursor()
        try:
            return queries.get_station_health(cursor, station_id)
        finally:
            cursor.close()

    def add_station(self, station_id, name, url, genre, market, has_mbid=False, scraper_type='iheart', wait_time=10):
        """Add a new station to the database"""
        cursor = self.conn.cursor()
        try:
            return crud.add_station(cursor, self.conn, station_id, name, url, genre, market,
                                  has_mbid, scraper_type, wait_time)
        finally:
            cursor.close()

    def delete_station(self, station_id):
        """Delete a station from the database"""
        cursor = self.conn.cursor()
        try:
            return crud.delete_station(cursor, self.conn, station_id)
        finally:
            cursor.close()

    def get_station_config(self, station_id):
        """Get station scraper configuration"""
        cursor = self.conn.cursor()
        try:
            return queries.get_station_config(cursor, station_id)
        finally:
            cursor.close()

    def update_station_failure(self, station_id, failed):
        """Update station failure tracking"""
        cursor = self.conn.cursor()
        try:
            if failed:
                return crud.increment_station_failure_count(cursor, self.conn, station_id)
            else:
                crud.record_scrape_success(cursor, self.conn, station_id)
        finally:
            cursor.close()

    def disable_station(self, station_id):
        """Disable a station (after too many failures)"""
        cursor = self.conn.cursor()
        try:
            crud.disable_station(cursor, self.conn, station_id)
        finally:
            cursor.close()

    def enable_station(self, station_id):
        """Enable a station"""
        cursor = self.conn.cursor()
        try:
            crud.enable_station(cursor, self.conn, station_id)
        finally:
            cursor.close()

    # ==================== ARTIST METHODS ====================

    def add_artist(self, mbid, name, first_seen_station):
        """Add or update artist"""
        cursor = self.conn.cursor()
        try:
            return crud.add_artist(cursor, self.conn, mbid, name, first_seen_station)
        finally:
            cursor.close()

    def get_artist_by_name(self, name):
        """Get artist by name"""
        cursor = self.conn.cursor()
        try:
            return queries.get_artist_by_name(cursor, name)
        finally:
            cursor.close()

    def get_artist_by_mbid(self, mbid):
        """Get artist by MBID"""
        cursor = self.conn.cursor()
        try:
            return queries.get_artist_by_mbid(cursor, mbid)
        finally:
            cursor.close()

    def get_all_artists(self):
        """Get all artists"""
        cursor = self.conn.cursor()
        try:
            return queries.get_all_artists(cursor)
        finally:
            cursor.close()

    def update_artist_mbid(self, artist_name, mbid):
        """Update artist MBID (DEPRECATED - use update_artist_mbid_from_pending)"""
        logger.warning("update_artist_mbid is deprecated, use update_artist_mbid_from_pending instead")
        # Still implement for backward compatibility
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                UPDATE artists
                SET mbid = ?
                WHERE name = ? AND mbid IS NULL
            """, (mbid, artist_name))
            self.conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()

    def update_artist_mbid_from_pending(self, artist_name, mbid):
        """Update artist MBID (for resolving NULL or PENDING MBIDs)"""
        cursor = self.conn.cursor()
        try:
            return crud.update_artist_mbid_from_pending(cursor, self.conn, artist_name, mbid)
        finally:
            cursor.close()

    def get_pending_artists(self):
        """Get all artists with PENDING MBIDs"""
        cursor = self.conn.cursor()
        try:
            return queries.get_pending_artists(cursor)
        finally:
            cursor.close()

    def mark_artist_imported_to_lidarr(self, mbid):
        """Mark artist as imported to Lidarr"""
        cursor = self.conn.cursor()
        try:
            return crud.mark_single_artist_imported_to_lidarr(cursor, self.conn, mbid)
        finally:
            cursor.close()

    def mark_artists_imported(self, mbids):
        """Mark multiple artists as imported to Lidarr"""
        cursor = self.conn.cursor()
        try:
            return crud.mark_artists_imported_to_lidarr(cursor, self.conn, mbids)
        finally:
            cursor.close()

    def reset_all_lidarr_import_status(self):
        """Reset all artists to "Needs Import" status

        Useful when sharing databases with friends or re-importing to Lidarr.

        Returns:
            Number of artists reset
        """
        cursor = self.conn.cursor()
        try:
            return crud.reset_all_lidarr_import_status(cursor, self.conn)
        finally:
            cursor.close()

    def delete_pending_artists_older_than(self, days=30):
        """Delete PENDING artists older than specified days

        Args:
            days: Delete artists older than this many days (default: 30)

        Returns:
            Number of artists deleted
        """
        cursor = self.conn.cursor()
        try:
            return crud.delete_pending_artists_older_than(cursor, self.conn, days)
        finally:
            cursor.close()

    def get_artists_for_import(self, min_plays=5, station_id=None, sort='total_plays', direction='desc'):
        """Get artists that need Lidarr import

        Args:
            min_plays: Minimum total plays (default: 5)
            station_id: Optional station ID to filter by
            sort: Column to sort by (default: 'total_plays')
            direction: Sort direction 'asc' or 'desc' (default: 'desc')
        """
        cursor = self.conn.cursor()
        try:
            return queries.get_artists_for_import(cursor, min_plays, station_id, sort, direction)
        finally:
            cursor.close()

    # ==================== SONG METHODS ====================

    def add_song(self, artist_mbid, artist_name, song_title, station_id=None):
        """Add or update song"""
        cursor = self.conn.cursor()
        try:
            return crud.add_song(cursor, self.conn, artist_mbid, artist_name, song_title, station_id)
        finally:
            cursor.close()

    def get_song_by_id(self, song_id):
        """Get song by ID"""
        cursor = self.conn.cursor()
        try:
            return queries.get_song_by_id(cursor, song_id)
        finally:
            cursor.close()

    def get_all_songs(self, station_id=None):
        """Get all songs for export"""
        cursor = self.conn.cursor()
        try:
            return queries.get_all_songs(cursor, station_id)
        finally:
            cursor.close()

    def increment_play_count(self, date, hour, song_id, station_id):
        """Increment play count for a song on a specific date/hour/station"""
        cursor = self.conn.cursor()
        try:
            crud.increment_play_count(cursor, self.conn, date, hour, song_id, station_id)
        finally:
            cursor.close()

    # ==================== QUERY METHODS ====================

    def get_stats(self):
        """Get database statistics"""
        cursor = self.conn.cursor()
        try:
            return queries.get_statistics(cursor)
        finally:
            cursor.close()

    def get_top_songs(self, days=None, station_id=None, station_ids=None, limit=50):
        """Get top songs by play count"""
        # Use a fresh cursor to avoid 'Recursive use of cursors' error in multi-threaded Flask
        cursor = self.conn.cursor()
        try:
            return queries.get_top_songs(cursor, days, station_id, station_ids, limit)
        finally:
            cursor.close()

    def get_recent_songs(self, days=None, station_ids=None, limit=50):
        """Get most recently played songs"""
        # Use a fresh cursor to avoid 'Recursive use of cursors' error in multi-threaded Flask
        cursor = self.conn.cursor()
        try:
            return queries.get_recent_songs(cursor, days, station_ids, limit)
        finally:
            cursor.close()

    def get_top_artists(self, days=None, station_ids=None, limit=50):
        """Get top artists by play count"""
        # Use a fresh cursor to avoid 'Recursive use of cursors' error in multi-threaded Flask
        cursor = self.conn.cursor()
        try:
            return queries.get_top_artists(cursor, days, station_ids, limit)
        finally:
            cursor.close()

    def get_trending_songs(self, days=90):
        """Get trending songs (recent plays vs older plays)"""
        cursor = self.conn.cursor()
        try:
            return queries.get_trending_songs(cursor, days)
        finally:
            cursor.close()

    # ==================== EXPORT METHODS ====================

    def export_to_json(self, output_file, station_id=None):
        """Export database to JSON"""
        cursor = self.conn.cursor()
        try:
            return exports.export_to_json(cursor, output_file, station_id)
        finally:
            cursor.close()

    def get_artists_for_lidarr_export(self, station_id=None):
        """Get artists for Lidarr export"""
        cursor = self.conn.cursor()
        try:
            return exports.get_artists_for_lidarr_export(cursor, station_id)
        finally:
            cursor.close()

    def get_songs_for_plex_export(self, station_ids=None, min_plays=1, max_plays=None, days=None,
                                  mode='merge', limit=None):
        """Get songs for Plex playlist export"""
        cursor = self.conn.cursor()
        try:
            return exports.get_songs_for_plex_export(cursor, station_ids, min_plays, max_plays,
                                                    days, mode, limit)
        finally:
            cursor.close()

    # ==================== GUI METHODS ====================

    def get_recent_plays(self, limit=10, station_id=None):
        """Get recent plays for dashboard live feed

        Args:
            limit: Maximum number of plays to return (default: 10)
            station_id: Filter by specific station ID (default: None = all stations)
        """
        # Use a fresh cursor to avoid 'Recursive use of cursors' error in multi-threaded Flask
        cursor = self.conn.cursor()
        try:
            return queries.get_recent_plays(cursor, limit, station_id)
        finally:
            cursor.close()

    # ==================== CHART QUERY METHODS ====================

    def get_plays_over_time(self, days=30, station_id=None):
        """Get play counts over time for line chart

        Args:
            days: Number of days to look back (default: 30)
            station_id: Filter by specific station (optional)
        """
        # Use a fresh cursor to avoid 'Recursive use of cursors' error in multi-threaded Flask
        cursor = self.conn.cursor()
        try:
            return queries.get_plays_over_time(cursor, days, station_id)
        finally:
            cursor.close()

    def get_station_distribution(self, days=None):
        """Get play distribution by station for pie chart

        Args:
            days: Number of days to look back (None = all time)
        """
        # Use a fresh cursor to avoid 'Recursive use of cursors' error in multi-threaded Flask
        cursor = self.conn.cursor()
        try:
            return queries.get_station_distribution(cursor, days)
        finally:
            cursor.close()

    def get_daily_plays_chart_data(self, days=30):
        """Get daily plays for chart"""
        cursor = self.conn.cursor()
        try:
            return queries.get_daily_plays_chart_data(cursor, days)
        finally:
            cursor.close()

    def get_hourly_plays_chart_data(self):
        """Get hourly plays for heat map"""
        cursor = self.conn.cursor()
        try:
            return queries.get_hourly_plays_chart_data(cursor)
        finally:
            cursor.close()

    def get_dashboard_stats(self):
        """Get dashboard statistics"""
        cursor = self.conn.cursor()
        try:
            return queries.get_dashboard_stats(cursor)
        finally:
            cursor.close()

    # ==================== STATION HEALTH TRACKING METHODS ====================

    def record_scrape_success(self, station_id):
        """Record successful scrape for a station"""
        cursor = self.conn.cursor()
        try:
            crud.record_scrape_success(cursor, self.conn, station_id)
        finally:
            cursor.close()

    def record_scrape_failure(self, station_id):
        """Record failed scrape for a station"""
        cursor = self.conn.cursor()
        try:
            return crud.record_scrape_failure(cursor, self.conn, station_id)
        finally:
            cursor.close()

    # ==================== SCRAPING HELPER METHODS ====================

    def get_station_by_id(self, station_id):
        """Get station information by ID"""
        cursor = self.conn.cursor()
        try:
            return queries.get_station_by_id(cursor, station_id)
        finally:
            cursor.close()

    def add_artist_if_new(self, mbid, name):
        """Add artist to database if not already present"""
        cursor = self.conn.cursor()
        try:
            return crud.add_artist_if_new(cursor, self.conn, mbid, name)
        finally:
            cursor.close()

    def add_song_if_new(self, artist_mbid, song_title):
        """Add song to database if not already present"""
        cursor = self.conn.cursor()
        try:
            return crud.add_song_if_new(cursor, self.conn, artist_mbid, song_title)
        finally:
            cursor.close()

    def record_play(self, song_id, station_id, play_count=1):
        """Record a play for a song on a station"""
        cursor = self.conn.cursor()
        try:
            return crud.record_play(cursor, self.conn, song_id, station_id, play_count)
        finally:
            cursor.close()

    # ==================== PLAYLISTS (Unified: Manual + Auto) ====================

    def add_playlist(self, name, is_auto, interval_minutes=None, station_ids=None, max_songs=None, mode=None,
                     min_plays=1, max_plays=None, days=None, enabled=True):
        """Add a new playlist (manual or auto)"""
        cursor = self.conn.cursor()
        try:
            return crud.add_playlist(cursor, self.conn, name, is_auto, interval_minutes, station_ids,
                                   max_songs, mode, min_plays, max_plays, days, enabled)
        finally:
            cursor.close()

    def get_playlists(self):
        """Get all playlists (manual and auto)"""
        cursor = self.conn.cursor()
        try:
            return queries.get_playlists(cursor)
        finally:
            cursor.close()

    def get_playlist(self, playlist_id):
        """Get single playlist by ID (manual or auto)"""
        cursor = self.conn.cursor()
        try:
            return queries.get_playlist(cursor, playlist_id)
        finally:
            cursor.close()

    def update_playlist(self, playlist_id, name=None, is_auto=None, interval_minutes=None,
                       station_ids=None, max_songs=None, mode=None,
                       min_plays=None, max_plays=None, days=None):
        """Update playlist (manual or auto)"""
        cursor = self.conn.cursor()
        try:
            return crud.update_playlist(cursor, self.conn, playlist_id, name, is_auto, interval_minutes,
                                       station_ids, max_songs, mode, min_plays, max_plays, days)
        finally:
            cursor.close()

    def delete_playlist(self, playlist_id):
        """Delete playlist (manual or auto)"""
        cursor = self.conn.cursor()
        try:
            return crud.delete_playlist(cursor, self.conn, playlist_id)
        finally:
            cursor.close()

    def set_playlist_enabled(self, playlist_id, enabled):
        """Enable or disable playlist"""
        cursor = self.conn.cursor()
        try:
            return crud.set_playlist_enabled(cursor, self.conn, playlist_id, enabled)
        finally:
            cursor.close()

    def update_playlist_next_run(self, playlist_id, interval_minutes=None):
        """Update the next_run time for a playlist"""
        cursor = self.conn.cursor()
        try:
            return crud.update_playlist_next_run(cursor, self.conn, playlist_id, interval_minutes)
        finally:
            cursor.close()

    def record_playlist_update(self, playlist_id, success=True, last_updated=None, next_update=None):
        """Record a playlist update attempt

        Args:
            playlist_id: Playlist ID
            success: True if update succeeded, False if failed
            last_updated: Optional datetime for last_updated field
            next_update: Optional datetime for next_update field
        """
        # Use a fresh cursor to avoid threading issues
        cursor = self.get_cursor()
        try:
            return crud.record_playlist_update(cursor, self.conn, playlist_id, success, last_updated, next_update)
        finally:
            cursor.close()

    def get_due_playlists(self):
        """Get auto playlists that need updating"""
        cursor = self.conn.cursor()
        try:
            return queries.get_due_playlists(cursor)
        finally:
            cursor.close()

    def get_random_songs(self, station_ids=None, min_plays=1, max_plays=None, days=None, limit=50):
        """Get random songs from filtered results"""
        cursor = self.conn.cursor()
        try:
            return queries.get_random_songs(cursor, station_ids, min_plays, max_plays, days, limit)
        finally:
            cursor.close()

    def get_ai_playlist_songs(self, station_ids=None, min_plays=1, first_seen=None, last_seen=None):
        """Get songs for AI playlist generation

        Args:
            station_ids: Filter by stations (None or empty list = all stations)
            min_plays: Minimum play count (default: 1)
            first_seen: First seen date filter (ISO format string, e.g., "2026-01-01")
            last_seen: Last seen date filter (ISO format string, e.g., "2026-02-16")

        Returns:
            List of tuples: (artist_name, song_title)
        """
        # Use a fresh cursor to avoid 'Recursive use of cursors' error in multi-threaded Flask
        cursor = self.conn.cursor()
        try:
            return queries.get_ai_playlist_songs(cursor, station_ids, min_plays, first_seen, last_seen)
        finally:
            cursor.close()

    # ==================== MANUAL PLAYLISTS (v12) ====================

    def create_manual_playlist(self, name, plex_playlist_name=None):
        """Create a new manual playlist

        Args:
            name: Internal playlist name (must be unique)
            plex_playlist_name: Optional name for Plex (defaults to name if not provided)

        Returns:
            playlist_id (int) of created playlist
        """
        cursor = self.conn.cursor()
        try:
            return crud.create_manual_playlist(cursor, self.conn, name, plex_playlist_name)
        finally:
            cursor.close()

    def get_manual_playlist(self, playlist_id):
        """Get a single manual playlist by ID

        Args:
            playlist_id: Playlist ID

        Returns:
            Dict with playlist info or None if not found
        """
        cursor = self.conn.cursor()
        try:
            return queries.get_manual_playlist(cursor, playlist_id)
        finally:
            cursor.close()

    def get_all_manual_playlists(self):
        """Get all manual playlists

        Returns:
            List of dicts with playlist info including song counts
        """
        cursor = self.conn.cursor()
        try:
            return queries.get_manual_playlists(cursor)
        finally:
            cursor.close()

    def update_manual_playlist(self, playlist_id, name=None, plex_playlist_name=None):
        """Update manual playlist metadata

        Args:
            playlist_id: Playlist ID to update
            name: New internal name (optional)
            plex_playlist_name: New Plex name (optional)

        Returns:
            True if updated, False if playlist not found
        """
        cursor = self.conn.cursor()
        try:
            return crud.update_manual_playlist(cursor, self.conn, playlist_id, name, plex_playlist_name)
        finally:
            cursor.close()

    def delete_manual_playlist(self, playlist_id):
        """Delete a manual playlist and all its song associations

        Args:
            playlist_id: Playlist ID to delete

        Returns:
            True if deleted, False if not found
        """
        cursor = self.conn.cursor()
        try:
            return crud.delete_manual_playlist(cursor, self.conn, playlist_id)
        finally:
            cursor.close()

    def add_song_to_manual_playlist(self, playlist_id, song_id):
        """Add a song to a manual playlist

        Args:
            playlist_id: Playlist ID
            song_id: Song ID to add

        Returns:
            True if added, False if song already in playlist
        """
        cursor = self.conn.cursor()
        try:
            return crud.add_song_to_manual_playlist(cursor, self.conn, playlist_id, song_id)
        finally:
            cursor.close()

    def remove_song_from_manual_playlist(self, playlist_id, song_id):
        """Remove a song from a manual playlist

        Args:
            playlist_id: Playlist ID
            song_id: Song ID to remove

        Returns:
            True if removed, False if song not in playlist
        """
        cursor = self.conn.cursor()
        try:
            return crud.remove_song_from_manual_playlist(cursor, self.conn, playlist_id, song_id)
        finally:
            cursor.close()

    def get_manual_playlist_songs(self, playlist_id, limit=None, offset=None):
        """Get all songs in a manual playlist

        Args:
            playlist_id: Playlist ID
            limit: Optional limit for pagination
            offset: Optional offset for pagination

        Returns:
            List of dicts with song details
        """
        cursor = self.conn.cursor()
        try:
            return queries.get_manual_playlist_songs(cursor, playlist_id, limit, offset)
        finally:
            cursor.close()

    def clear_manual_playlist(self, playlist_id):
        """Remove all songs from a manual playlist (keep playlist, clear songs)

        Args:
            playlist_id: Playlist ID to clear

        Returns:
            Number of songs removed
        """
        cursor = self.conn.cursor()
        try:
            return crud.clear_manual_playlist(cursor, self.conn, playlist_id)
        finally:
            cursor.close()

    # ==================== PLAYLIST BUILDER STATE (v12) ====================

    def add_song_to_builder_state(self, session_id, song_id):
        """Add a song to the playlist builder state for a session

        Args:
            session_id: Flask session ID
            song_id: Song ID to add

        Returns:
            True if added, False if song already in state
        """
        cursor = self.conn.cursor()
        try:
            return crud.add_song_to_builder_state(cursor, self.conn, session_id, song_id)
        finally:
            cursor.close()

    def remove_song_from_builder_state(self, session_id, song_id):
        """Remove a song from the playlist builder state

        Args:
            session_id: Flask session ID
            song_id: Song ID to remove

        Returns:
            True if removed, False if song not in state
        """
        cursor = self.conn.cursor()
        try:
            return crud.remove_song_from_builder_state(cursor, self.conn, session_id, song_id)
        finally:
            cursor.close()

    def get_builder_state_songs(self, session_id):
        """Get all songs in the playlist builder state for a session

        Args:
            session_id: Flask session ID

        Returns:
            List of dicts with song details
        """
        cursor = self.conn.cursor()
        try:
            return queries.get_builder_state_songs(cursor, session_id)
        finally:
            cursor.close()

    def clear_builder_state(self, session_id):
        """Clear all songs from the playlist builder state for a session

        Args:
            session_id: Flask session ID

        Returns:
            Number of songs removed
        """
        cursor = self.conn.cursor()
        try:
            return crud.clear_builder_state(cursor, self.conn, session_id)
        finally:
            cursor.close()

    def get_builder_state_song_ids(self, session_id):
        """Get list of song IDs in the playlist builder state for a session

        Args:
            session_id: Flask session ID

        Returns:
            List of song IDs (integers)
        """
        cursor = self.conn.cursor()
        try:
            return queries.get_builder_state_song_ids(cursor, session_id)
        finally:
            cursor.close()

    # ==================== CONNECTION MANAGEMENT ====================

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def get_thread_local_connection(self):
        """Create a new database connection for use in background threads

        This creates a fresh connection that won't block the main Flask database connection.
        Use this for background jobs to avoid blocking Flask requests.

        Returns:
            RadioDatabase instance with a new connection
        """
        thread_local_db = RadioDatabase(self.db_path)
        thread_local_db.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        thread_local_db.cursor = thread_local_db.conn.cursor()
        thread_local_db.cursor.execute("PRAGMA foreign_keys = ON")
        return thread_local_db


__all__ = ['RadioDatabase']
