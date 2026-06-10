-- Migration: Schema v11 → v12
-- Description: Add manual playlist support
-- Date: 2026-02-23
-- Author: Radio Monitor Development Team

BEGIN TRANSACTION;

-- Create manual_playlists table
-- Stores manual playlist metadata (not songs, just the playlist definition)
CREATE TABLE IF NOT EXISTS manual_playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,  -- Internal name for our database
    plex_playlist_name TEXT,    -- Name sent to Plex (can differ)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_manual_playlists_name ON manual_playlists(name);
CREATE INDEX IF NOT EXISTS idx_manual_playlists_created ON manual_playlists(created_at);

-- Create manual_playlist_songs table
-- Junction table linking playlists to songs (many-to-many relationship)
CREATE TABLE IF NOT EXISTS manual_playlist_songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manual_playlist_id INTEGER NOT NULL,
    song_id INTEGER NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (manual_playlist_id) REFERENCES manual_playlists(id) ON DELETE CASCADE,
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
    UNIQUE(manual_playlist_id, song_id)  -- Prevent duplicates
);

CREATE INDEX IF NOT EXISTS idx_manual_playlist_songs_playlist ON manual_playlist_songs(manual_playlist_id);
CREATE INDEX IF NOT EXISTS idx_manual_playlist_songs_song ON manual_playlist_songs(song_id);

-- Create playlist_builder_state table
-- Temporary storage for in-progress playlist building (survives crashes)
CREATE TABLE IF NOT EXISTS playlist_builder_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,        -- Flask session ID
    song_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
    UNIQUE(session_id, song_id)      -- One entry per song per session
);

CREATE INDEX IF NOT EXISTS idx_playlist_builder_state_session ON playlist_builder_state(session_id);
CREATE INDEX IF NOT EXISTS idx_playlist_builder_state_song ON playlist_builder_state(song_id);

-- Update schema version to 12
INSERT INTO schema_version (version, description)
VALUES (12, 'Add manual playlist support: manual_playlists, manual_playlist_songs, playlist_builder_state tables');

COMMIT;
