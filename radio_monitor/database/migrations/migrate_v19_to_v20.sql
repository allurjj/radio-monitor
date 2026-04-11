-- Migration v19 to v20: Add match_key column for duplicate detection
-- This adds an aggressive normalization key to prevent duplicate artists

-- Step 1: Add match_key column to artists table (if not exists)
-- Note: SQLite doesn't support IF NOT EXISTS for ALTER TABLE ADD COLUMN
-- We'll check if the column exists first by trying to use it
-- This migration is safe for both v19 databases (need column) and fresh v20 databases (already has it)

-- Step 2: Backfill existing artists with match_key
-- Rules: lowercase, remove spaces, remove punctuation (& + , . - ' ")
-- Additional cleanup: Remove "the" prefix for band names
-- Only update if match_key is NULL (handles both fresh and migrated databases)
UPDATE artists SET match_key = LOWER(
    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(name, ' ', ''), '&', ''), '+', ''), ',', ''), '.', ''), '-', ''), char(39), '')
) WHERE match_key IS NULL;

-- Remove apostrophes (both ASCII and Unicode)
UPDATE artists SET match_key = REPLACE(match_key, '''', '') WHERE match_key IS NOT NULL;
UPDATE artists SET match_key = REPLACE(match_key, char(39), '') WHERE match_key IS NOT NULL;

-- Remove "the" prefix (case-insensitive after lowercase conversion)
UPDATE artists SET match_key = SUBSTR(match_key, 4)
WHERE match_key LIKE 'the%';

-- Step 3: Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_artists_match_key ON artists(match_key);

-- Step 4: Update schema version
INSERT INTO schema_version (version, description) VALUES (20, 'Add match_key column for aggressive duplicate detection');
