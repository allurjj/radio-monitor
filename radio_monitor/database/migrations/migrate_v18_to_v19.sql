-- Migration v18 to v19: Add spotiflac_downloads table
-- This adds tracking for SpotiFLAC download jobs

-- Create spotiflac_downloads table
CREATE TABLE IF NOT EXISTS spotiflac_downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plex_match_failure_id INTEGER,  -- Link to the Plex failure that triggered this download
    song_title TEXT NOT NULL,
    artist_name TEXT NOT NULL,
    album_name TEXT,
    spotify_url TEXT,
    download_status TEXT NOT NULL DEFAULT 'starting',  -- 'starting', 'downloading', 'converting', 'complete', 'failed'
    service_used TEXT,  -- 'tidal', 'qobuz', 'amazon', 'deezer', 'youtube', 'spotify'
    file_path TEXT,
    file_size_mb REAL,
    error_message TEXT,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (plex_match_failure_id) REFERENCES plex_match_failures(id) ON DELETE SET NULL
);

-- Create index on plex_match_failure_id for lookups
CREATE INDEX IF NOT EXISTS idx_spotiflac_downloads_plex_failure_id ON spotiflac_downloads(plex_match_failure_id);

-- Create index on download_status for filtering
CREATE INDEX IF NOT EXISTS idx_spotiflac_downloads_status ON spotiflac_downloads(download_status);

-- Create index on started_at for sorting
CREATE INDEX IF NOT EXISTS idx_spotiflac_downloads_started_at ON spotiflac_downloads(started_at);

-- Update schema version
INSERT INTO schema_version (version, description) VALUES (19, 'Add spotiflac_downloads table for tracking SpotiFLAC download jobs');
