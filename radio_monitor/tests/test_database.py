#!/usr/bin/env python
"""
Unit tests for database functionality

Tests:
1. Artist CRUD operations
2. Song CRUD operations
3. Play count tracking
4. Statistics queries
5. Station health tracking
"""

import unittest
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radio_monitor.database import RadioDatabase


class TestDatabaseArtist(unittest.TestCase):
    """Test artist CRUD operations"""

    def setUp(self):
        """Set up test database"""
        self.db = RadioDatabase(":memory:")
        self.db.connect()

    def tearDown(self):
        """Clean up test database"""
        self.db.close()

    def test_add_artist(self):
        """Test adding a new artist"""
        mbid = "test-mbid-123"
        name = "Test Artist"
        station = "wtmx"

        self.db.add_artist(mbid, name, station)

        # Verify artist was added
        artist = self.db.get_artist_by_mbid(mbid)
        self.assertIsNotNone(artist, "Artist should be found")
        self.assertEqual(artist['name'], name, "Artist name should match")
        self.assertEqual(artist['mbid'], mbid, "Artist MBID should match")

    def test_add_duplicate_artist(self):
        """Test adding duplicate artist (should not error)"""
        mbid = "test-mbid-456"
        name = "Duplicate Artist"

        # Add same artist twice
        self.db.add_artist(mbid, name, "wtmx")
        self.db.add_artist(mbid, name, "us99")

        # Should still have only one artist with this MBID
        artist = self.db.get_artist_by_mbid(mbid)
        self.assertIsNotNone(artist, "Artist should be found")
        self.assertEqual(artist['name'], name, "Artist name should match")

    def test_get_artist_by_name(self):
        """Test retrieving artist by name"""
        mbid = "test-mbid-789"
        name = "Searchable Artist"

        self.db.add_artist(mbid, name, "wtmx")

        # Search by exact name
        artist = self.db.get_artist_by_name(name)
        self.assertIsNotNone(artist, "Artist should be found by name")
        self.assertEqual(artist['mbid'], mbid, "MBID should match")

    def test_get_artist_not_found(self):
        """Test retrieving nonexistent artist"""
        artist = self.db.get_artist_by_mbid("nonexistent-mbid")
        self.assertIsNone(artist, "Nonexistent artist should return None")

    def test_mark_artists_imported(self):
        """Test marking artists as imported to Lidarr"""
        mbids = ["mbid-1", "mbid-2", "mbid-3"]

        # Add artists
        for mbid in mbids:
            self.db.add_artist(mbid, f"Artist {mbid}", "wtmx")

        # Mark as imported
        self.db.mark_artists_imported(mbids)

        # Verify all are marked
        for mbid in mbids:
            artist = self.db.get_artist_by_mbid(mbid)
            self.assertFalse(artist['needs_lidarr_import'],
                           f"Artist {mbid} should not need import")
            self.assertIsNotNone(artist['lidarr_imported_at'],
                              f"Artist {mbid} should have import timestamp")


class TestDatabaseSong(unittest.TestCase):
    """Test song CRUD operations"""

    def setUp(self):
        """Set up test database"""
        self.db = RadioDatabase(":memory:")
        self.db.connect()
        # Add test artist
        self.mbid = "test-mbid-songs"
        self.db.add_artist(self.mbid, "Test Artist", "wtmx")

    def tearDown(self):
        """Clean up test database"""
        self.db.close()

    def test_add_song(self):
        """Test adding a new song"""
        artist_name = "Test Artist"
        song_title = "Test Song"

        is_new, song_id, play_count = self.db.add_song(self.mbid, artist_name, song_title)

        self.assertTrue(is_new, "Song should be new")
        self.assertIsNotNone(song_id, "Song ID should not be None")
        self.assertEqual(play_count, 1, "Play count should be 1")

        # Verify song was added (get_top_songs returns tuples: (title, artist, plays))
        songs = self.db.get_top_songs(limit=1)
        self.assertEqual(len(songs), 1, "Should have 1 song")
        self.assertEqual(songs[0][0], song_title, "Song title should match")

    def test_increment_play_count(self):
        """Test incrementing play count"""
        artist_name = "Test Artist"
        song_title = "Popular Song"

        # Add song
        is_new, song_id, play_count = self.db.add_song(self.mbid, artist_name, song_title, station_id="wtmx")

        # Increment play count
        date = "2025-01-07"
        hour = 7
        station = "wtmx"

        self.db.increment_play_count(date, hour, song_id, station)

        # Verify by getting top songs (play count should be incremented)
        songs = self.db.get_top_songs(limit=1)
        self.assertEqual(len(songs), 1, "Should have 1 song")
        # Should have 2 plays (1 from add_song + 1 from increment)
        self.assertEqual(songs[0][2], 2, "Play count should be 2")

    def test_song_play_count_aggregation(self):
        """Test that song play counts are aggregated correctly"""
        artist_name = "Test Artist"
        song_title = "Hit Song"

        # Add song (creates 1 play)
        is_new, song_id, play_count = self.db.add_song(self.mbid, artist_name, song_title, station_id="wtmx")

        # Add more plays via increment
        for i in range(5):
            self.db.increment_play_count("2025-01-07", i, song_id, "wtmx")

        # Get top songs (returns tuples: (title, artist, plays))
        songs = self.db.get_top_songs(limit=1)
        self.assertEqual(len(songs), 1, "Should have 1 song")
        # Should have 6 plays total (1 from add_song + 5 from increments)
        self.assertEqual(songs[0][2], 6, "Play count should be 6 (1 from add + 5 increments)")


