"""
Pytest configuration and fixtures for Radio Monitor tests

Provides test database, Flask app, and HTTP client fixtures for testing
all components of the application.
"""

import pytest
import sqlite3
import tempfile
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from radio_monitor.database import RadioDatabase
from radio_monitor.gui import app as gui_app


@pytest.fixture
def test_db_path():
    """Provide a temporary database file path"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    # Cleanup
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@pytest.fixture
def test_db(test_db_path):
    """Provide an in-memory test database with schema initialized

    Returns a RadioDatabase instance with a fresh test database.
    The database is cleaned up after the test.
    """
    db = RadioDatabase(test_db_path)
    db.connect()  # This initializes the schema

    # Populate with test data
    cursor = db.get_cursor()
    # Add test station
    cursor.execute("""
        INSERT INTO stations (id, name, url, genre, market, enabled)
        VALUES ('test-station', 'Test Station', 'http://test.com', 'Test', 'Test', 1)
    """)
    # Add test artist
    cursor.execute("""
        INSERT INTO artists (mbid, name, first_seen_station, needs_lidarr_import)
        VALUES ('test-mbid-1', 'Test Artist', 'test-station', 0)
    """)
    # Add test song
    cursor.execute("""
        INSERT INTO songs (artist_mbid, artist_name, song_title, play_count)
        VALUES ('test-mbid-1', 'Test Artist', 'Test Song', 10)
    """)
    db.conn.commit()

    yield db

    # Cleanup
    db.conn.close()


@pytest.fixture
def test_app(test_db):
    """Provide a Flask test app with test database

    Returns a Flask app instance configured for testing.
    All routes are available and the database is isolated.
    """
    # Configure the existing app for testing
    gui_app.config['TESTING'] = True
    gui_app.config['DATABASE'] = test_db.db_path
    gui_app.config['SECRET_KEY'] = 'test-secret-key'
    gui_app.config['WTF_CSRF_ENABLED'] = False

    yield gui_app


@pytest.fixture
def test_client(test_app):
    """Provide a Flask test client for making HTTP requests

    Returns a Flask test client that can make requests to all routes.
    """
    return test_app.test_client()


@pytest.fixture
def test_notification(test_db):
    """Create a test notification in the database

    Returns the ID of the created notification.
    """
    import json
    cursor = test_db.get_cursor()
    cursor.execute("""
        INSERT INTO notifications (notification_type, name, enabled, config, triggers)
        VALUES (?, ?, ?, ?, ?)
    """, (
        'discord',
        'Test Discord Notification',
        0,  # Disabled for testing
        json.dumps({'webhook_url': 'http://test.com/webhook'}),
        json.dumps(['on_test_event'])
    ))
    test_db.conn.commit()
    return cursor.lastrowid


@pytest.fixture
def test_activity(test_db):
    """Create test activity log entries

    Creates a few test activity entries for testing queries.
    """
    cursor = test_db.get_cursor()
    cursor.execute("""
        INSERT INTO activity_log (event_type, event_severity, title, description, source)
        VALUES (?, ?, ?, ?, ?)
    """, ('test_event', 'info', 'Test Activity', 'Test description', 'system'))
    test_db.conn.commit()


@pytest.fixture
def authenticated_client(test_client):
    """Provide a test client with API key authentication

    Creates an API key and adds it to request headers.
    """
    # For now, just return the test client
    # TODO: Implement API key authentication in Phase 4
    yield test_client


@pytest.fixture
def sample_artists(test_db):
    """Create sample artists for testing pagination and filtering

    Creates 25 artists with different attributes.
    """
    cursor = test_db.get_cursor()
    for i in range(1, 26):
        needs_import = 1 if i % 3 == 0 else 0  # Every 3rd artist needs import
        cursor.execute("""
            INSERT INTO artists (mbid, name, first_seen_station, needs_lidarr_import)
            VALUES (?, ?, ?, ?)
        """, (f'test-mbid-{i}', f'Test Artist {i}', 'test-station', needs_import))
    test_db.conn.commit()


@pytest.fixture
def sample_songs(test_db):
    """Create sample songs for testing

    Creates 50 songs across 5 artists.
    """
    cursor = test_db.get_cursor()
    for artist_num in range(1, 6):
        artist_mbid = f'test-mbid-{artist_num}'
        for song_num in range(1, 11):
            cursor.execute("""
                INSERT INTO songs (artist_mbid, artist_name, song_title, play_count)
                VALUES (?, ?, ?, ?)
            """, (
                artist_mbid,
                f'Test Artist {artist_num}',
                f'Test Song {song_num}',
                song_num * 10  # Varying play counts
            ))
    test_db.conn.commit()


@pytest.fixture
def sample_plex_failures(test_db):
    """Create sample Plex failure records for testing

    Creates various types of failures.
    """
    cursor = test_db.get_cursor()
    # First get a song ID
    cursor.execute("SELECT id FROM songs LIMIT 1")
    result = cursor.fetchone()
    if result:
        song_id = result[0]

        failure_types = ['no_match', 'multiple_matches', 'plex_error']
        for failure_type in failure_types:
            cursor.execute("""
                INSERT INTO plex_match_failures
                (song_id, failure_reason, search_terms_used, resolved)
                VALUES (?, ?, ?, ?)
            """, (song_id, failure_type, '{"title": "Test"}', 0))
        test_db.conn.commit()


# Test data helper functions
def create_test_station_data():
    """Create test station data"""
    return {
        'id': 'test-station-2',
        'name': 'Test Station 2',
        'url': 'http://test2.com',
        'genre': 'Rock',
        'market': 'Chicago',
        'enabled': True
    }


def create_test_artist_data():
    """Create test artist data"""
    return {
        'mbid': 'new-test-mbid',
        'name': 'New Test Artist',
        'needs_lidarr_import': True
    }


def create_test_song_data(artist_mbid='test-mbid-1'):
    """Create test song data"""
    return {
        'artist_mbid': artist_mbid,
        'artist_name': 'Test Artist',
        'song_title': 'New Test Song',
        'play_count': 5
    }


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
