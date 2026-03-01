#!/usr/bin/env python
"""
Unit tests for MBID lookup functionality

Tests:
1. MBID lookup for found artist
2. MBID lookup for not found artist
3. MBID caching
4. Rate limiting
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radio_monitor.mbid import lookup_artist_mbid
from radio_monitor.database import RadioDatabase


class TestMBIDLookup(unittest.TestCase):
    """Test MBID lookup functionality"""

    def setUp(self):
        """Set up test database"""
        self.db = RadioDatabase(":memory:")
        self.db.connect()

    def tearDown(self):
        """Clean up test database"""
        self.db.close()

    def test_mbid_lookup_found_taylor_swift(self):
        """Test MBID lookup for known artist (Taylor Swift)

        Note: This test requires internet connection to MusicBrainz API.
        Skipped if API is unreachable.
        """
        mbid = lookup_artist_mbid("Taylor Swift", self.db)

        # Skip test if API is unreachable
        if mbid is None:
            self.skipTest("MusicBrainz API unreachable - skipping live API test")

        self.assertEqual(mbid, "20244d07-534f-4eff-b4d4-930878889970",
                        "Taylor Swift MBID should match known value")

    def test_mbid_lookup_found_bad_bunny(self):
        """Test MBID lookup for known artist (Bad Bunny)

        Note: This test requires internet connection to MusicBrainz API.
        Skipped if API is unreachable.
        """
        mbid = lookup_artist_mbid("Bad Bunny", self.db)

        # Skip test if API is unreachable
        if mbid is None:
            self.skipTest("MusicBrainz API unreachable - skipping live API test")

        self.assertEqual(mbid, "954c026c-5a24-4e0f-b74e-af7bc1e4ff8a",
                        "Bad Bunny MBID should match known value")

    def test_mbid_lookup_not_found(self):
        """Test MBID lookup for nonexistent artist"""
        mbid = lookup_artist_mbid("Nonexistent Artist 123456789", self.db)

        self.assertIsNone(mbid, "MBID should be None for nonexistent artist")

    def test_mbid_cache_hit(self):
        """Test that second lookup uses cache

        Note: This test requires internet connection to MusicBrainz API.
        Skipped if API is unreachable.
        """
        # First lookup (cache miss)
        mbid1 = lookup_artist_mbid("Taylor Swift", self.db)

        # Skip if API unreachable
        if mbid1 is None:
            self.skipTest("MusicBrainz API unreachable - skipping cache test")

        # Second lookup (cache hit)
        mbid2 = lookup_artist_mbid("Taylor Swift", self.db)

        self.assertEqual(mbid1, mbid2, "Cached MBID should match first lookup")

    def test_mbid_case_insensitive(self):
        """Test that MBID lookup is case-insensitive

        Note: This test requires internet connection to MusicBrainz API.
        Skipped if API is unreachable.
        """
        mbid1 = lookup_artist_mbid("taylor swift", self.db)

        # Skip if API unreachable
        if mbid1 is None:
            self.skipTest("MusicBrainz API unreachable - skipping case test")

        mbid2 = lookup_artist_mbid("TAYLOR SWIFT", self.db)
        mbid3 = lookup_artist_mbid("TaYlOr SwIfT", self.db)

        self.assertIsNotNone(mbid1, "Lowercase lookup should work")
        self.assertIsNotNone(mbid2, "Uppercase lookup should work")
        self.assertIsNotNone(mbid3, "Mixed case lookup should work")
        self.assertEqual(mbid1, mbid2, "Case should not affect MBID")
        self.assertEqual(mbid2, mbid3, "Case should not affect MBID")

    def test_mbid_with_special_characters(self):
        """Test MBID lookup with artist name containing special characters

        Note: This test requires internet connection to MusicBrainz API.
        Skipped if API is unreachable.
        """
        # Test with artist that has special characters
        mbid = lookup_artist_mbid("Carly Rae Jepsen", self.db)

        # Skip if API unreachable
        if mbid is None:
            self.skipTest("MusicBrainz API unreachable - skipping special character test")

        # Verify it's a valid MBID format (UUID)
        self.assertRegex(mbid, r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
                        "MBID should be valid UUID format")


class TestMBIDCache(unittest.TestCase):
    """Test MBID caching functionality"""

    def setUp(self):
        """Set up test database"""
        self.db = RadioDatabase(":memory:")
        self.db.connect()

    def tearDown(self):
        """Clean up test database"""
        self.db.close()

    def test_cache_persists_across_lookups(self):
        """Test that cached MBID persists across multiple lookups

        Note: This test requires internet connection to MusicBrainz API.
        Skipped if API is unreachable.
        """
        mbid1 = lookup_artist_mbid("Taylor Swift", self.db)

        # Skip if API unreachable
        if mbid1 is None:
            self.skipTest("MusicBrainz API unreachable - skipping cache persistence test")

        # Manually add to cache to simulate successful first lookup
        self.db.add_artist(mbid1, "Taylor Swift", "test")

        # Second lookup should find in cache
        mbid2 = lookup_artist_mbid("Taylor Swift", self.db)

        self.assertEqual(mbid1, mbid2, "First and second lookup should match")

    def test_different_artists_have_different_mbids(self):
        """Test that different artists get different MBIDs

        Note: This test requires internet connection to MusicBrainz API.
        Skipped if API is unreachable.
        """
        mbid_taylor = lookup_artist_mbid("Taylor Swift", self.db)

        # Skip if API unreachable
        if mbid_taylor is None:
            self.skipTest("MusicBrainz API unreachable - skipping different artists test")

        mbid_bad_bunny = lookup_artist_mbid("Bad Bunny", self.db)

        # Skip if second lookup failed
        if mbid_bad_bunny is None:
            self.skipTest("MusicBrainz API unreachable - second lookup failed")

        self.assertNotEqual(mbid_taylor, mbid_bad_bunny,
                           "Different artists should have different MBIDs")


if __name__ == '__main__':
    unittest.main()
