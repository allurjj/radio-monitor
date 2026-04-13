-- Migration v20 → v21: Song Verification (Phase 1)
-- Adds MusicBrainz + Lidarr verification tracking

-- Add verification status to songs table
ALTER TABLE songs ADD COLUMN verification_status TEXT DEFAULT 'UNVERIFIED';
ALTER TABLE songs ADD COLUMN verification_date TIMESTAMP;

-- Add verification details table
CREATE TABLE artist_song_verification (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id INTEGER NOT NULL,
    verification_source TEXT NOT NULL,
    is_verified BOOLEAN NOT NULL DEFAULT 0,
    verified_at TIMESTAMP,
    metadata_json TEXT,
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
    UNIQUE(song_id, verification_source)
);

-- Indexes for fast lookups
CREATE INDEX idx_verification_song_id ON artist_song_verification(song_id);
CREATE INDEX idx_verification_source ON artist_song_verification(verification_source);
CREATE INDEX idx_songs_verification_status ON songs(verification_status);

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES (21);
