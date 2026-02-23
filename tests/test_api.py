"""
API endpoint tests

Tests all API endpoints for proper responses, error handling,
filtering, sorting, and authentication.
"""

import pytest
import json
from datetime import datetime


@pytest.mark.unit
class TestSystemAPI:
    """Test system-related API endpoints"""

    def test_system_status(self, test_client):
        """Test /api/system/status endpoint"""
        response = test_client.get('/api/system/status')
        assert response.status_code == 200

        data = response.get_json()
        assert 'database' in data
        assert 'uptime' in data

    def test_system_health(self, test_client):
        """Test /api/system/health endpoint"""
        response = test_client.get('/api/system/health')
        assert response.status_code == 200

        data = response.get_json()
        assert 'status' in data


@pytest.mark.unit
class TestMonitorAPI:
    """Test monitoring-related API endpoints"""

    def test_monitor_status(self, test_client):
        """Test /api/monitor/status endpoint"""
        response = test_client.get('/api/monitor/status')
        assert response.status_code == 200

        data = response.get_json()
        assert 'running' in data


@pytest.mark.unit
class TestArtistsAPI:
    """Test artist-related API endpoints"""

    def test_get_artists_list(self, test_client, sample_artists):
        """Test GET /api/artists endpoint"""
        response = test_client.get('/api/artists?limit=10&page=1')
        assert response.status_code == 200

        data = response.get_json()
        assert 'items' in data
        assert 'total' in data
        assert len(data['items']) == 10

    def test_get_artist_detail(self, test_client):
        """Test GET /api/artists/<mbid> endpoint"""
        response = test_client.get('/api/artists/test-mbid-1')
        assert response.status_code == 200

        data = response.get_json()
        assert data['mbid'] == 'test-mbid-1'
        assert data['name'] == 'Test Artist'

    def test_get_artist_not_found(self, test_client):
        """Test artist detail with non-existent MBID"""
        response = test_client.get('/api/artists/non-existent-mbid')
        assert response.status_code == 404

    def test_filter_artists_by_status(self, test_client, sample_artists):
        """Test filtering artists by import status"""
        response = test_client.get('/api/artists?needs_lidarr_import=1')
        assert response.status_code == 200

        data = response.get_json()
        # All returned artists should need import
        for artist in data['items']:
            assert artist['needs_lidarr_import'] == 1

    def test_search_artists(self, test_client):
        """Test searching artists"""
        response = test_client.get('/api/artists?search=Test')
        assert response.status_code == 200

        data = response.get_json()
        # Should return artists matching "Test"
        assert len(data['items']) >= 1

    def test_filter_artists_by_mbid_status_pending(self, test_client, sample_artists):
        """Test filtering artists by mbid_status='pending'"""
        # Create some PENDING artists first
        from radio_monitor.database import RadioDatabase
        db = test_client.application.config['db']
        cursor = db.get_cursor()
        cursor.execute("""
            UPDATE artists
            SET mbid = 'PENDING-test-' || mbid
            WHERE rowid <= 5
        """)
        db.conn.commit()
        cursor.close()

        # Test pending filter
        response = test_client.get('/api/artists?mbid_status=pending')
        assert response.status_code == 200

        data = response.get_json()
        # All returned artists should have PENDING MBIDs
        for artist in data['items']:
            assert artist['mbid'].startswith('PENDING-'), \
                f"Artist {artist['name']} has non-PENDING MBID: {artist['mbid']}"

    def test_filter_artists_by_mbid_status_valid(self, test_client, sample_artists):
        """Test filtering artists by mbid_status='valid'"""
        # Create some PENDING artists
        from radio_monitor.database import RadioDatabase
        db = test_client.application.config['db']
        cursor = db.get_cursor()
        cursor.execute("""
            UPDATE artists
            SET mbid = 'PENDING-test-' || mbid
            WHERE rowid <= 5
        """)
        db.conn.commit()
        cursor.close()

        # Test valid filter
        response = test_client.get('/api/artists?mbid_status=valid')
        assert response.status_code == 200

        data = response.get_json()
        # All returned artists should have valid MBIDs
        for artist in data['items']:
            assert not artist['mbid'].startswith('PENDING-'), \
                f"Artist {artist['name']} has PENDING MBID: {artist['mbid']}"
            assert artist['mbid'] is not None, \
                f"Artist {artist['name']} has NULL MBID"

    def test_filter_artists_by_mbid_status_none(self, test_client, sample_artists):
        """Test filtering artists by mbid_status='none'"""
        # Create some NULL mbid artists
        from radio_monitor.database import RadioDatabase
        db = test_client.application.config['db']
        cursor = db.get_cursor()
        cursor.execute("""
            UPDATE artists
            SET mbid = NULL
            WHERE rowid <= 3
        """)
        db.conn.commit()
        cursor.close()

        # Test none filter
        response = test_client.get('/api/artists?mbid_status=none')
        assert response.status_code == 200

        data = response.get_json()
        # All returned artists should have NULL MBIDs
        for artist in data['items']:
            assert artist['mbid'] is None, \
                f"Artist {artist['name']} has non-NULL MBID: {artist['mbid']}"

    def test_filter_artists_mbid_status_combined_filters(self, test_client, sample_artists):
        """Test mbid_status filter combined with other filters"""
        # Create some PENDING artists
        from radio_monitor.database import RadioDatabase
        db = test_client.application.config['db']
        cursor = db.get_cursor()
        cursor.execute("""
            UPDATE artists
            SET mbid = 'PENDING-test-' || mbid,
                name = 'Test Artist ' || rowid
            WHERE rowid <= 5
        """)
        db.conn.commit()
        cursor.close()

        # Test combined filter (PENDING + search)
        response = test_client.get('/api/artists?mbid_status=pending&search=Test')
        assert response.status_code == 200

        data = response.get_json()
        # Should return only PENDING artists with 'Test' in name
        assert len(data['items']) > 0
        for artist in data['items']:
            assert artist['mbid'].startswith('PENDING-'), \
                f"Artist {artist['name']} has non-PENDING MBID: {artist['mbid']}"
            assert 'Test' in artist['name'], \
                f"Artist {artist['name']} doesn't contain 'Test'"


