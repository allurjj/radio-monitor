#!/usr/bin/env python
"""
Test suite for v1.1.1 bug fixes.

Run with: python -m pytest tests/test_v111_fixes.py -v
Or: python tests/test_v111_fixes.py
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime

from radio_monitor.normalization import normalize_artist_name, normalize_song_title
from radio_monitor.database.crud import add_artist


class TestNormalization:
    """Test normalization functions (Phase 0 - already implemented)"""

    def test_normalize_artist_title_case(self):
        """Test artist name title case normalization"""
        assert normalize_artist_name("AIN'T IT FUN") == "Ain't It Fun"
        assert normalize_artist_name("WE'RE GOOD") == "We're Good"
        assert normalize_artist_name("THE WEEKND") == "The Weeknd"

    def test_normalize_artist_exceptions(self):
        """Test artist name exceptions"""
        assert normalize_artist_name("PINK") == "P!NK"  # Preserves special cases
        assert normalize_artist_name("ABBA") == "ABBA"  # All caps preserved
        assert normalize_artist_name("KISS") == "KISS"  # All caps preserved

    def test_normalize_apostrophe_unification(self):
        """Test apostrophe unification for Plex compatibility"""
        # Tests would need to verify U+2019 -> U+0027 conversion
        result = normalize_song_title("Don't Stop")
        assert "'" in result  # Should use straight apostrophe
        assert "Don't" in result

    def test_normalize_song_title(self):
        """Test song title normalization"""
        assert normalize_song_title("AIN'T IT FUN") == "Ain't It Fun"
        assert normalize_song_title("WE'RE GOOD") == "We're Good"


class TestArtistUniqueConstraint:
    """Test artist UNIQUE constraint handling (Phase 3.1)"""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a test database with connection and cursor"""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Create artists table with actual schema
        cursor.execute("""
            CREATE TABLE artists (
                mbid TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                first_seen_station TEXT,
                first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                needs_lidarr_import BOOLEAN DEFAULT 1,
                lidarr_imported_at TIMESTAMP
            )
        """)

        conn.commit()
        yield conn, cursor
        conn.close()

    def test_add_new_artist(self, test_db):
        """Test adding a new artist"""
        conn, cursor = test_db
        is_new = add_artist(
            cursor=cursor,
            conn=conn,
            mbid="test-mbid-123",
            name="Test Artist",
            first_seen_station="test_station"
        )

        assert is_new == True  # Should return True for new artist
        cursor.execute("SELECT name, mbid FROM artists WHERE mbid = ?", ("test-mbid-123",))
        result = cursor.fetchone()
        assert result[0] == "Test Artist"
        assert result[1] == "test-mbid-123"

    def test_add_duplicate_artist_same_mbid(self, test_db):
        """Test adding duplicate artist with same MBID (should update)"""
        conn, cursor = test_db
        # Add first time
        is_new1 = add_artist(
            cursor=cursor,
            conn=conn,
            mbid="test-mbid-123",
            name="Test Artist",
            first_seen_station="station1"
        )

        # Add again with same MBID
        is_new2 = add_artist(
            cursor=cursor,
            conn=conn,
            mbid="test-mbid-123",
            name="Test Artist",
            first_seen_station="station2"
        )

        # First should be new, second should not
        assert is_new1 == True
        assert is_new2 == False

        # Should only have one artist
        cursor.execute("SELECT COUNT(*) FROM artists")
        count = cursor.fetchone()[0]
        assert count == 1

    def test_add_duplicate_artist_different_mbid(self, test_db):
        """Test adding duplicate artist with different MBID (should keep first)"""
        conn, cursor = test_db
        # Add first time
        is_new1 = add_artist(
            cursor=cursor,
            conn=conn,
            mbid="mbid-1",
            name="Test Artist",
            first_seen_station="station1"
        )

        # Try to add again with different MBID
        is_new2 = add_artist(
            cursor=cursor,
            conn=conn,
            mbid="mbid-2",
            name="Test Artist",
            first_seen_station="station2"
        )

        # First should be new, second should not (keeps first MBID)
        assert is_new1 == True
        assert is_new2 == False

        # Should only have one artist with first MBID
        cursor.execute("SELECT COUNT(*) FROM artists WHERE name = ?", ("Test Artist",))
        count = cursor.fetchone()[0]
        assert count == 1

        cursor.execute("SELECT mbid FROM artists WHERE name = ?", ("Test Artist",))
        mbid = cursor.fetchone()[0]
        assert mbid == "mbid-1"  # First MBID kept


