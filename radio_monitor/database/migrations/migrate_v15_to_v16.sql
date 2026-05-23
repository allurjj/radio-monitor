-- Migration 016: Add Plex manual overrides system
-- Date: 2026-04-06

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
);

CREATE INDEX IF NOT EXISTS idx_plex_overrides_song_id ON plex_manual_overrides(song_id);
CREATE INDEX IF NOT EXISTS idx_plex_overrides_plex_key ON plex_manual_overrides(plex_track_key);
CREATE INDEX IF NOT EXISTS idx_plex_overrides_active ON plex_manual_overrides(is_active);

INSERT OR IGNORE INTO schema_version (version, description, applied_at)
VALUES (16, 'Add Plex manual overrides system', CURRENT_TIMESTAMP);
