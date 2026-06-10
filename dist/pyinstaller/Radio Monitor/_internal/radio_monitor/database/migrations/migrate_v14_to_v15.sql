-- Migration: Schema v14 → v15
-- Description: Add Various Artists fallback support to playlists and manual_playlists
-- Date: 2026-04-06
-- Author: Radio Monitor Development Team

BEGIN TRANSACTION;

-- Add columns to playlists table for Various Artists fallback support (automatic playlists)
ALTER TABLE playlists ADD COLUMN enable_various_artists_fallback BOOLEAN DEFAULT 0;
ALTER TABLE playlists ADD COLUMN various_artists_timeout_ms INTEGER DEFAULT 5000;

-- Add columns to manual_playlists table for Various Artists fallback support (manual playlists)
ALTER TABLE manual_playlists ADD COLUMN enable_various_artists_fallback BOOLEAN DEFAULT 0;
ALTER TABLE manual_playlists ADD COLUMN various_artists_timeout_ms INTEGER DEFAULT 5000;

-- Update schema version to 15
INSERT INTO schema_version (version, description)
VALUES (15, 'Add Various Artists fallback support to playlists and manual_playlists: enable_various_artists_fallback, various_artists_timeout_ms');

COMMIT;
