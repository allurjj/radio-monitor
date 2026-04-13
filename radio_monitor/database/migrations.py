"""
Database schema migration functions for Radio Monitor 1.0

This module handles all database migrations:
- Legacy schema → v1 (5-table schema)
- v1 → v2 (add auto_playlists table)
- v2 → v3 (unified playlists: merge manual + auto)
- v3 → v4 (add activity_log table for system events)
- v4 → v5 (add plex_match_failures, notifications, notification_history tables)
- v5 → v6 (fix playlists table: allow NULL interval_minutes)
- v6 → v7 (add minute column to song_plays_daily)
- v7 → v8 (add wait_time column to stations)
- v8 → v9 (add manual_mbid_overrides table)
- v9 → v10 (add ai_playlist_generations table)
- v10 → v11 (remove WTMX support)
- v11 → v12 (add manual playlist support)
- v12 → v13 (add station grouping and sorting)
- v13 → v14 (add blocklist table)
- v14 → v15 (add Various Artists fallback support)
- v15 → v16 (add Plex manual overrides system)
- v16 → v17 (fix NULL artist_mbid values and clean up orphaned artists)
- v17 → v18 (add retry_match_succeeded column)
- v18 → v19 (add spotiflac_downloads table)
- v19 → v20 (add match_key column for duplicate detection)

Migrations are applied automatically when the database is opened.
"""

import sqlite3
import shutil
import logging

logger = logging.getLogger(__name__)

# Import schema functions
from .schema import create_tables, populate_stations, populate_manual_mbid_overrides


def _initialize_schema(cursor, conn, db_path, SCHEMA_VERSION):
    """Initialize schema (create new or migrate from legacy)

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        db_path: Path to database file
        SCHEMA_VERSION: Current schema version (from database module)
    """
    # Check if schema_version table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='schema_version'
    """)

    if not cursor.fetchone():
        # No schema_version table - need to check if this is legacy DB
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='songs'
        """)

        if cursor.fetchone():
            # Legacy database - migrate it
            _migrate_from_legacy(cursor, conn, db_path)
        else:
            # Fresh database - create new schema
            _create_new_schema(cursor, conn, SCHEMA_VERSION)
    else:
        # Schema version table exists - check version
        cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        result = cursor.fetchone()

        if not result or result[0] < SCHEMA_VERSION:
            # Need to upgrade to latest schema version
            current_version = result[0] if result else 0

            # Migrate to version 2 (add auto_playlists table)
            if current_version < 2:
                _migrate_to_v2(cursor, conn)

            # Migrate to version 3 (unified playlists: add is_auto, max_plays, rename table)
            if current_version < 3:
                _migrate_to_v3(cursor, conn)

            # Migrate to version 4 (add activity_log table)
            if current_version < 4:
                _migrate_to_v4(cursor, conn)

            # Migrate to version 5 (add plex_failures, notifications tables)
            if current_version < 5:
                _migrate_to_v5(cursor, conn)

            # Migrate to version 6 (fix playlists table: allow NULL interval_minutes)
            if current_version < 6:
                _migrate_to_v6(cursor, conn)

            # Migrate to version 7 (add minute column to song_plays_daily)
            if current_version < 7:
                _migrate_to_v7(cursor, conn)

            # Migrate to version 8 (add wait_time column to stations)
            if current_version < 8:
                _migrate_to_v8(cursor, conn)

            # Migrate to version 9 (add manual_mbid_overrides table)
            if current_version < 9:
                _migrate_to_v9(cursor, conn)

            # Migrate to version 10 (add ai_playlist_generations table)
            if current_version < 10:
                _migrate_to_v10(cursor, conn)

            # Migrate to version 11 (remove WTMX support)
            if current_version < 11:
                _migrate_to_v11(cursor, conn)

            # Migrate to version 12 (add manual playlist support)
            if current_version < 12:
                _migrate_to_v12(cursor, conn)

            # Migrate to version 13 (add station grouping and sorting)
            if current_version < 13:
                _migrate_to_v13(cursor, conn)

            # Migrate to version 14 (add blocklist table)
            if current_version < 14:
                _migrate_to_v14(cursor, conn)

            # Migrate to version 15 (add Various Artists fallback support)
            if current_version < 15:
                _migrate_to_v15(cursor, conn)

            # Migrate to version 16 (add Plex manual overrides system)
            if current_version < 16:
                _migrate_to_v16(cursor, conn)

            # Migrate to version 17 (fix NULL artist_mbid values and clean up orphaned artists)
            if current_version < 17:
                _migrate_to_v17(cursor, conn)

            # Migrate to version 18 (add retry_match_succeeded column)
            if current_version < 18:
                _migrate_to_v18(cursor, conn)

            # Migrate to version 19 (add spotiflac_downloads table)
            if current_version < 19:
                _migrate_to_v19(cursor, conn)

            # Migrate to version 20 (add match_key column for duplicate detection)
            if current_version < 20:
                _migrate_to_v20(cursor, conn)

            # Migrate to version 21 (add song verification tracking)
            if current_version < 21:
                _migrate_to_v21(cursor, conn)


