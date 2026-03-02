"""
Database schema definitions for Radio Monitor 1.0

This module contains all CREATE TABLE statements and indexes for the
16-table SQLite schema.

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
- manual_playlists: Manual playlist definitions (v12)
- manual_playlist_songs: Manual playlist song associations (v12)
- playlist_builder_state: In-progress playlist builder state (v12)
- blocklist: Blocked artists and songs (v14)

Schema Version: 14
"""

import logging

logger = logging.getLogger(__name__)


def create_tables(cursor):
    """Create all 16 tables and indexes

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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sort_order INTEGER DEFAULT 0
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

    # 13. manual_playlists table (v12)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS manual_playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            plex_playlist_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_playlists_name ON manual_playlists(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_playlists_created ON manual_playlists(created_at)")

    # 14. manual_playlist_songs table (v12)
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

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_playlist_songs_playlist ON manual_playlist_songs(manual_playlist_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_playlist_songs_song ON manual_playlist_songs(song_id)")

    # 15. playlist_builder_state table (v12)
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

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlist_builder_state_session ON playlist_builder_state(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlist_builder_state_song ON playlist_builder_state(song_id)")

    # 16. blocklist table (v14)
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

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocklist_entity_type ON blocklist(entity_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocklist_artist_mbid ON blocklist(artist_mbid)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocklist_song_id ON blocklist(song_id)")


def populate_stations(cursor):
    """Populate stations table with initial 28 stations (alphabetical by name)

    Args:
        cursor: SQLite cursor object
    """
    stations = [
        # All 28 stations sorted alphabetically by name
        ('b96', 'B96 Chicago', 'https://www.iheart.com/live/b96-353/', 'Urban/Pop', 'Chicago', 0, 'iheart', 15, 0),
        ('big955', 'Big 95.5', 'https://www.iheart.com/live/big-955-8731', 'Country', 'Chicago', 0, 'iheart', 10, 0),
        ('fm1061', 'FM106.1', 'https://www.iheart.com/live/fm1061-2677', 'Country', 'Milwaukee', 0, 'iheart', 10, 0),
        ('iheart2000s', 'iHeart2000s', 'https://www.iheart.com/live/iheart2000s-6850', '2000s', 'USA', 0, 'iheart', 10, 0),
        ('iheart2010s', 'iHeart2010s', 'https://www.iheart.com/live/iheart2010s-8478', '2010s', 'USA', 0, 'iheart', 10, 0),
        ('iheart2020s', 'iHeart2020s', 'https://www.iheart.com/live/iheart2020s-10765', '2020s', 'USA', 0, 'iheart', 10, 0),
        ('iheart70s', 'iHeart70s', 'https://www.iheart.com/live/iheart70s-6843', '70s', 'USA', 0, 'iheart', 10, 0),
        ('iheart80s', 'iHeart80s', 'https://www.iheart.com/live/iheart80s-5060', '80s', 'USA', 0, 'iheart', 10, 0),
        ('iheart90s', 'iHeart90s', 'https://www.iheart.com/live/iheart90s-6834', '90s', 'USA', 0, 'iheart', 10, 0),
        ('iheartclassicrock', 'iHeart Classic Rock', 'https://www.iheart.com/live/classic-rock-4426', 'Rock', 'USA', 0, 'iheart', 10, 0),
        ('iheartcountry', 'iHeartCountry', 'https://www.iheart.com/live/iheartcountry-4418', 'Country', 'USA', 0, 'iheart', 10, 0),
        ('iheartcountry2000s', 'iHeartCountry 2000s', 'https://www.iheart.com/live/iheartcountry-2000s-10027', 'Country', 'USA', 0, 'iheart', 10, 0),
        ('iheartcountry80s', 'iHeartCountry 80s', 'https://www.iheart.com/live/iheartcountry-80s-6836', 'Country', 'USA', 0, 'iheart', 10, 0),
        ('iheartcountry90s', 'iHeartCountry 90s', 'https://www.iheart.com/live/iheartcountry-90s-6870', 'Country', 'USA', 0, 'iheart', 10, 0),
        ('iheartcountryclassics', 'iHeartCountry Classics', 'https://www.iheart.com/live/iheartcountry-classics-4435', 'Country', 'USA', 0, 'iheart', 10, 0),
        ('iheartcountryfavorites', 'iHeartCountry Favorites', 'https://www.iheart.com/live/iheartcountry-favorites-8625', 'Country', 'USA', 0, 'iheart', 10, 0),
        ('iheartcountrytop30', 'iHeart  Country Top 30 Bobby Bones', 'https://www.iheart.com/live/country-top-30-6760', 'Country', 'USA', 0, 'iheart', 10, 0),
        ('iheartliterock', 'iHeart Lite Rock', 'https://www.iheart.com/live/lite-rock-6830', 'Rock', 'USA', 0, 'iheart', 10, 0),
        ('iheartnewcountry', 'iHeart New Country', 'https://www.iheart.com/live/new-country-4712', 'Country', 'USA', 0, 'iheart', 10, 0),
        ('iheartsoftrock', 'iHeart Soft Rock', 'https://www.iheart.com/live/soft-rock-4414', 'Rock', 'USA', 0, 'iheart', 10, 0),
        ('litefm1067', 'WLTW', 'https://www.iheart.com/live/1067-lite-fm-1477', 'Pop', 'New York', 0, 'iheart', 10, 0),
        ('q101', 'Q101 Chicago', 'https://www.iheart.com/live/q101-6468/', 'Alternative', 'Chicago', 0, 'iheart', 15, 0),
        ('rock955', 'Rock 95.5 Chicago', 'https://www.iheart.com/live/rock-955-857/', 'Rock', 'Chicago', 0, 'iheart', 15, 0),
        ('us99', 'US99 99.5fm Chicago', 'https://www.iheart.com/live/us-99-10819/', 'Country', 'Chicago', 0, 'iheart', 15, 0),
        ('wls', '94.7 WLS Chicago', 'https://www.iheart.com/live/947-wls-5367/', 'Classic Hits', 'Chicago', 0, 'iheart', 15, 0),
        ('wiil', '95 WIIL ROCK Chicago', 'https://www.iheart.com/live/95-wiil-rock-7716/', 'Rock', 'Chicago', 0, 'iheart', 15, 0),
        ('wlite', '93.9 LITE fm Chicago', 'https://www.iheart.com/live/939-lite-fm-853/', 'Adult Contemporary', 'Chicago', 0, 'iheart', 15, 0),
    ]

    for station in stations:
        cursor.execute("""
            INSERT OR IGNORE INTO stations (id, name, url, genre, market, has_mbid, scraper_type, wait_time, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, station)