class TestDatabaseStats(unittest.TestCase):
    """Test statistics queries"""

    def setUp(self):
        """Set up test database"""
        self.db = RadioDatabase(":memory:")
        self.db.connect()

        # Add test data
        self.mbid1 = "mbid-stats-1"
        self.mbid2 = "mbid-stats-2"

        self.db.add_artist(self.mbid1, "Artist One", "wtmx")
        self.db.add_artist(self.mbid2, "Artist Two", "us99")

        # Add songs
        is_new1, self.song1, play_count1 = self.db.add_song(self.mbid1, "Artist One", "Song One", station_id="wtmx")
        is_new2, self.song2, play_count2 = self.db.add_song(self.mbid2, "Artist Two", "Song Two", station_id="us99")

        # Add more plays
        for i in range(9):  # 9 more = 10 total with add_song
            self.db.increment_play_count("2025-01-07", i, self.song1, "wtmx")
        for i in range(4):  # 4 more = 5 total with add_song
            self.db.increment_play_count("2025-01-07", i, self.song2, "us99")

    def tearDown(self):
        """Clean up test database"""
        self.db.close()

    def test_get_stats(self):
        """Test getting database statistics"""
        stats = self.db.get_stats()

        self.assertIsNotNone(stats, "Stats should not be None")
        self.assertEqual(stats['artists'], 2, "Should have 2 artists")
        self.assertEqual(stats['songs'], 2, "Should have 2 songs")
        self.assertGreater(stats['total_plays'], 0, "Should have plays")

    def test_get_top_songs(self):
        """Test getting top songs"""
        songs = self.db.get_top_songs(limit=10)

        self.assertEqual(len(songs), 2, "Should have 2 songs")
        # Song One should be first (10 plays vs 5 plays)
        # Returns tuples: (title, artist, plays)
        self.assertEqual(songs[0][0], "Song One", "Top song should be Song One")
        # Play count includes 1 from add_song + 9 from increment = 10 total
        self.assertGreaterEqual(songs[0][2], 9, "Song One should have at least 9 plays")


class TestStationHealth(unittest.TestCase):
    """Test station health tracking"""

    def setUp(self):
        """Set up test database"""
        self.db = RadioDatabase(":memory:")
        self.db.connect()

        # Add a test station
        self.db.cursor.execute("""
            INSERT INTO stations (id, name, url, genre, market)
            VALUES ('test1', 'Test Station', 'http://test.com', 'Pop', 'Chicago')
        """)
        self.db.conn.commit()

    def tearDown(self):
        """Clean up test database"""
        self.db.close()

    def test_record_scrape_success(self):
        """Test recording successful scrape"""
        station_id = "test1"

        self.db.record_scrape_success(station_id)

        health = self.db.get_station_health(station_id)
        self.assertEqual(health['consecutive_failures'], 0,
                        "Failures should be reset to 0")
        self.assertTrue(health['enabled'], "Station should be enabled")

    def test_record_scrape_failure(self):
        """Test recording failed scrape"""
        station_id = "test1"

        # Record 5 failures
        for i in range(5):
            self.db.record_scrape_failure(station_id)

        health = self.db.get_station_health(station_id)
        self.assertEqual(health['consecutive_failures'], 5,
                        "Should have 5 failures")
        self.assertTrue(health['enabled'], "Station should still be enabled")

    def test_auto_disable_after_144_failures(self):
        """Test auto-disable after 144 failures"""
        station_id = "test1"

        # Record 144 failures
        for i in range(144):
            self.db.record_scrape_failure(station_id)

        health = self.db.get_station_health(station_id)
        self.assertEqual(health['consecutive_failures'], 144,
                        "Should have 144 failures")
        self.assertFalse(health['enabled'], "Station should be disabled")

    def test_get_station_health_status(self):
        """Test station health status calculation"""
        station_id = "test1"

        # Test healthy status (0 failures)
        self.db.record_scrape_success(station_id)
        health = self.db.get_station_health(station_id)
        self.assertEqual(health['status'], 'Healthy', "Status should be Healthy")
        self.assertEqual(health['status_class'], 'success', "Class should be success")

        # Test degraded status (1 failure)
        self.db.record_scrape_failure(station_id)
        health = self.db.get_station_health(station_id)
        self.assertIn('Degraded', health['status'], "Status should be Degraded")
        self.assertEqual(health['status_class'], 'warning', "Class should be warning")


if __name__ == '__main__':
    unittest.main()
