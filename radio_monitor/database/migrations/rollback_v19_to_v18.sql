-- Rollback v19 to v18: Remove spotiflac_downloads table

-- Drop indexes
DROP INDEX IF EXISTS idx_spotiflac_downloads_started_at;
DROP INDEX IF EXISTS idx_spotiflac_downloads_status;
DROP INDEX IF EXISTS idx_spotiflac_downloads_plex_failure_id;

-- Drop table
DROP TABLE IF EXISTS spotiflac_downloads;

-- Update schema version
UPDATE schema_version SET version = 18;