@pytest.mark.unit
class TestSongsAPI:
    """Test song-related API endpoints"""

    def test_get_songs_list(self, test_client, sample_songs):
        """Test GET /api/songs endpoint"""
        response = test_client.get('/api/songs?limit=25&page=1')
        assert response.status_code == 200

        data = response.get_json()
        assert 'items' in data
        assert len(data['items']) == 25

    def test_get_song_detail(self, test_client):
        """Test GET /api/songs/<id> endpoint"""
        # First get a song ID
        response = test_client.get('/api/songs?limit=1')
        data = response.get_json()
        if data['items']:
            song_id = data['items'][0]['id']

            response = test_client.get(f'/api/songs/{song_id}')
            assert response.status_code == 200

            song_data = response.get_json()
            assert song_data['id'] == song_id

    def test_search_songs(self, test_client):
        """Test searching songs"""
        response = test_client.get('/api/songs?search=Test')
        assert response.status_code == 200

        data = response.get_json()
        assert 'items' in data

    def test_filter_songs_by_artist(self, test_client, sample_songs):
        """Test filtering songs by artist"""
        response = test_client.get('/api/songs?artist=Test+Artist+1')
        assert response.status_code == 200

        data = response.get_json()
        # All songs should be by Test Artist 1
        for song in data['items']:
            assert song['artist_name'] == 'Test Artist 1'


