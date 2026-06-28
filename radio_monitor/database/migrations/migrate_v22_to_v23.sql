-- Migration: Schema v22 to v23
-- Description: Add year column to songs table and year range filtering to playlists table
-- Created: 2026-06-28

BEGIN TRANSACTION;

-- Add year column to songs table (nullable for existing records)
ALTER TABLE songs ADD COLUMN year INTEGER;

-- Add year range columns to playlists table (nullable for existing playlists)
ALTER TABLE playlists ADD COLUMN year_from INTEGER;
ALTER TABLE playlists ADD COLUMN year_to INTEGER;

-- Create index for year-based filtering on songs
CREATE INDEX IF NOT EXISTS idx_songs_year ON songs(year);

-- Update schema version
INSERT OR REPLACE INTO schema_version (version, description, applied_at)
VALUES (23, 'Add year column to songs table and year range filtering to playlists', CURRENT_TIMESTAMP);

COMMIT;
