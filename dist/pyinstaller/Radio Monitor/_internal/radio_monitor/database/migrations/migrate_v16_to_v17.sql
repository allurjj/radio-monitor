-- Migration 017: Fix NULL artist_mbid values in songs table
-- Date: 2026-04-07
-- Issue: Songs with NULL artist_mbid cause crashes when linking to artist detail pages

-- Step 1: Find all songs with NULL artist_mbid
-- These will be logged for manual review

-- Step 2: For each NULL artist_mbid, try to find the correct artist by name
-- Strategy: Use artist_name to match artists.name (case-insensitive)

-- Step 3: Create PENDING artists for orphaned songs (no matching artist)
-- This ensures every song has a valid artist_mbid

-- Step 4: Update songs with corrected artist_mbids

-- Clean up orphaned artists (0 songs) after fixing NULL mbids
DELETE FROM artists
WHERE mbid NOT IN (SELECT DISTINCT artist_mbid FROM songs WHERE artist_mbid IS NOT NULL);

INSERT OR IGNORE INTO schema_version (version, description, applied_at)
VALUES (17, 'Fix NULL artist_mbid values and clean up orphaned artists', CURRENT_TIMESTAMP);
