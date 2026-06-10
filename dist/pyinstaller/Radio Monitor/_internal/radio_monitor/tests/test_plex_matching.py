#!/usr/bin/env python
"""
Unit tests for Plex matching functionality

Tests:
1. Exact match
2. Normalized match
3. Fuzzy match
4. Partial match
5. No match
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radio_monitor.plex import (
    normalize_text,
    find_song_in_library,
    test_plex_connection
)


# Mock Plex library
def create_mock_library():
    """Create a mock Plex music library"""
    return [
        {
            'title': 'Bad Guy',
            'artist': 'Billie Eilish',
            'album': 'When We All Fall Asleep, Where Do We Go?',
            'year': 2019,
            'ratingKey': 1
        },
        {
            'title': "Don't Start Now",
            'artist': 'Dua Lipa',
            'album': 'Future Nostalgia',
            'year': 2019,
            'ratingKey': 2
        },
        {
            'title': 'Watermelon Sugar',
            'artist': 'Harry Styles',
            'album': 'Fine Line',
            'year': 2019,
            'ratingKey': 3
        },
        {
            'title': 'Levitating',
            'artist': 'Dua Lipa',
            'album': 'Future Nostalgia',
            'year': 2020,
            'ratingKey': 4
        },
        {
            'title': 'Anti-Hero',
            'artist': 'Taylor Swift',
            'album': 'Midnights',
            'year': 2022,
            'ratingKey': 5
        },
        {
            'title': 'As It Was',
            'artist': 'Harry Styles',
            'album': "Harry's House",
            'year': 2022,
            'ratingKey': 6
        }
    ]


class TestPlexNormalization(unittest.TestCase):
    """Test string normalization for matching"""

    def test_normalize_text_lowercase(self):
        """Test text normalization lowercase"""
        self.assertEqual(normalize_text("HELLO WORLD"), "hello world")

    def test_normalize_text_remove_special_chars(self):
        """Test text normalization removes special characters"""
        # Remove punctuation
        self.assertEqual(normalize_text("Don't Start Now"), "dont start now")
        self.assertEqual(normalize_text("We're Young"), "were young")

    def test_normalize_text_remove_spaces(self):
        """Test text normalization removes extra spaces"""
        self.assertEqual(normalize_text("  Watermelon  Sugar  "), "watermelon sugar")

    def test_normalize_text_combined(self):
        """Test text normalization with all operations"""
        self.assertEqual(normalize_text("  DON'T  Start  Now  "), "dont start now")


class TestPlexMatching(unittest.TestCase):
    """Test Plex song matching via find_song_in_library

    Note: These tests require a real Plex server with library object.
    Unit tests only test the normalization logic.
    """

    def setUp(self):
        """Set up mock library"""
        self.library = create_mock_library()

    def test_exact_match_found(self):
        """Test exact match (found)

        Note: Requires real Plex connection - skipped for unit tests
        """
        # Unit tests can't test full Plex integration without a server
        self.skipTest("Requires Plex server connection - use integration tests")

    def test_exact_match_not_found(self):
        """Test exact match (not found)

        Note: Requires real Plex connection - skipped for unit tests
        """
        self.skipTest("Requires Plex server connection - use integration tests")

    def test_normalized_match_apostrophe(self):
        """Test normalized match handles missing apostrophe

        Note: Requires real Plex connection - skipped for unit tests
        """
        self.skipTest("Requires Plex server connection - use integration tests")

    def test_normalized_match_case_insensitive(self):
        """Test normalized match is case-insensitive

        Note: Requires real Plex connection - skipped for unit tests
        """
        self.skipTest("Requires Plex server connection - use integration tests")

    def test_fuzzy_match_typos(self):
        """Test fuzzy match handles typos

        Note: Requires real Plex connection - skipped for unit tests
        """
        self.skipTest("Requires Plex server connection - use integration tests")

    def test_fuzzy_match_too_different(self):
        """Test fuzzy match fails when too different

        Note: Requires real Plex connection - skipped for unit tests
        """
        self.skipTest("Requires Plex server connection - use integration tests")

    def test_partial_match(self):
        """Test partial match (word matching)

        Note: Requires real Plex connection - skipped for unit tests
        """
        self.skipTest("Requires Plex server connection - use integration tests")

    def test_partial_match_not_found(self):
        """Test partial match (not found)

        Note: Requires real Plex connection - skipped for unit tests
        """
        self.skipTest("Requires Plex server connection - use integration tests")


class TestPlexFindSong(unittest.TestCase):
    """Test complete find_song_in_library function

    Note: These tests require a Plex server connection.
    Skipped if Plex is not configured.
    """

    def setUp(self):
        """Set up mock library"""
        self.library = create_mock_library()

    def test_find_song_exact_match(self):
        """Test finding song with exact match

        Note: Requires real Plex connection - skipped for unit tests
        """
        # This test requires a real Plex library object with .search() method
        # For unit testing, we verify the normalization logic works
        self.skipTest("Requires Plex server connection - use integration tests")

    def test_find_song_normalized_match(self):
        """Test finding song with normalized match

        Note: Requires real Plex connection - skipped for unit tests
        """
        self.skipTest("Requires Plex server connection - use integration tests")

    def test_find_song_fuzzy_match(self):
        """Test finding song with fuzzy match

        Note: Requires real Plex connection - skipped for unit tests
        """
        self.skipTest("Requires Plex server connection - use integration tests")

    def test_find_song_not_found(self):
        """Test finding song that doesn't exist

        Note: Requires real Plex connection - skipped for unit tests
        """
        self.skipTest("Requires Plex server connection - use integration tests")

    def test_find_song_case_insensitive(self):
        """Test finding song is case-insensitive

        Note: Requires real Plex connection - skipped for unit tests
        """
        self.skipTest("Requires Plex server connection - use integration tests")

    def test_find_song_multiple_songs_by_artist(self):
        """Test finding correct song when artist has multiple songs

        Note: Requires real Plex connection - skipped for unit tests
        """
        self.skipTest("Requires Plex server connection - use integration tests")


class TestPlexMatchingEdgeCases(unittest.TestCase):
    """Test edge cases for Plex matching"""

    def setUp(self):
        """Set up mock library"""
        self.library = create_mock_library()

    def test_empty_library(self):
        """Test matching with empty library"""
        result = find_song_in_library([], "Any Song", "Any Artist")

        self.assertIsNone(result, "Should not find match in empty library")

    def test_empty_strings(self):
        """Test matching with empty strings"""
        result = find_song_in_library(self.library, "", "Billie Eilish")

        # Should still try to match by artist
        # (exact match won't work, but fuzzy might)

    def test_special_characters(self):
        """Test matching with special characters

        Note: Requires real Plex connection - skipped for unit tests
        """
        self.skipTest("Requires Plex server connection - use integration tests")


if __name__ == '__main__':
    unittest.main()