def _create_new_schema(cursor, conn, SCHEMA_VERSION):
    """Create new schema (6 tables: stations, artists, songs, song_plays_daily, schema_version, playlists)

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        SCHEMA_VERSION: Current schema version
    """
    # Create all tables and indexes
    create_tables(cursor)

    # Populate initial stations
    populate_stations(cursor)

    # Populate manual MBID overrides for difficult-to-match artists
    populate_manual_mbid_overrides(cursor)

    # Record schema version
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (?, ?)
    """, (SCHEMA_VERSION, 'Initial schema with 6 tables (including playlists)'))

    conn.commit()


def _migrate_from_legacy(cursor, conn, db_path):
    """Migrate from legacy single-table schema to new 6-table schema

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
        db_path: Path to database file
    """
    print("Detected legacy database - migrating to new schema...")

    # Backup old database
    backup_path = str(db_path) + "_old.db"
    print(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)

    # Rename old songs table
    cursor.execute("ALTER TABLE songs RENAME TO songs_legacy")

    # Create new schema
    _create_new_schema(cursor, conn, SCHEMA_VERSION=3)

    # Migrate data from legacy table
    print("Migrating existing data...")

    cursor.execute("""
        SELECT DISTINCT station, artist, song, artist_mbid, MIN(first_seen) as first_seen
        FROM songs_legacy
        GROUP BY station, artist, song
    """)

    migrated = 0
    for row in cursor.fetchall():
        station_id, artist_name, song_title, artist_mbid, first_seen = row

        # Note: In legacy schema, we don't have artist MBIDs for most songs
        # They will be looked up in Phase 3
        # For now, create songs with NULL artist_mbid

        try:
            cursor.execute("""
                INSERT INTO songs (artist_mbid, artist_name, song_title, first_seen_at)
                VALUES (?, ?, ?, ?)
            """, (artist_mbid, artist_name, song_title, first_seen))

            # Get the new song_id
            song_id = cursor.lastrowid

            # Migrate play counts to song_plays_daily
            # We'll aggregate all plays to today's date at hour 0
            cursor.execute("""
                SELECT SUM(play_count) as total_plays
                FROM songs_legacy
                WHERE station = ? AND artist = ? AND song = ?
            """, (station_id, artist_name, song_title))

            total_plays = cursor.fetchone()[0] or 0

            if total_plays > 0:
                cursor.execute("""
                    INSERT OR IGNORE INTO song_plays_daily (date, hour, song_id, station_id, play_count)
                    VALUES (DATE('now'), 0, ?, ?, ?)
                """, (song_id, station_id, total_plays))

            migrated += 1
        except Exception as e:
            print(f"  Warning: Failed to migrate {song_title} - {artist_name}: {e}")

    # Update song play_counts
    cursor.execute("""
        UPDATE songs SET play_count = (
            SELECT COALESCE(SUM(play_count), 0)
            FROM song_plays_daily
            WHERE song_plays_daily.song_id = songs.id
        )
    """)

    print(f"Migrated {migrated} songs from legacy database")

    # Drop legacy table (commented out for safety - can be done manually)
    # cursor.execute("DROP TABLE IF EXISTS songs_legacy")

    conn.commit()
    print("Migration complete! Legacy table preserved as 'songs_legacy'")


def _migrate_to_v2(cursor, conn):
    """Migrate database from version 1 to version 2 (add auto_playlists table)

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
    """
    print("Migrating database to version 2 (adding auto_playlists table)...")

    # Create auto_playlists table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auto_playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            interval_minutes INTEGER NOT NULL,
            station_ids TEXT NOT NULL,
            max_songs INTEGER NOT NULL,
            mode TEXT NOT NULL,
            min_plays INTEGER DEFAULT 1,
            days INTEGER,
            enabled BOOLEAN DEFAULT 1,
            last_updated DATETIME,
            next_update DATETIME,
            plex_playlist_name TEXT,
            consecutive_failures INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_auto_playlists_enabled ON auto_playlists(enabled)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_auto_playlists_next_update ON auto_playlists(next_update)")

    # Record schema version
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (?, ?)
    """, (2, 'Add auto_playlists table'))

    conn.commit()
    print("Migration to version 2 complete!")


