"""
Test database lookup by match_key functionality

Tests for the Phase 1 database-first lookup implementation.
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from radio_monitor.database import RadioDatabase
from radio_monitor.database.queries import get_artist_by_match_key
from radio_monitor.normalization import generate_match_key_for_db


def test_database_lookup_existing_artist():
    """Test lookup of existing artist"""
    # Create test database
    db_path = ":memory:"  # Use in-memory database for testing
    db = RadioDatabase(db_path)
    db.connect()

    cursor = db.get_cursor()

    # First, ensure artist exists
    artist_name = "Brooks & Dunn"
    match_key = generate_match_key_for_db(artist_name)

    # Add artist to database (NULL for first_seen_station to avoid FK constraint)
    cursor.execute("""
        INSERT INTO artists (mbid, name, match_key, first_seen_station)
        VALUES (?, ?, ?, NULL)
    """, ("f30118c5-test-mbid", artist_name, match_key))
    db.conn.commit()

    # Now test lookup
    result = get_artist_by_match_key(cursor, match_key)

    assert result is not None
    assert result['name'] == artist_name
    assert result['mbid'] == "f30118c5-test-mbid"
    assert result['match_key'] == match_key

    cursor.close()


def test_database_lookup_nonexistent_artist():
    """Test lookup of nonexistent artist"""
    db_path = ":memory:"
    db = RadioDatabase(db_path)
    db.connect()

    cursor = db.get_cursor()

    match_key = generate_match_key_for_db("Nonexistent Artist")

    result = get_artist_by_match_key(cursor, match_key)

    assert result is None

    cursor.close()


def test_database_lookup_pending_mbid():
    """Test lookup of artist with PENDING MBID"""
    db_path = ":memory:"
    db = RadioDatabase(db_path)
    db.connect()

    cursor = db.get_cursor()

    artist_name = "Test Artist"
    match_key = generate_match_key_for_db(artist_name)
    pending_mbid = "PENDING-test-uuid"

    # Add artist with PENDING MBID (NULL for first_seen_station)
    cursor.execute("""
        INSERT INTO artists (mbid, name, match_key, first_seen_station)
        VALUES (?, ?, ?, NULL)
    """, (pending_mbid, artist_name, match_key))
    db.conn.commit()

    result = get_artist_by_match_key(cursor, match_key)

    assert result is not None
    assert result['mbid'].startswith("PENDING-")
    assert result['mbid'] == pending_mbid

    cursor.close()


def test_database_radio_database_wrapper():
    """Test RadioDatabase.get_artist_by_match_key method"""
    db_path = ":memory:"
    db = RadioDatabase(db_path)
    db.connect()

    cursor = db.get_cursor()

    # Add test artist
    artist_name = "Dan + Shay"
    match_key = generate_match_key_for_db(artist_name)

    cursor.execute("""
        INSERT INTO artists (mbid, name, match_key, first_seen_station)
        VALUES (?, ?, ?, NULL)
    """, ("33cf3954-test-mbid", artist_name, match_key))
    db.conn.commit()

    cursor.close()

    # Test using RadioDatabase method
    result = db.get_artist_by_match_key(match_key)

    assert result is not None
    assert result['name'] == artist_name
    assert result['mbid'] == "33cf3954-test-mbid"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
