-- Rollback v21 → v20: Remove Song Verification (Phase 1)

-- Drop verification table
DROP TABLE IF EXISTS artist_song_verification;

-- Note: We don't drop the columns from songs table
-- because SQLite doesn't support DROP COLUMN

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES (20);
