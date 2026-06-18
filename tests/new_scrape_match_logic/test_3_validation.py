"""
Phase 3 Tests: Song Validation Helper Functions

Tests for the helper functions that enhance song validation:
- strip_song_suffixes(): Removes version suffixes for better matching
- calculate_similarity(): Calculates string similarity for near matches

These functions can be used by recording_validation.py to enhance matching
without replacing the existing validation logic.
"""

import pytest
from radio_monitor.normalization import calculate_similarity, strip_song_suffixes


# ==================== STRIP SUFFIX TESTS ====================

def test_strip_song_suffixes():
    """Test suffix stripping function"""
    # Remix variations
    assert strip_song_suffixes("Neon Moon (Remix)") == "Neon Moon"
    assert strip_song_suffixes("Test Song (Club Remix)") == "Test Song"
    assert strip_song_suffixes("Austin - Remix") == "Austin"

    # Live variations
    assert strip_song_suffixes("Neon Moon (Live)") == "Neon Moon"
    assert strip_song_suffixes("Test Song - Live") == "Test Song"
    assert strip_song_suffixes("Song (Live Version)") == "Song"

    # Edit variations
    assert strip_song_suffixes("Test Song (Radio Edit)") == "Test Song"
    assert strip_song_suffixes("Test Song (Vocal Edit)") == "Test Song"
    assert strip_song_suffixes("Song (Edit)") == "Song"

    # Remaster variations
    assert strip_song_suffixes("Test Song (Remastered)") == "Test Song"
    assert strip_song_suffixes("Test Song (2023 Remaster)") == "Test Song"
    assert strip_song_suffixes("Song - Remastered") == "Song"

    # Already clean (no change)
    assert strip_song_suffixes("Neon Moon") == "Neon Moon"
    assert strip_song_suffixes("Test Song") == "Test Song"


def test_strip_suffixes_preserves_clean_titles():
    """Test that strip_song_suffixes doesn't modify clean titles"""
    assert strip_song_suffixes("Neon Moon") == "Neon Moon"
    assert strip_song_suffixes("Test Song") == "Test Song"
    assert strip_song_suffixes("Austin") == "Austin"
    assert strip_song_suffixes("Don't Take the Girl") == "Don't Take the Girl"


def test_strip_suffixes_handles_short_titles():
    """Test that strip_song_suffixes works correctly for short titles"""
    assert strip_song_suffixes("Bad (Remix)") == "Bad"
    assert strip_song_suffixes("Up (Live)") == "Up"
    assert strip_song_suffixes("Hey (Edit)") == "Hey"
    assert strip_song_suffixes("A (Remix)") == "A"


# ==================== SIMILARITY TESTS ====================

def test_similarity_calculation():
    """Test similarity calculation between strings"""
    # Exact match
    assert calculate_similarity("Neon Moon", "Neon Moon") == 1.0

    # Case insensitive
    assert calculate_similarity("Neon Moon", "neon moon") == 1.0

    # Different songs should have low similarity
    assert calculate_similarity("Neon Moon", "Different Song") < 0.5
    assert calculate_similarity("Test Song", "Completely Different Title") < 0.5


def test_similarity_threshold():
    """Test that similarity calculation works correctly"""
    # High similarity (close matches - minor typos)
    assert calculate_similarity("Neon Moon", "Neon Moo") >= 0.85

    # Very low similarity (completely different)
    assert calculate_similarity("Test Song", "Completely Different Title") < 0.3
    assert calculate_similarity("Neon Moon", "Boot Scootin' Boogy") < 0.3


def test_similarity_function_exists():
    """Test that calculate_similarity function exists and is callable"""
    assert callable(calculate_similarity)


def test_similarity_function_signature():
    """Test that calculate_similarity has correct signature"""
    import inspect
    sig = inspect.signature(calculate_similarity)
    params = list(sig.parameters.keys())

    # Should have two parameters
    assert len(params) == 2


def test_strip_function_exists():
    """Test that strip_song_suffixes function exists and is callable"""
    assert callable(strip_song_suffixes)


def test_strip_function_signature():
    """Test that strip_song_suffixes has correct signature"""
    import inspect
    sig = inspect.signature(strip_song_suffixes)
    params = list(sig.parameters.keys())

    # Should have one parameter
    assert len(params) == 1
    assert 'title' in params


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