def _migrate_to_v3(cursor, conn):
    """Migrate database from version 2 to version 3 (unified playlists)

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
    """
    print("Migrating database to version 3 (unified playlists: rename table, add is_auto, max_plays)...")

    # Step 1: Rename auto_playlists table to playlists
    print("  - Renaming auto_playlists -> playlists...")
    cursor.execute("ALTER TABLE auto_playlists RENAME TO playlists")

    # Step 2: Add is_auto column (BOOLEAN, default TRUE - all existing are auto)
    print("  - Adding is_auto column...")
    cursor.execute("ALTER TABLE playlists ADD COLUMN is_auto BOOLEAN DEFAULT 1")

    # Step 3: Add max_plays column (INTEGER, optional)
    print("  - Adding max_plays column...")
    cursor.execute("ALTER TABLE playlists ADD COLUMN max_plays INTEGER")

    # Step 4: Update existing rows (all existing playlists are auto)
    print("  - Updating existing rows...")
    cursor.execute("UPDATE playlists SET is_auto = 1")

    # Step 5: Drop old indexes
    print("  - Dropping old indexes...")
    cursor.execute("DROP INDEX IF EXISTS idx_auto_playlists_enabled")
    cursor.execute("DROP INDEX IF EXISTS idx_auto_playlists_next_update")

    # Step 6: Create new indexes
    print("  - Creating new indexes...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlists_enabled ON playlists(enabled)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlists_next_update ON playlists(next_update)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlists_is_auto ON playlists(is_auto)")

    # Step 7: Record schema version
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (?, ?)
    """, (3, 'Unified playlists: rename auto_playlists->playlists, add is_auto, max_plays'))

    conn.commit()
    print("Migration to version 3 complete!")


def _migrate_to_v4(cursor, conn):
    """Migrate database from version 3 to version 4 (add activity_log table)

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
    """
    print("Migrating database to version 4 (adding activity_log table)...")

    # Step 1: Create activity_log table
    print("  - Creating activity_log table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            event_type TEXT NOT NULL,
            event_severity TEXT DEFAULT 'info',
            title TEXT NOT NULL,
            description TEXT,
            metadata TEXT,
            source TEXT DEFAULT 'system'
        )
    """)

    # Step 2: Create indexes
    print("  - Creating indexes...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON activity_log(timestamp DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_type ON activity_log(event_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_severity ON activity_log(event_severity)")

    # Step 3: Log the migration as an activity
    print("  - Logging migration event...")
    cursor.execute("""
        INSERT INTO activity_log (event_type, event_severity, title, description, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v3 to v4', 'system')
    """)

    # Step 4: Record schema version
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (?, ?)
    """, (4, 'Add activity_log table for system event tracking'))

    conn.commit()
    print("Migration to version 4 complete!")


def _migrate_to_v5(cursor, conn):
    """Migrate database from version 4 to version 5 (add plex_failures and notifications tables)

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
    """
    print("Migrating database to version 5 (adding plex_failures and notifications tables)...")

    # Step 1: Create plex_match_failures table
    print("  - Creating plex_match_failures table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plex_match_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NULL,
            playlist_id INTEGER,
            failure_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            failure_reason TEXT NOT NULL,
            search_attempts INTEGER DEFAULT 1,
            search_terms_used TEXT,
            resolved BOOLEAN DEFAULT 0,
            resolved_at DATETIME,
            FOREIGN KEY (song_id) REFERENCES songs(id),
            FOREIGN KEY (playlist_id) REFERENCES playlists(id)
        )
    """)

    # Step 2: Create indexes for plex_match_failures
    print("  - Creating indexes for plex_match_failures...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_failures_song ON plex_match_failures(song_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_failures_date ON plex_match_failures(failure_date DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_failures_resolved ON plex_match_failures(resolved)")

    # Step 3: Create notifications table
    print("  - Creating notifications table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_type TEXT NOT NULL,
            name TEXT NOT NULL UNIQUE,
            enabled BOOLEAN DEFAULT 1,
            config TEXT NOT NULL,
            triggers TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_triggered DATETIME,
            failure_count INTEGER DEFAULT 0
        )
    """)

    # Step 4: Create indexes for notifications
    print("  - Creating indexes for notifications...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_enabled ON notifications(enabled)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(notification_type)")

    # Step 5: Create notification_history table
    print("  - Creating notification_history table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notification_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_id INTEGER NOT NULL,
            sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            event_type TEXT NOT NULL,
            event_severity TEXT,
            title TEXT,
            message TEXT,
            success BOOLEAN DEFAULT 1,
            error_message TEXT,
            FOREIGN KEY (notification_id) REFERENCES notifications(id)
        )
    """)

    # Step 6: Create indexes for notification_history
    print("  - Creating indexes for notification_history...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_notification ON notification_history(notification_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_sent_at ON notification_history(sent_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_event_type ON notification_history(event_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_success ON notification_history(success)")

    # Step 7: Log the migration as an activity
    print("  - Logging migration event...")
    cursor.execute("""
        INSERT INTO activity_log (event_type, event_severity, title, description, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v4 to v5: added plex_failures and notifications tables', 'system')
    """)

    # Step 8: Record schema version
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (?, ?)
    """, (5, 'Add plex_match_failures, notifications, notification_history tables for Phase 4'))

    conn.commit()
    print("Migration to version 5 complete!")


def _migrate_to_v6(cursor, conn):
    """Migrate database from version 5 to version 6 (fix playlists table: allow NULL interval_minutes)

    This migration fixes the playlists table to allow NULL interval_minutes for manual playlists.
    The original table was created from v2 auto_playlists which had NOT NULL constraint on interval_minutes.

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
    """
    print("Migrating database to version 6 (fixing playlists table to allow NULL interval_minutes)...")

    # Step 1: Create new playlists table with correct schema (interval_minutes can be NULL)
    print("  - Creating new playlists table...")
    cursor.execute("""
        CREATE TABLE playlists_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            is_auto BOOLEAN DEFAULT 1,
            interval_minutes INTEGER,
            station_ids TEXT NOT NULL,
            max_songs INTEGER NOT NULL,
            mode TEXT NOT NULL,
            min_plays INTEGER DEFAULT 1,
            max_plays INTEGER,
            days INTEGER,
            enabled BOOLEAN DEFAULT 1,
            last_updated DATETIME,
            next_update DATETIME,
            plex_playlist_name TEXT,
            consecutive_failures INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Step 2: Copy all data from old table to new table
    print("  - Copying data to new table...")
    cursor.execute("""
        INSERT INTO playlists_new (
            id, name, is_auto, interval_minutes, station_ids, max_songs, mode,
            min_plays, max_plays, days, enabled, last_updated, next_update,
            plex_playlist_name, consecutive_failures, created_at
        )
        SELECT
            id, name, is_auto, interval_minutes, station_ids, max_songs, mode,
            min_plays, max_plays, days, enabled, last_updated, next_update,
            plex_playlist_name, consecutive_failures, created_at
        FROM playlists
    """)

    # Step 3: Drop old table
    print("  - Dropping old playlists table...")
    cursor.execute("DROP TABLE playlists")

    # Step 4: Rename new table to playlists
    print("  - Renaming playlists_new to playlists...")
    cursor.execute("ALTER TABLE playlists_new RENAME TO playlists")

    # Step 5: Recreate indexes
    print("  - Recreating indexes...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlists_enabled ON playlists(enabled)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlists_next_update ON playlists(next_update)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlists_is_auto ON playlists(is_auto)")

    # Step 6: Log the migration as an activity
    print("  - Logging migration event...")
    cursor.execute("""
        INSERT INTO activity_log (event_type, event_severity, title, description, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v5 to v6: fixed playlists table to allow NULL interval_minutes for manual playlists', 'system')
    """)

    # Step 7: Record schema version
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (?, ?)
    """, (6, 'Fix playlists table: allow NULL interval_minutes for manual playlists (Bug #7)'))

    conn.commit()
    print("Migration to version 6 complete!")


def _migrate_to_v7(cursor, conn):
    """Migrate database from version 6 to version 7 (add minute column to song_plays_daily)

    This migration adds minute precision to song_plays_daily table for better duplicate detection.
    Old records: minute is NULL (hour precision only)
    New records: minute is 0-59 (minute precision)

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
    """
    print("Migrating database to version 7 (adding minute column to song_plays_daily)...")

    # Step 1: Add minute column (nullable)
    print("  - Adding minute column...")
    cursor.execute("ALTER TABLE song_plays_daily ADD COLUMN minute INTEGER")

    # Step 2: Log the migration as an activity
    print("  - Logging migration event...")
    cursor.execute("""
        INSERT INTO activity_log (event_type, event_severity, title, description, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v6 to v7: added minute column to song_plays_daily for duplicate detection', 'system')
    """)

    # Step 3: Record schema version
    print("  - Recording schema version...")
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (?, ?)
    """, (7, 'Add minute column to song_plays_daily for duplicate detection (time window deduplication)'))

    conn.commit()
    print("Migration to version 7 complete!")