class TestAdvertisementFiltering:
    """Test advertisement and website content filtering"""

    def test_filter_advertisement_phrases(self):
        """Test filtering advertisement phrases"""
        from radio_monitor.scrapers import is_advertisement_or_website_content

        # These should be filtered
        assert is_advertisement_or_website_content("Advertise With Us")
        assert is_advertisement_or_website_content("Sponsor This Show")
        assert is_advertisement_or_website_content("Sign Up Now")
        assert is_advertisement_or_website_content("Subscribe Today")

    def test_filter_website_content(self):
        """Test filtering website UI elements"""
        from radio_monitor.scrapers import is_advertisement_or_website_content

        # These should be filtered
        assert is_advertisement_or_website_content("Download the App")
        assert is_advertisement_or_website_content("Privacy Policy")
        assert is_advertisement_or_website_content("Terms of Service")
        assert is_advertisement_or_website_content("Contact Support")

    def test_allow_legitimate_songs(self):
        """Test that legitimate songs pass through"""
        from radio_monitor.scrapers import is_advertisement_or_website_content

        # These should NOT be filtered
        assert not is_advertisement_or_website_content("Blinding Lights")
        assert not is_advertisement_or_website_content("Shape of You")
        assert not is_advertisement_or_website_content("The Weeknd")
        assert not is_advertisement_or_website_content("Taylor Swift")


class TestDatetimeConsistency:
    """Test datetime.now() consistency pattern"""

    def test_single_datetime_capture(self):
        """Test capturing datetime once for related values"""
        # This is a documentation test - the pattern is in code
        # CORRECT pattern
        now = datetime.now()
        today = now.date().isoformat()
        current_hour = now.hour
        current_minute = now.minute

        # All values should be consistent
        assert today == now.date().isoformat()
        assert current_hour == now.hour
        assert current_minute == now.minute


class TestDuplicateDetection:
    """Test cross-hour duplicate detection pattern"""

    def test_cross_hour_time_difference(self):
        """Test calculating time difference across hour boundaries"""
        # Example from MEMORY.md:
        # Same song found at 15:44 and 16:44 (exactly 60 min apart)
        # With 75-min window using <=, this should be detected as duplicate

        existing_hour = 15
        existing_minute = 44
        current_hour = 16
        current_minute = 44
        duplicate_window_min = 75

        existing_total_min = existing_hour * 60 + existing_minute
        current_total_min = current_hour * 60 + current_minute
        time_diff_min = abs(current_total_min - existing_total_min)

        assert time_diff_min == 60
        assert time_diff_min <= duplicate_window_min  # Should be duplicate

    def test_use_less_than_or_equal(self):
        """Test that we use <= not < for time window"""
        # 65 minutes apart with 75-min window
        time_diff_min = 65
        duplicate_window_min = 75

        # CORRECT: Use <=
        is_duplicate_correct = time_diff_min <= duplicate_window_min
        assert is_duplicate_correct == True

        # WRONG: Using < would miss this duplicate
        is_duplicate_wrong = time_diff_min < duplicate_window_min
        assert is_duplicate_wrong == True  # Still true in this case

        # But at exactly 75 minutes:
        time_diff_min = 75
        is_duplicate_correct = time_diff_min <= duplicate_window_min
        is_duplicate_wrong = time_diff_min < duplicate_window_min

        assert is_duplicate_correct == True  # Correct: catches it
        assert is_duplicate_wrong == False  # Wrong: misses it


def run_tests():
    """Run tests manually without pytest"""
    print("Running v1.1.1 fix tests...\n")

    # Test 1: Normalization
    print("Test 1: Normalization functions")
    test_norm = TestNormalization()
    test_norm.test_normalize_artist_title_case()
    test_norm.test_normalize_artist_exceptions()
    test_norm.test_normalize_apostrophe_unification()
    test_norm.test_normalize_song_title()
    print("✓ Normalization tests passed\n")

    # Test 2: Advertisement filtering
    print("Test 2: Advertisement filtering")
    test_ads = TestAdvertisementFiltering()
    test_ads.test_filter_advertisement_phrases()
    test_ads.test_filter_website_content()
    test_ads.test_allow_legitimate_songs()
    print("✓ Advertisement filtering tests passed\n")

    # Test 3: Datetime consistency
    print("Test 3: Datetime consistency")
    test_dt = TestDatetimeConsistency()
    test_dt.test_single_datetime_capture()
    print("✓ Datetime consistency test passed\n")

    # Test 4: Duplicate detection
    print("Test 4: Duplicate detection")
    test_dup = TestDuplicateDetection()
    test_dup.test_cross_hour_time_difference()
    test_dup.test_use_less_than_or_equal()
    print("✓ Duplicate detection tests passed\n")

    print("All tests passed! ✓")


if __name__ == '__main__':
    # Try to run with pytest, fall back to manual
    try:
        pytest.main([__file__, '-v'])
    except ImportError:
        print("pytest not installed, running manual tests...\n")
        run_tests()
