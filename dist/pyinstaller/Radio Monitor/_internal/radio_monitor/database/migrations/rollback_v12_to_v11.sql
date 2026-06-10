-- Rollback: Schema v12 → v11
-- Description: Remove manual playlist support
-- Date: 2026-02-23
-- Author: Radio Monitor Development Team
-- WARNING: This will DELETE all manual playlists and playlist builder state!

BEGIN TRANSACTION;

-- Drop playlist_builder_state table
DROP TABLE IF EXISTS playlist_builder_state;

-- Drop manual_playlist_songs table
DROP TABLE IF EXISTS manual_playlist_songs;

-- Drop manual_playlists table
DROP TABLE IF EXISTS manual_playlists;

-- Remove schema version 12 entry
DELETE FROM schema_version WHERE version = 12;

COMMIT;