def _migrate_to_v8(cursor, conn):
    """Migrate database from version 7 to version 8 (add wait_time column to stations)

    This migration adds wait_time column to stations table for database-driven station configs.
    Old stations will get default values based on scraper_type (wtmx=10, iheart=15)

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
    """
    print("Migrating database to version 8 (adding wait_time column to stations)...")

    # Step 1: Add wait_time column (nullable, with default)
    print("  - Adding wait_time column...")
    try:
        cursor.execute("ALTER TABLE stations ADD COLUMN wait_time INTEGER DEFAULT 10")
    except Exception as e:
        # Column might already exist if migration was partially run
        if "duplicate column name" not in str(e).lower():
            raise

    # Step 2: Update existing stations with appropriate wait_time based on scraper_type
    print("  - Updating existing stations with default wait_time values...")
    cursor.execute("""
        UPDATE stations
        SET wait_time = CASE
            WHEN scraper_type = 'wtmx' THEN 10
            ELSE 15
        END
        WHERE wait_time IS NULL OR wait_time = 10
    """)

    # Step 3: Log migration as an activity
    print("  - Logging migration event...")
    cursor.execute("""
        INSERT INTO activity_log (event_type, event_severity, title, description, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v7 to v8: added wait_time column to stations for database-driven scraper config', 'system')
    """)

    # Step 4: Record schema version
    print("  - Recording schema version...")
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (?, ?)
    """, (8, 'Add wait_time column to stations for database-driven station scraper configuration'))

    conn.commit()
    print("Migration to version 8 complete!")


def _migrate_to_v9(cursor, conn):
    """Migrate database from version 8 to version 9 (add manual_mbid_overrides table)

    This migration adds manual_mbid_overrides table to persist user-specified MBID mappings.
    This prevents PENDING entries from being recreated after user manually fixes them.

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
    """
    print("Migrating database to version 9 (adding manual_mbid_overrides table)...")

    # Step 1: Create manual_mbid_overrides table
    print("  - Creating manual_mbid_overrides table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS manual_mbid_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_name_normalized TEXT NOT NULL UNIQUE,
            artist_name_original TEXT NOT NULL,
            mbid TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    """)

    # Step 2: Create indexes
    print("  - Creating indexes...")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_mbid_overrides_name
        ON manual_mbid_overrides(artist_name_normalized)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_mbid_overrides_mbid
        ON manual_mbid_overrides(mbid)
    """)

    # Step 3: Log the migration as an activity
    print("  - Logging migration event...")
    cursor.execute("""
        INSERT INTO activity_log (event_type, event_severity, title, description, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v8 to v9: added manual_mbid_overrides table for persistent MBID fixes', 'system')
    """)

    # Step 4: Record schema version
    print("  - Recording schema version...")
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (?, ?)
    """, (9, 'Add manual_mbid_overrides table for persistent user-specified MBID mappings'))

    conn.commit()
    print("Migration to version 9 complete!")


