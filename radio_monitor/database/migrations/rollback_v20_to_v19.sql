-- Rollback v20 to v19: Remove match_key column

-- Step 1: Drop index
DROP INDEX IF EXISTS idx_artists_match_key;

-- Step 2: Drop column
-- SQLite doesn't support ALTER TABLE DROP COLUMN directly
-- We need to recreate the table without the match_key column

-- Create new table without match_key
CREATE TABLE IF NOT EXISTS artists_backup (
    mbid TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    first_seen_station TEXT,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    needs_lidarr_import BOOLEAN DEFAULT 1,
    lidarr_imported_at TIMESTAMP,
    FOREIGN KEY (first_seen_station) REFERENCES stations(id)
);

-- Copy data from artists to artists_backup
INSERT INTO artists_backup SELECT mbid, name, first_seen_station, first_seen_at, last_seen_at, needs_lidarr_import, lidarr_imported_at FROM artists;

-- Drop old table
DROP TABLE artists;

-- Rename backup to artists
ALTER TABLE artists_backup RENAME TO artists;

-- Recreate indexes
CREATE INDEX IF NOT EXISTS idx_artists_name ON artists(name);
CREATE INDEX IF NOT EXISTS idx_artists_needs_import ON artists(needs_lidarr_import) WHERE needs_lidarr_import = 1;
CREATE INDEX IF NOT EXISTS idx_artists_last_seen ON artists(last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_artists_first_seen ON artists(first_seen_at DESC);

-- Step 3: Update schema version
UPDATE schema_version SET version = 19;
