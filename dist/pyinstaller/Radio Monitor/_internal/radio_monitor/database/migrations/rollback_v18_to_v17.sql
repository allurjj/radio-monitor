-- Rollback v18 to v17: Remove retry_match_succeeded column from plex_match_failures

-- Remove retry_match_succeeded column
ALTER TABLE plex_match_failures DROP COLUMN retry_match_succeeded;

-- Update schema version
UPDATE schema_version SET version = 17;