def _migrate_to_v10(cursor, conn):
    """Migrate database from version 9 to version 10 (add ai_playlist_generations table)

    This migration adds ai_playlist_generations table to track AI playlist generations
    with structured, queryable data. This is better than activity_log for filtering,
    sorting, and analysis of AI playlist generations.

    Args:
        cursor: SQLite cursor object
        conn: SQLite connection object
    """
    print("Migrating database to version 10 (adding ai_playlist_generations table)...")

    # Step 1: Create ai_playlist_generations table
    print("  - Creating ai_playlist_generations table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_playlist_generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            playlist_name TEXT NOT NULL,
            model TEXT NOT NULL,
            instructions TEXT,
            filters_json TEXT,
            status TEXT NOT NULL,
            songs_requested INTEGER,
            songs_returned INTEGER,
            songs_added_to_plex INTEGER,
            songs_skipped INTEGER,
            songs_hallucinated INTEGER DEFAULT 0,
            error_message TEXT,
            plex_url TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Step 2: Create indexes
    print("  - Creating indexes...")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ai_gen_timestamp
        ON ai_playlist_generations(timestamp DESC)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ai_gen_status
        ON ai_playlist_generations(status)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ai_gen_playlist_name
        ON ai_playlist_generations(playlist_name)
    """)

    # Step 3: Log the migration as an activity
    print("  - Logging migration event...")
    cursor.execute("""
        INSERT INTO activity_log (event_type, event_severity, title, description, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v9 to v10: added ai_playlist_generations table for AI playlist tracking', 'system')
    """)

    # Step 4: Record schema version
    print("  - Recording schema version...")
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (?, ?)
    """, (10, 'Add ai_playlist_generations table for AI playlist tracking with structured data'))

    conn.commit()


def _migrate_to_v11(cursor, conn):
    """Migrate database from v10 to v11

    Changes:
    - Disable WTMX station (if exists)
    - Validate all stations are iHeartRadio type
    - Update schema version

    Args:
        cursor: Database cursor
        conn: Database connection
    """
    print("Migrating database from v10 to v11...")

    # Step 1: Disable or delete WTMX station if it exists
    cursor.execute("""
        SELECT id FROM stations WHERE id = 'wtmx'
    """)

    wtmx_exists = cursor.fetchone()

    if wtmx_exists:
        print("  - Disabling WTMX station (Selenium dependency removed in v1.1.0)...")
        cursor.execute("""
            UPDATE stations
            SET enabled = 0
            WHERE id = 'wtmx'
        """)

        # Also add a note to the station name
        cursor.execute("""
            UPDATE stations
            SET name = name || ' [DISABLED - Selenium removed in v1.1.0]'
            WHERE id = 'wtmx'
        """)

    # Step 2: Validate all enabled stations are iHeartRadio type
    cursor.execute("""
        SELECT id, scraper_type FROM stations WHERE enabled = 1
    """)

    invalid_stations = []
    for station_id, scraper_type in cursor.fetchall():
        if scraper_type != 'iheart':
            invalid_stations.append((station_id, scraper_type))

    if invalid_stations:
        print(f"  - Found {len(invalid_stations)} stations with unsupported scraper_type:")
        for station_id, scraper_type in invalid_stations:
            print(f"    - {station_id} (type: {scraper_type})")
            # Disable these stations
            cursor.execute("""
                UPDATE stations
                SET enabled = 0
                WHERE id = ?
            """, (station_id,))

    # Step 3: Log the migration as an activity
    print("  - Logging migration event...")
    cursor.execute("""
        INSERT INTO activity_log (event_type, event_severity, title, description, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v10 to v11: disabled WTMX station (Selenium dependency removed)', 'system')
    """)

    # Step 4: Update schema version
    print("  - Recording schema version...")
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (?, ?)
    """, (11, 'Remove WTMX station support (Selenium dependency removed in v1.1.0)'))

    conn.commit()
    print("  - Migration to v11 complete")
    print("Migration to version 11 complete!")


def _migrate_to_v12(cursor, conn):
    """Migrate database from v11 to v12 (add manual playlist support)

    This migration adds three new tables to support manual playlist creation:
    - manual_playlists: Stores manual playlist metadata
    - manual_playlist_songs: Junction table for playlist-song relationships
    - playlist_builder_state: Temporary storage for in-progress playlist building

    Args:
        cursor: Database cursor
        conn: Database connection
    """
    print("Migrating database from v11 to v12 (adding manual playlist support)...")

    # Step 1: Create manual_playlists table
    print("  - Creating manual_playlists table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS manual_playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            plex_playlist_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Step 2: Create indexes for manual_playlists
    print("  - Creating indexes for manual_playlists...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_playlists_name ON manual_playlists(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_playlists_created ON manual_playlists(created_at)")

    # Step 3: Create manual_playlist_songs table
    print("  - Creating manual_playlist_songs table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS manual_playlist_songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manual_playlist_id INTEGER NOT NULL,
            song_id INTEGER NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (manual_playlist_id) REFERENCES manual_playlists(id) ON DELETE CASCADE,
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
            UNIQUE(manual_playlist_id, song_id)
        )
    """)

    # Step 4: Create indexes for manual_playlist_songs
    print("  - Creating indexes for manual_playlist_songs...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_playlist_songs_playlist ON manual_playlist_songs(manual_playlist_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_playlist_songs_song ON manual_playlist_songs(song_id)")

    # Step 5: Create playlist_builder_state table
    print("  - Creating playlist_builder_state table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlist_builder_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            song_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
            UNIQUE(session_id, song_id)
        )
    """)

    # Step 6: Create indexes for playlist_builder_state
    print("  - Creating indexes for playlist_builder_state...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlist_builder_state_session ON playlist_builder_state(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlist_builder_state_song ON playlist_builder_state(song_id)")

    # Step 7: Log the migration as an activity
    print("  - Logging migration event...")
    cursor.execute("""
        INSERT INTO activity_log (event_type, event_severity, title, description, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v11 to v12: added manual playlist support (manual_playlists, manual_playlist_songs, playlist_builder_state tables)', 'system')
    """)

    # Step 8: Record schema version
    print("  - Recording schema version...")
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (?, ?)
    """, (12, 'Add manual playlist support: manual_playlists, manual_playlist_songs, playlist_builder_state tables'))

    conn.commit()
    print("  - Migration to v12 complete")
    print("Migration to version 12 complete!")


