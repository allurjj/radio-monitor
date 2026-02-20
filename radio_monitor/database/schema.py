"""
Database schema definitions for Radio Monitor 1.0

This module contains all CREATE TABLE statements and indexes for the
12-table SQLite schema.

Tables:
- stations: Radio station metadata
- artists: Artist information (MBID as primary key)
- songs: Song catalog
- song_plays_daily: Daily play tracking
- schema_version: Schema version tracking
- playlists: Unified playlists (manual + auto)
- activity_log: System activity and event tracking
- plex_match_failures: Plex matching failure tracking (v5)
- notifications: Notification configurations (v5)
- notification_history: Notification send history (v5)
- manual_mbid_overrides: User-specified MBID mappings (v9)
- ai_playlist_generations: AI playlist generation tracking (v10)

Schema Version: 10
"""

import logging

logger = logging.getLogger(__name__)


def create_tables(cursor):
    """Create all 6 tables and indexes

    Args:
        cursor: SQLite cursor object
    """
    # 1. stations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            genre TEXT,
            market TEXT,
            has_mbid BOOLEAN DEFAULT 0,
            scraper_type TEXT DEFAULT 'iheart',
            wait_time INTEGER DEFAULT 10,
            enabled BOOLEAN DEFAULT 1,
            consecutive_failures INTEGER DEFAULT 0,
            last_failure_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stations_enabled ON stations(enabled)")

    # 2. artists table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS artists (
            mbid TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            first_seen_station TEXT,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            needs_lidarr_import BOOLEAN DEFAULT 1,
            lidarr_imported_at TIMESTAMP,
            FOREIGN KEY (first_seen_station) REFERENCES stations(id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_artists_name ON artists(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_artists_needs_import ON artists(needs_lidarr_import) WHERE needs_lidarr_import = 1")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_artists_last_seen ON artists(last_seen_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_artists_first_seen ON artists(first_seen_at DESC)")

    # 3. songs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_mbid TEXT,
            artist_name TEXT NOT NULL,
            song_title TEXT NOT NULL,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            play_count INTEGER DEFAULT 1,
            FOREIGN KEY (artist_mbid) REFERENCES artists(mbid),
            UNIQUE(artist_mbid, song_title)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_songs_play_count ON songs(play_count DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_songs_last_seen ON songs(last_seen_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_songs_first_seen ON songs(first_seen_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_songs_artist_title ON songs(artist_name, song_title)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_songs_artist_name ON songs(artist_name)")

    # 4. song_plays_daily table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS song_plays_daily (
            date DATE NOT NULL,
            hour INTEGER NOT NULL,
            minute INTEGER,
            song_id INTEGER NOT NULL,
            station_id TEXT NOT NULL,
            play_count INTEGER DEFAULT 1,
            PRIMARY KEY (date, hour, song_id, station_id),
            FOREIGN KEY (song_id) REFERENCES songs(id),
            FOREIGN KEY (station_id) REFERENCES stations(id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plays_date ON song_plays_daily(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plays_song_station ON song_plays_daily(song_id, station_id, date)")

    # 5. schema_version table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        )
    """)

    # 6. playlists table (unified: manual + auto)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlists (
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

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlists_enabled ON playlists(enabled)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlists_next_update ON playlists(next_update)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlists_is_auto ON playlists(is_auto)")

    # 7. activity_log table (v4)
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

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON activity_log(timestamp DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_type ON activity_log(event_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_severity ON activity_log(event_severity)")

    # 8. plex_match_failures table (v5)
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

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_failures_song ON plex_match_failures(song_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_failures_date ON plex_match_failures(failure_date DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_failures_resolved ON plex_match_failures(resolved)")

    # 9. notifications table (v5)
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

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_enabled ON notifications(enabled)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(notification_type)")

    # 10. notification_history table (v5)
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

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_notification ON notification_history(notification_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_sent_at ON notification_history(sent_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_event_type ON notification_history(event_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_success ON notification_history(success)")

    # 11. manual_mbid_overrides table (v9)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS manual_mbid_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_name_normalized TEXT NOT NULL UNIQUE,
            artist_name_original TEXT NOT NULL,
            mbid TEXT NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_overrides_normalized ON manual_mbid_overrides(artist_name_normalized)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_overrides_mbid ON manual_mbid_overrides(mbid)")

    # 12. ai_playlist_generations table (v10)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_playlist_generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instructions TEXT NOT NULL,
            station_ids TEXT,
            min_plays INTEGER DEFAULT 1,
            date_range_days INTEGER,
            max_songs INTEGER DEFAULT 50,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            song_count INTEGER DEFAULT 0,
            hallucinated_count INTEGER DEFAULT 0,
            songs_json TEXT NOT NULL,
            plex_playlist_name TEXT,
            model_used TEXT,
            status TEXT DEFAULT 'completed'
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_generations_created_at ON ai_playlist_generations(generated_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_generations_status ON ai_playlist_generations(status)")


def populate_stations(cursor):
    """Populate stations table with initial 12 stations

    Includes 8 Chicago stations + 4 additional iHeartRadio stations

    Args:
        cursor: SQLite cursor object
    """
    stations = [
        # Chicago stations (8)
        ('wtmx', 'WTMX 101.9fm Chicago', 'https://wtmx.com/listen/', 'Pop', 'Chicago', 1, 'wtmx', 10),
        ('us99', 'US99 99.5fm Chicago', 'https://www.iheart.com/live/us-99-10819/', 'Country', 'Chicago', 0, 'iheart', 15),
        ('wls', '94.7 WLS Chicago', 'https://www.iheart.com/live/947-wls-5367/', 'Classic Hits', 'Chicago', 0, 'iheart', 15),
        ('rock955', 'Rock 95.5 Chicago', 'https://www.iheart.com/live/rock-955-857/', 'Rock', 'Chicago', 0, 'iheart', 15),
        ('q101', 'Q101 Chicago', 'https://www.iheart.com/live/q101-6468/', 'Alternative', 'Chicago', 0, 'iheart', 15),
        ('b96', 'B96 Chicago', 'https://www.iheart.com/live/b96-353/', 'Urban/Pop', 'Chicago', 0, 'iheart', 15),
        ('wlite', '93.9 LITE fm Chicago', 'https://www.iheart.com/live/939-lite-fm-853/', 'Adult Contemporary', 'Chicago', 0, 'iheart', 15),
        ('wiil', '95 WIIL ROCK Chicago', 'https://www.iheart.com/live/95-wiil-rock-7716/', 'Rock', 'Chicago', 0, 'iheart', 15),
        # Additional iHeartRadio stations (4)
        ('big955', 'Big 95.5', 'https://www.iheart.com/live/big-955-8731', 'Country', 'Chicago', 0, 'iheart', 10),
        ('iheart70s', 'iHeart70s', 'https://www.iheart.com/live/iheart70s-6843', 'Other', 'USA', 0, 'iheart', 10),
        ('iheart80s', 'iHeart80s', 'https://www.iheart.com/live/iheart80s-5060', 'Other', 'USA', 0, 'iheart', 10),
        ('iheart90s', 'iHeart90s', 'https://www.iheart.com/live/iheart90s-6834', 'Other', 'USA', 0, 'iheart', 10),
    ]

    for station in stations:
        cursor.execute("""
            INSERT OR IGNORE INTO stations (id, name, url, genre, market, has_mbid, scraper_type, wait_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, station)
