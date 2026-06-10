-- Rollback: Schema v15 → v14
-- Description: Remove Various Artists fallback support from playlists
-- Date: 2026-04-06
-- Author: Radio Monitor Development Team

BEGIN TRANSACTION;

-- Note: SQLite doesn't support DROP COLUMN directly
-- This is a limitation - rollback would require recreating the table
-- For production use, consider using a full database export/import strategy

-- Update schema version back to 14
DELETE FROM schema_version WHERE version = 15;

COMMIT;