def _migrate_to_v13(cursor, conn):
    """Migrate database from v12 to v13 (add station sorting)

    This migration adds a sort_order field to the stations table
    and populates the stations table with all 28 default stations.

    Args:
        cursor: Database cursor
        conn: Database connection
    """
    print("Migrating database from v12 to v13 (adding station sorting)...")

    # Step 1: Add sort_order column
    print("  - Adding sort_order column...")
    try:
        cursor.execute("ALTER TABLE stations ADD COLUMN sort_order INTEGER DEFAULT 0")
    except Exception as e:
        if "duplicate column name" in str(e).lower():
            print("    - Column sort_order already exists, skipping...")
        else:
            raise

    # Step 2: Populate/Update stations with all 28 default stations
    print("  - Populating stations with all 28 default stations...")
    from .schema import populate_stations
    populate_stations(cursor)

    # Step 3: Log the migration as an activity
    print("  - Logging migration event...")
    cursor.execute("""
        INSERT INTO activity_log (event_type, event_severity, title, description, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v12 to v13: added sort_order field and populated 28 default stations (alphabetically sorted)', 'system')
    """)

    # Step 4: Record schema version
    print("  - Recording schema version...")
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (?, ?)
    """, (13, 'Add station sorting: sort_order field + 28 default stations'))

    conn.commit()
    print("Migration to version 13 complete!")


def _migrate_to_v14(cursor, conn):
    """Migrate database from v13 to v14 (add blocklist table)

    This migration adds the blocklist table to support blocking artists and songs
    from playlist generation. Users can block individual songs or all songs by an artist.

    Args:
        cursor: Database cursor
        conn: Database connection
    """
    print("Migrating database from v13 to v14 (adding blocklist support)...")

    # Step 1: Create blocklist table
    print("  - Creating blocklist table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blocklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL CHECK(entity_type IN ('artist', 'song')),
            entity_id TEXT NOT NULL,
            artist_mbid TEXT,
            song_id INTEGER,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT DEFAULT 'user',
            FOREIGN KEY (artist_mbid) REFERENCES artists(mbid) ON DELETE CASCADE,
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
            UNIQUE(entity_type, entity_id)
        )
    """)

    # Step 2: Create indexes
    print("  - Creating indexes...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocklist_entity_type ON blocklist(entity_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocklist_artist_mbid ON blocklist(artist_mbid)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocklist_song_id ON blocklist(song_id)")

    # Step 3: Log the migration as an activity
    print("  - Logging migration event...")
    cursor.execute("""
        INSERT INTO activity_log (event_type, event_severity, title, description, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v13 to v14: added blocklist table for blocking artists/songs from playlists', 'system')
    """)

    # Step 4: Record schema version
    print("  - Recording schema version...")
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (?, ?)
    """, (14, 'Add blocklist table for blocking artists/songs from playlist generation'))

    conn.commit()
    print("Migration to version 14 complete!")


def _migrate_to_v15(cursor, conn):
    """Migrate database from v14 to v15 (add Various Artists fallback support)

    This migration adds Various Artists fallback support to both automatic and manual playlists.
    Users can opt-in to scan 'Various Artists' compilation albums in Plex when standard
    matching strategies fail, with a configurable per-song timeout to prevent runaway searches.

    Args:
        cursor: Database cursor
        conn: Database connection
    """
    print("Migrating database from v14 to v15 (adding Various Artists fallback support)...")

    # Step 1: Add columns to playlists table (automatic playlists)
    print("  - Adding columns to playlists table...")
    try:
        cursor.execute("ALTER TABLE playlists ADD COLUMN enable_various_artists_fallback BOOLEAN DEFAULT 0")
        print("    - Added enable_various_artists_fallback to playlists")
    except sqlite3.OperationalError:
        print("    - enable_various_artists_fallback already exists in playlists (skipping)")

    try:
        cursor.execute("ALTER TABLE playlists ADD COLUMN various_artists_timeout_ms INTEGER DEFAULT 5000")
        print("    - Added various_artists_timeout_ms to playlists")
    except sqlite3.OperationalError:
        print("    - various_artists_timeout_ms already exists in playlists (skipping)")

    # Step 2: Add columns to manual_playlists table (manual playlists)
    print("  - Adding columns to manual_playlists table...")
    try:
        cursor.execute("ALTER TABLE manual_playlists ADD COLUMN enable_various_artists_fallback BOOLEAN DEFAULT 0")
        print("    - Added enable_various_artists_fallback to manual_playlists")
    except sqlite3.OperationalError:
        print("    - enable_various_artists_fallback already exists in manual_playlists (skipping)")

    try:
        cursor.execute("ALTER TABLE manual_playlists ADD COLUMN various_artists_timeout_ms INTEGER DEFAULT 5000")
        print("    - Added various_artists_timeout_ms to manual_playlists")
    except sqlite3.OperationalError:
        print("    - various_artists_timeout_ms already exists in manual_playlists (skipping)")

    # Step 3: Log the migration as an activity
    print("  - Logging migration event...")
    cursor.execute("""
        INSERT INTO activity_log (event_type, event_severity, title, description, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v14 to v15: added Various Artists fallback support to playlists and manual_playlists tables', 'system')
    """)

    # Step 4: Record schema version
    print("  - Recording schema version...")
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (?, ?)
    """, (15, 'Add Various Artists fallback support to playlists and manual_playlists: enable_various_artists_fallback, various_artists_timeout_ms'))

    conn.commit()
    print("Migration to version 15 complete!")


def _migrate_to_v16(cursor, conn):
    """Migrate database from v15 to v16 (add Plex manual overrides system)

    This migration adds a user manual override system for Plex song matching.
    Users can manually map failed Plex matches to correct tracks for 100% reliability.

    Args:
        cursor: Database cursor
        conn: Database connection
    """
    print("Migrating database from v15 to v16 (adding Plex manual overrides system)...")

    # Step 1: Create plex_manual_overrides table
    print("  - Creating plex_manual_overrides table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plex_manual_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NULL,
            plex_track_key TEXT NOT NULL,
            plex_track_title TEXT NOT NULL,
            plex_artist_name TEXT NOT NULL,
            plex_album_title TEXT,
            plex_year INTEGER,
            plex_duration_ms INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            notes TEXT,
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
            UNIQUE(song_id, plex_track_key)
        )
    """)

    # Step 2: Create indexes
    print("  - Creating indexes...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plex_overrides_song_id ON plex_manual_overrides(song_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plex_overrides_plex_key ON plex_manual_overrides(plex_track_key)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plex_overrides_active ON plex_manual_overrides(is_active)")

    # Step 3: Log the migration as an activity
    print("  - Logging migration event...")
    cursor.execute("""
        INSERT INTO activity_log (event_type, event_severity, title, description, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v15 to v16: added plex_manual_overrides table for manual Plex track matching', 'system')
    """)

    # Step 4: Record schema version
    print("  - Recording schema version...")
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (?, ?)
    """, (16, 'Add Plex manual overrides system: plex_manual_overrides table with user-specified Plex track mappings'))

    conn.commit()
    print("Migration to version 16 complete!")