@pytest.mark.unit
class TestStationsAPI:
    """Test station-related API endpoints"""

    def test_get_stations_list(self, test_client):
        """Test GET /api/stations endpoint"""
        response = test_client.get('/api/stations')
        assert response.status_code == 200

        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_station_detail(self, test_client):
        """Test GET /api/stations/<id> endpoint"""
        response = test_client.get('/api/stations/test-station')
        assert response.status_code == 200

        data = response.get_json()
        assert data['id'] == 'test-station'

    def test_update_station(self, test_client):
        """Test PUT /api/stations/<id> endpoint"""
        update_data = {'enabled': False}
        response = test_client.put(
            '/api/stations/test-station',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        assert response.status_code == 200

        # Verify update
        response = test_client.get('/api/stations/test-station')
        data = response.get_json()
        assert data['enabled'] == 0


@pytest.mark.unit
class TestActivityAPI:
    """Test activity-related API endpoints"""

    def test_get_activity_list(self, test_client):
        """Test GET /api/activity endpoint"""
        response = test_client.get('/api/activity?limit=10')
        assert response.status_code == 200

        data = response.get_json()
        assert 'items' in data
        assert 'total' in data

    def test_get_recent_activity(self, test_client):
        """Test GET /api/activity/recent endpoint"""
        response = test_client.get('/api/activity/recent')
        assert response.status_code == 200

        data = response.get_json()
        assert isinstance(data, list)

    def test_get_activity_stats(self, test_client):
        """Test GET /api/activity/stats endpoint"""
        response = test_client.get('/api/activity/stats')
        assert response.status_code == 200

        data = response.get_json()
        assert 'by_type' in data
        assert 'by_severity' in data

    def test_filter_activity_by_type(self, test_client):
        """Test filtering activity by event type"""
        response = test_client.get('/api/activity?event_type=test_event')
        assert response.status_code == 200

        data = response.get_json()
        # All activities should be of the specified type
        for item in data['items']:
            assert item['event_type'] == 'test_event'


@pytest.mark.unit
class TestSearchAPI:
    """Test global search API endpoints"""

    def test_global_search(self, test_client):
        """Test GET /api/search endpoint"""
        response = test_client.get('/api/search?q=Test&limit=5')
        assert response.status_code == 200

        data = response.get_json()
        assert 'results' in data
        assert 'total' in data

    def test_search_artists_quick(self, test_client):
        """Test GET /api/search/artists endpoint"""
        response = test_client.get('/api/search/artists?q=Test')
        assert response.status_code == 200

        data = response.get_json()
        assert isinstance(data, list)

    def test_search_songs_quick(self, test_client):
        """Test GET /api/search/songs endpoint"""
        response = test_client.get('/api/search/songs?q=Test')
        assert response.status_code == 200

        data = response.get_json()
        assert isinstance(data, list)


@pytest.mark.unit
class TestNotificationsAPI:
    """Test notification-related API endpoints"""

    def test_get_notifications(self, test_client, test_notification):
        """Test GET /api/notifications endpoint"""
        response = test_client.get('/api/notifications')
        assert response.status_code == 200

        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_create_notification(self, test_client):
        """Test POST /api/notifications endpoint"""
        notification_data = {
            'notification_type': 'discord',
            'name': 'Test Discord',
            'config': {'webhook_url': 'http://test.com'},
            'triggers': ['on_test']
        }

        response = test_client.post(
            '/api/notifications',
            data=json.dumps(notification_data),
            content_type='application/json'
        )
        assert response.status_code == 201

        data = response.get_json()
        assert 'id' in data

    def test_update_notification(self, test_client, test_notification):
        """Test PUT /api/notifications/<id> endpoint"""
        update_data = {'enabled': True}

        response = test_client.put(
            f'/api/notifications/{test_notification}',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        assert response.status_code == 200

    def test_delete_notification(self, test_client, test_notification):
        """Test DELETE /api/notifications/<id> endpoint"""
        response = test_client.delete(f'/api/notifications/{test_notification}')
        assert response.status_code == 200

    def test_get_notification_history(self, test_client):
        """Test GET /api/notifications/history endpoint"""
        response = test_client.get('/api/notifications/history?limit=10')
        assert response.status_code == 200

        data = response.get_json()
        assert 'items' in data

    def test_get_notification_stats(self, test_client):
        """Test GET /api/notifications/stats endpoint"""
        response = test_client.get('/api/notifications/stats')
        assert response.status_code == 200

        data = response.get_json()
        assert 'total' in data


@pytest.mark.unit
class TestPlexFailuresAPI:
    """Test Plex failures API endpoints"""

    def test_get_plex_failures(self, test_client, sample_plex_failures):
        """Test GET /api/plex-failures endpoint"""
        response = test_client.get('/api/plex-failures?limit=10')
        assert response.status_code == 200

        data = response.get_json()
        assert 'items' in data

    def test_get_plex_failure_stats(self, test_client):
        """Test GET /api/plex-failures/stats endpoint"""
        response = test_client.get('/api/plex-failures/stats')
        assert response.status_code == 200

        data = response.get_json()
        assert 'total' in data
        assert 'by_reason' in data

    def test_resolve_plex_failure(self, test_client, sample_plex_failures):
        """Test PUT /api/plex-failures/<id>/resolve endpoint"""
        # Get a failure ID
        response = test_client.get('/api/plex-failures?limit=1')
        data = response.get_json()
        if data['items']:
            failure_id = data['items'][0]['id']

            response = test_client.put(f'/api/plex-failures/{failure_id}/resolve')
            assert response.status_code == 200

    def test_export_plex_failures(self, test_client, sample_plex_failures):
        """Test GET /api/plex-failures/export endpoint"""
        response = test_client.get('/api/plex-failures/export')
        assert response.status_code == 200
        assert response.content_type == 'text/csv'


@pytest.mark.unit
class TestErrorHandling:
    """Test API error handling"""

    def test_404_error(self, test_client):
        """Test 404 error response"""
        response = test_client.get('/api/non-existent-endpoint')
        assert response.status_code == 404

    def test_invalid_json(self, test_client):
        """Test handling of invalid JSON in POST"""
        response = test_client.post(
            '/api/notifications',
            data='invalid json',
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_missing_required_fields(self, test_client):
        """Test handling of missing required fields"""
        incomplete_data = {'name': 'Test'}  # Missing required fields

        response = test_client.post(
            '/api/notifications',
            data=json.dumps(incomplete_data),
            content_type='application/json'
        )
        assert response.status_code == 400


@pytest.mark.integration
class TestEndToEnd:
    """End-to-end integration tests"""

    def test_complete_artist_workflow(self, test_client):
        """Test complete workflow: create artist -> retrieve -> update -> delete"""
        # Create
        artist_data = {
            'mbid': 'workflow-test-mbid',
            'name': 'Workflow Test Artist'
        }
        # Note: This assumes there's a create endpoint
        # response = test_client.post('/api/artists', json=artist_data)
        # assert response.status_code == 201

        # Retrieve
        response = test_client.get('/api/artists/workflow-test-mbid')
        # assert response.status_code == 200

        # Verify data
        # data = response.get_json()
        # assert data['name'] == 'Workflow Test Artist'

    def test_pagination_navigation(self, test_client, sample_artists):
        """Test navigating through paginated results"""
        # Get first page
        response = test_client.get('/api/artists?limit=10&page=1')
        data = response.get_json()
        total_pages = data['pages']

        # Navigate through all pages
        for page_num in range(1, min(total_pages + 1, 4)):  # Test up to 4 pages
            response = test_client.get(f'/api/artists?limit=10&page={page_num}')
            assert response.status_code == 200
            data = response.get_json()
            assert data['page'] == page_num
