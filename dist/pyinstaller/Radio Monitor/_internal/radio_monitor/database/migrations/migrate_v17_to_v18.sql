-- Migration v17 to v18: Add retry_match_succeeded column to plex_match_failures
-- This adds tracking for retry match success status

-- Add retry_match_succeeded column
ALTER TABLE plex_match_failures ADD COLUMN retry_match_succeeded BOOLEAN DEFAULT NULL;

-- Update schema version
INSERT INTO schema_version (version, description) VALUES (18, 'Add retry_match_succeeded column to plex_match_failures for tracking Plex retry attempts');