def _migrate_to_v17(cursor, conn):
    """Migrate database from v16 to v17 (fix NULL artist_mbid values and clean up orphaned artists)

    This migration fixes critical issues:
    1. Songs with NULL artist_mbid cause crashes when linking to artist detail pages
    2. Orphaned artists (0 songs) clutter the database and can't be deleted
    3. Existing NULL mbids in artists table cause startswith() crashes

    Strategy:
    - Find all songs with NULL artist_mbid
    - For each song, try to match artist_name to existing artists
    - If no match, create PENDING artist
    - Delete orphaned artists (0 songs)
    """
    import uuid
    from radio_monitor.normalization import normalize_artist_name

    print("Migrating from schema v16 to v17...")
    print("  - Fixing NULL artist_mbid values and cleaning up orphaned artists...")

    # Step 1: Find all songs with NULL artist_mbid
    print("  - Finding songs with NULL artist_mbid...")
    cursor.execute("""
        SELECT id, song_title, artist_name
        FROM songs
        WHERE artist_mbid IS NULL
    """)
    null_songs = cursor.fetchall()

    if not null_songs:
        print("  - No songs with NULL artist_mbid found (good!)")
    else:
        print(f"  - Found {len(null_songs)} songs with NULL artist_mbid, fixing...")

        # Step 2: For each song, try to find matching artist
        for song_id, song_title, artist_name in null_songs:
            if not artist_name:
                # No artist name either, create generic PENDING artist
                pending_mbid = f"PENDING-{uuid.uuid4()}"
                cursor.execute("""
                    INSERT INTO artists (mbid, name, first_seen_at, last_seen_at, needs_lidarr_import)
                    VALUES (?, ?, datetime('now'), datetime('now'), 1)
                """, (pending_mbid, "Unknown Artist"))
                cursor.execute("UPDATE songs SET artist_mbid = ? WHERE id = ?", (pending_mbid, song_id))
                print(f"    - Created 'Unknown Artist' for song: {song_title}")
                continue

            # Try to find existing artist by name (case-insensitive)
            normalized_name = normalize_artist_name(artist_name)
            cursor.execute("SELECT mbid FROM artists WHERE name = ? COLLATE NOCASE", (normalized_name,))
            result = cursor.fetchone()

            if result:
                # Found matching artist, use it
                cursor.execute("UPDATE songs SET artist_mbid = ? WHERE id = ?", (result[0], song_id))
                print(f"    - Matched '{artist_name}' to existing MBID: {result[0]}")
            else:
                # No matching artist, create PENDING artist
                pending_mbid = f"PENDING-{uuid.uuid4()}"
                cursor.execute("""
                    INSERT INTO artists (mbid, name, first_seen_at, last_seen_at, needs_lidarr_import)
                    VALUES (?, ?, datetime('now'), datetime('now'), 1)
                """, (pending_mbid, normalized_name))
                cursor.execute("UPDATE songs SET artist_mbid = ? WHERE id = ?", (pending_mbid, song_id))
                print(f"    - Created PENDING artist for '{artist_name}'")

    # Step 3: Clean up orphaned artists (0 songs)
    print("  - Cleaning up orphaned artists (0 songs)...")
    cursor.execute("""
        SELECT mbid, name FROM artists
        WHERE mbid NOT IN (SELECT DISTINCT artist_mbid FROM songs WHERE artist_mbid IS NOT NULL)
    """)
    orphaned_artists = cursor.fetchall()

    if orphaned_artists:
        print(f"  - Found {len(orphaned_artists)} orphaned artists, deleting...")
        for mbid, name in orphaned_artists:
            print(f"    - Deleting orphaned artist: {name} ({mbid})")

        cursor.execute("""
            DELETE FROM artists
            WHERE mbid NOT IN (SELECT DISTINCT artist_mbid FROM songs WHERE artist_mbid IS NOT NULL)
        """)
        print(f"  - Deleted {cursor.rowcount} orphaned artists")
    else:
        print("  - No orphaned artists found (good!)")

    # Step 4: Fix any remaining NULL mbids in artists table
    print("  - Fixing NULL mbids in artists table...")
    cursor.execute("SELECT COUNT(*) FROM artists WHERE mbid IS NULL")
    null_artist_count = cursor.fetchone()[0]

    if null_artist_count > 0:
        print(f"  - Found {null_artist_count} artists with NULL mbid, fixing...")
        cursor.execute("""
            UPDATE artists
            SET mbid = 'PENDING-' || lower(hex(randomblob(16)))
            WHERE mbid IS NULL
        """)
        print(f"  - Fixed {cursor.rowcount} NULL mbids in artists table")
    else:
        print("  - No NULL mbids in artists table (good!)")

    # Step 5: Record schema version
    print("  - Recording schema version...")
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (?, ?)
    """, (17, 'Fix NULL artist_mbid values and clean up orphaned artists: all songs now have valid artist_mbids, orphaned artists removed'))

    # Step 6: Log migration completion
    cursor.execute("""
        INSERT INTO activity_log (event_type, title, description, event_severity, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v16 to v17: fixed NULL artist_mbid values, removed orphaned artists', 'system')
    """)

    conn.commit()
    print("Migration to version 17 complete!")


def _migrate_to_v18(cursor, conn):
    """Migrate database from v17 to v18 (add retry_match_succeeded column)

    This migration adds tracking for retry match success status:
    - retry_match_succeeded column to plex_match_failures table
    - Tracks whether manual retry attempts succeeded (TRUE), failed (FALSE), or not yet tried (NULL)
    """
    from pathlib import Path

    print("Migrating from schema v17 to v18...")
    print("  - Adding retry_match_succeeded column to plex_match_failures table...")

    # Execute migration SQL
    migration_file = Path(__file__).parent / 'migrations' / 'migrate_v17_to_v18.sql'
    with open(migration_file, 'r') as f:
        sql = f.read()

    cursor.executescript(sql)

    print("  - Added retry_match_succeeded column")

    # Log migration completion
    cursor.execute("""
        INSERT INTO activity_log (event_type, title, description, event_severity, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v17 to v18: added retry_match_succeeded column for tracking Plex retry attempts', 'system')
    """)

    conn.commit()
    print("Migration to version 18 complete!")


def _migrate_to_v19(cursor, conn):
    """Migrate database from v17 to v18 (add spotiflac_downloads table)

    This migration adds tracking for SpotiFLAC download jobs:
    - spotiflac_downloads table with job tracking
    - Links to plex_match_failures for download context
    - Tracks download status, service used, file paths
    """
    from pathlib import Path

    print("Migrating from schema v18 to v19...")
    print("  - Adding spotiflac_downloads table...")

    # Execute migration SQL
    migration_file = Path(__file__).parent / 'migrations' / 'migrate_v18_to_v19.sql'
    with open(migration_file, 'r') as f:
        sql = f.read()

    cursor.executescript(sql)

    print("  - Added spotiflac_downloads table")

    # Log migration completion
    cursor.execute("""
        INSERT INTO activity_log (event_type, title, description, event_severity, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v18 to v19: added spotiflac_downloads table for tracking SpotiFLAC download jobs', 'system')
    """)

    conn.commit()
    print("Migration to version 19 complete!")


def _migrate_to_v20(cursor, conn):
    """Migrate database from v19 to v20 (add match_key column)

    This migration adds aggressive normalization for duplicate detection:
    - match_key column to artists table
    - Backfills existing artists with match_key values
    - Creates index for fast duplicate detection
    """
    from pathlib import Path

    print("Migrating from schema v19 to v20...")
    print("  - Adding match_key column for duplicate detection...")

    # Check if match_key column already exists (for fresh databases)
    cursor.execute("PRAGMA table_info(artists)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]

    if 'match_key' not in column_names:
        # Add the column for existing v19 databases
        print("  - Adding match_key column to existing table...")
        cursor.execute("ALTER TABLE artists ADD COLUMN match_key TEXT")
    else:
        print("  - match_key column already exists (fresh database)")

    # Backfill existing artists with match_key (safe for both cases)
    print("  - Backfilling match_key for existing artists...")

    # Use a parameterized approach to avoid apostrophe escaping issues
    # Step 1: Lowercase and remove spaces, ampersands, plus signs, commas, periods, hyphens
    cursor.execute("""
        UPDATE artists SET match_key = LOWER(name)
        WHERE match_key IS NULL
    """)
    cursor.execute("UPDATE artists SET match_key = REPLACE(match_key, ' ', '') WHERE match_key IS NOT NULL")
    cursor.execute("UPDATE artists SET match_key = REPLACE(match_key, '&', '') WHERE match_key IS NOT NULL")
    cursor.execute("UPDATE artists SET match_key = REPLACE(match_key, '+', '') WHERE match_key IS NOT NULL")
    cursor.execute("UPDATE artists SET match_key = REPLACE(match_key, ',', '') WHERE match_key IS NOT NULL")
    cursor.execute("UPDATE artists SET match_key = REPLACE(match_key, '.', '') WHERE match_key IS NOT NULL")
    cursor.execute("UPDATE artists SET match_key = REPLACE(match_key, '-', '') WHERE match_key IS NOT NULL")
    cursor.execute("UPDATE artists SET match_key = REPLACE(match_key, char(39), '') WHERE match_key IS NOT NULL")

    # Remove "the" prefix
    cursor.execute("UPDATE artists SET match_key = SUBSTR(match_key, 4) WHERE match_key LIKE 'the%'")

    # Create index
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_artists_match_key ON artists(match_key)")

    # Update schema version
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (20, 'Add match_key column for aggressive duplicate detection')
    """)

    print("  - Added match_key column and index")

    # Log migration completion
    cursor.execute("""
        INSERT INTO activity_log (event_type, title, description, event_severity, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v19 to v20: added match_key column for aggressive duplicate detection', 'system')
    """)

    conn.commit()
    print("Migration to version 20 complete!")


def _migrate_to_v21(cursor, conn):
    """Migrate database from v20 to v21 (add song verification tracking)

    This migration adds MusicBrainz + Lidarr verification support:
    - verification_status column to songs table (VERIFIED_MB, VERIFIED_LIDARR, NOT_FOUND, UNVERIFIED)
    - verification_date column to songs table (timestamp of last verification)
    - artist_song_verification table for tracking verification details
    """
    print("Migrating from schema v20 to v21...")
    print("  - Adding song verification tracking...")

    # Check if verification_status column already exists (for fresh databases)
    cursor.execute("PRAGMA table_info(songs)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]

    if 'verification_status' not in column_names:
        # Add the columns for existing v20 databases
        print("  - Adding verification columns to existing table...")
        cursor.execute("ALTER TABLE songs ADD COLUMN verification_status TEXT DEFAULT 'UNVERIFIED'")
        cursor.execute("ALTER TABLE songs ADD COLUMN verification_date TIMESTAMP")
    else:
        print("  - verification columns already exist (fresh database)")

    # Create artist_song_verification table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS artist_song_verification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NULL,
            verification_source TEXT NOT NULL,
            is_verified BOOLEAN NOT NULL,
            metadata_json TEXT,
            verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
        )
    """)

    # Create index for fast lookup
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_verification_song_id ON artist_song_verification(song_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_verification_source ON artist_song_verification(verification_source)")

    # Update schema version
    cursor.execute("""
        INSERT INTO schema_version (version, description)
        VALUES (21, 'Add song verification tracking (MusicBrainz + Lidarr)')
    """)

    print("  - Added verification columns and artist_song_verification table")

    # Log migration completion
    cursor.execute("""
        INSERT INTO activity_log (event_type, title, description, event_severity, source)
        VALUES ('system', 'success', 'Database Migration', 'Migrated from schema v20 to v21: added song verification tracking for MusicBrainz + Lidarr', 'system')
    """)

    conn.commit()
    print("Migration to version 21 complete!")
