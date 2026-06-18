"""
Test match_key generation functionality

Tests for the Phase 1 database-first lookup implementation.
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from radio_monitor.normalization import generate_match_key_for_db, normalize_for_matching


def test_match_key_basic():
    """Test basic match key generation"""
    assert generate_match_key_for_db("Brooks & Dunn") == "brooksdunn"
    # P!NK becomes PNK (no !), then lowercased to pnk
    assert generate_match_key_for_db("P!NK") == "pnk"
    # "The" prefix is removed for band names
    assert generate_match_key_for_db("The Weeknd") == "weeknd"


def test_match_key_edge_cases():
    """Test edge cases"""
    assert generate_match_key_for_db("Carly Pearce + Lee Brice") == "carlypearceleebrice"
    assert generate_match_key_for_db("Post Malone") == "postmalone"
    assert generate_match_key_for_db("Dierks Bentley") == "dierksbentley"


def test_match_key_consistency():
    """Test that same input produces same output"""
    assert generate_match_key_for_db("Brooks & Dunn") == generate_match_key_for_db("BROOKS & DUNN")
    assert generate_match_key_for_db("P!NK") == generate_match_key_for_db("p!nk")
    assert generate_match_key_for_db("Brooks & Dunn") == generate_match_key_for_db("Brooks Dunn")


def test_match_key_special_chars():
    """Test special character handling"""
    assert generate_match_key_for_db("Mary J. Blige") == "maryjblige"
    assert generate_match_key_for_db("B-52s") == "b52s"
    assert generate_match_key_for_db("Earth, Wind & Fire") == "earthwindfire"


def test_match_key_the_prefix():
    """Test 'The' prefix removal"""
    assert generate_match_key_for_db("The Beatles") == "beatles"
    assert generate_match_key_for_db("THE ROLLING STONES") == "rollingstones"


def test_match_key_empty_string():
    """Test empty string handling"""
    result = generate_match_key_for_db("")
    assert result == ""


def test_match_key_null_input():
    """Test None input handling"""
    # The function should handle None gracefully
    # Currently it returns "" for None after normalization
    result = generate_match_key_for_db(None)
    # Should return empty string or handle gracefully
    assert result == "" or result is None


def test_normalize_for_matching():
    """Test the underlying normalization function"""
    assert normalize_for_matching("Brooks & Dunn") == "brooksdunn"
    assert normalize_for_matching("Dan + Shay") == "danshay"
    # "The" prefix is removed for band names
    assert normalize_for_matching("The Weeknd") == "weeknd"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
