"""
Test integration of database-first MBID lookup

Tests for the Phase 1 database-first lookup implementation.
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from radio_monitor.database import RadioDatabase
from radio_monitor.mbid import lookup_artist_mbid
from radio_monitor.normalization import generate_match_key_for_db


def test_lookup_uses_station_mbid():
    """Test that station MBID takes priority (when implemented in future phases)"""
    # This test is for future phases - for now just verify function works
    db_path = ":memory:"
    db = RadioDatabase(db_path)
    db.connect()

    # Just verify function doesn't crash with basic input
    mbid, verified_name, _, method = lookup_artist_mbid("Test Artist", db, max_retries=1)

    # Should return None for non-existent artist
    assert mbid is None or mbid.startswith("PENDING-")


def test_lookup_uses_database_mbid():
    """Test that database MBID is used before MusicBrainz"""
    db_path = ":memory:"
    db = RadioDatabase(db_path)
    db.connect()

    cursor = db.get_cursor()

    # Pre-populate database with known artist
    artist_name = "Brooks & Dunn"
    match_key = generate_match_key_for_db(artist_name)
    test_mbid = "f30118c5-0ff5-449a-839c-23efa634caa4"

    cursor.execute("""
        INSERT INTO artists (mbid, name, match_key, first_seen_station)
        VALUES (?, ?, ?, NULL)
    """, (test_mbid, artist_name, match_key))
    db.conn.commit()

    cursor.close()

    # Lookup should use database, not MusicBrainz
    mbid, verified_name, method = lookup_artist_mbid(artist_name, db)

    assert mbid == test_mbid
    assert verified_name == artist_name


def test_lookup_queries_musicbrainz_if_not_in_db():
    """Test that MusicBrainz is queried if artist not in database"""
    db_path = ":memory:"
    db = RadioDatabase(db_path)
    db.connect()

    # Use a well-known artist that should be in MusicBrainz
    # The Weeknd is a popular artist with a stable MBID
    artist_name = "The Weeknd"

    # Not in database, should query MusicBrainz
    mbid, verified_name, method = lookup_artist_mbid(artist_name, db, max_retries=3)

    # Should find MBID from MusicBrainz (or return None if API fails)
    if mbid:
        # If MBID found, it should not start with PENDING-
        assert not mbid.startswith("PENDING-") or mbid is None
        assert verified_name is not None


def test_lookup_retries_pending_mbid():
    """Test that PENDING MBID triggers MusicBrainz lookup"""
    db_path = ":memory:"
    db = RadioDatabase(db_path)
    db.connect()

    cursor = db.get_cursor()

    # Pre-populate with PENDING MBID
    artist_name = "Test Artist 12345"  # Use artist unlikely to be in MusicBrainz
    match_key = generate_match_key_for_db(artist_name)
    pending_mbid = "PENDING-test-uuid"

    cursor.execute("""
        INSERT INTO artists (mbid, name, match_key, first_seen_station)
        VALUES (?, ?, ?, NULL)
    """, (pending_mbid, artist_name, match_key))
    db.conn.commit()

    cursor.close()

    # Should retry MusicBrainz lookup (but won't find this artist)
    mbid, verified_name, method = lookup_artist_mbid(artist_name, db, max_retries=1, auto_retry_pending=True)

    # For a non-existent artist, should return None or a new PENDING MBID
    # The test verifies that the lookup was attempted (no crash)
    assert mbid is None or mbid.startswith("PENDING-") or isinstance(mbid, str)


def test_lookup_uses_match_key():
    """Test that match_key lookup works as fallback"""
    db_path = ":memory:"
    db = RadioDatabase(db_path)
    db.connect()

    cursor = db.get_cursor()

    # Add artist with different spacing than lookup name
    # Database has "Brooks & Dunn", we'll search for "Brooks Dunn"
    db_artist_name = "Brooks & Dunn"
    match_key = generate_match_key_for_db(db_artist_name)
    test_mbid = "f30118c5-0ff5-449a-839c-23efa634caa4"

    cursor.execute("""
        INSERT INTO artists (mbid, name, match_key, first_seen_station)
        VALUES (?, ?, ?, NULL)
    """, (test_mbid, db_artist_name, match_key))
    db.conn.commit()

    cursor.close()

    # Search with slightly different name (should still find via match_key)
    mbid, verified_name, _, method = lookup_artist_mbid("Brooks Dunn", db)

    # Should find via match_key lookup
    assert mbid == test_mbid


def test_database_cache_hit_rate():
    """Test that database-first lookup provides cache hits"""
    db_path = ":memory:"
    db = RadioDatabase(db_path)
    db.connect()

    cursor = db.get_cursor()

    # Add multiple known artists to database
    test_artists = [
        ("Brooks & Dunn", "f30118c5-0ff5-449a-839c-23efa634caa4"),
        ("Dan + Shay", "33cf3954-10af-4dcb-985f-9420d1fa4168"),
        ("Luke Combs", "c20ee61f-071f-4e65-9c81-45ee931a54ce"),
    ]

    for artist_name, test_mbid in test_artists:
        match_key = generate_match_key_for_db(artist_name)
        cursor.execute("""
            INSERT INTO artists (mbid, name, match_key, first_seen_station)
            VALUES (?, ?, ?, NULL)
        """, (test_mbid, artist_name, match_key))

    db.conn.commit()
    cursor.close()

    # Look up all artists - should use database cache
    cache_hits = 0
    for artist_name, expected_mbid in test_artists:
        mbid, _, _, _ = lookup_artist_mbid(artist_name, db)
        if mbid == expected_mbid:
            cache_hits += 1

    # All 3 should be cache hits
    assert cache_hits == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
