"""
Database operation tests

Tests all CRUD operations, pagination queries, activity logging,
and notification storage.
"""

import pytest
import json
from radio_monitor.database import crud, queries, activity, notifications as notif_db


@pytest.mark.unit
class TestDatabaseCRUD:
    """Test CRUD operations"""

    def test_create_station(self, test_db):
        """Test creating a new station"""
        station_data = {
            'id': 'new-station',
            'name': 'New Station',
            'url': 'http://new.com',
            'genre': 'Pop',
            'market': 'Chicago',
            'enabled': True
        }
        crud.create_station(test_db, station_data)

        # Verify station was created
        stations = queries.get_all_stations(test_db)
        assert len(stations) == 2  # 1 from fixture + 1 new
        assert any(s['id'] == 'new-station' for s in stations)

    def test_update_station(self, test_db):
        """Test updating an existing station"""
        crud.update_station(test_db, 'test-station', {'enabled': False})

        # Verify station was updated
        station = queries.get_station_detail(test_db, 'test-station')
        assert station is not None
        assert station['enabled'] == 0

    def test_create_artist(self, test_db):
        """Test creating a new artist"""
        artist_data = {
            'mbid': 'new-artist-mbid',
            'name': 'New Artist',
            'first_seen_station': 'test-station',
            'needs_lidarr_import': True
        }
        crud.create_artist(test_db, artist_data)

        # Verify artist was created
        artists = queries.get_all_artists(test_db)
        assert len(artists) == 2  # 1 from fixture + 1 new

    def test_create_song(self, test_db):
        """Test creating a new song"""
        song_data = {
            'artist_mbid': 'test-mbid-1',
            'artist_name': 'Test Artist',
            'song_title': 'New Song',
            'play_count': 1
        }
        crud.create_song(test_db, song_data)

        # Verify song was created
        songs = queries.get_all_songs(test_db)
        assert len(songs) == 2  # 1 from fixture + 1 new

    def test_delete_song(self, test_db):
        """Test deleting a song"""
        # Get the test song ID
        cursor = test_db.get_cursor()
        cursor.execute("SELECT id FROM songs LIMIT 1")
        result = cursor.fetchone()
        song_id = result[0] if result else None

        if song_id:
            crud.delete_song(test_db, song_id)

            # Verify song was deleted
            songs = queries.get_all_songs(test_db)
            assert len(songs) == 0


@pytest.mark.unit
class TestDatabaseQueries:
    """Test database queries"""

    def test_get_all_stations(self, test_db):
        """Test retrieving all stations"""
        stations = queries.get_all_stations(test_db)
        assert isinstance(stations, list)
        assert len(stations) >= 1
        assert stations[0]['id'] == 'test-station'

    def test_get_station_detail(self, test_db):
        """Test retrieving station detail"""
        station = queries.get_station_detail(test_db, 'test-station')
        assert station is not None
        assert station['name'] == 'Test Station'

    def test_get_all_artists(self, test_db):
        """Test retrieving all artists"""
        artists = queries.get_all_artists(test_db)
        assert isinstance(artists, list)
        assert len(artists) >= 1
        assert artists[0]['mbid'] == 'test-mbid-1'

    def test_get_artist_by_mbid(self, test_db):
        """Test retrieving artist by MBID"""
        artist = queries.get_artist_by_mbid(test_db, 'test-mbid-1')
        assert artist is not None
        assert artist['name'] == 'Test Artist'

    def test_get_all_songs(self, test_db):
        """Test retrieving all songs"""
        songs = queries.get_all_songs(test_db)
        assert isinstance(songs, list)
        assert len(songs) >= 1

    def test_get_song_by_id(self, test_db):
        """Test retrieving song by ID"""
        cursor = test_db.get_cursor()
        cursor.execute("SELECT id FROM songs LIMIT 1")
        result = cursor.fetchone()
        if result:
            song = queries.get_song_by_id(test_db, result[0])
            assert song is not None
            assert song['song_title'] == 'Test Song'


@pytest.mark.unit
class TestPagination:
    """Test pagination queries"""

    def test_get_artists_paginated(self, test_db, sample_artists):
        """Test paginated artist query"""
        # First page
        page1 = queries.get_artists_paginated(test_db, page=1, limit=10)
        assert len(page1['items']) == 10
        assert page1['total'] == 25  # From fixture
        assert page1['pages'] == 3

        # Second page
        page2 = queries.get_artists_paginated(test_db, page=2, limit=10)
        assert len(page2['items']) == 10

        # Last page
        page3 = queries.get_artists_paginated(test_db, page=3, limit=10)
        assert len(page3['items']) == 5

    def test_get_songs_paginated(self, test_db, sample_songs):
        """Test paginated song query"""
        page = queries.get_songs_paginated(test_db, page=1, limit=25)
        assert len(page['items']) == 25
        assert page['total'] == 50  # From fixture

    def test_pagination_filters(self, test_db, sample_artists):
        """Test pagination with filters"""
        # Filter by import status
        page = queries.get_artists_paginated(
            test_db,
            page=1,
            limit=10,
            filters={'needs_lidarr_import': 1}
        )
        # Every 3rd artist needs import, so ~8 out of 25
        assert len(page['items']) == 8

    def test_mbid_status_filter_pending(self, test_db, sample_artists):
        """Test mbid_status filter with 'pending' value"""
        # First, create some PENDING artists
        cursor = test_db.get_cursor()
        cursor.execute("""
            UPDATE artists
            SET mbid = 'PENDING-test-' || mbid
            WHERE rowid <= 5
        """)
        test_db.conn.commit()
        cursor.close()

        # Test pending filter
        page = queries.get_artists_paginated(
            test_db,
            page=1,
            limit=10,
            filters={'mbid_status': 'pending'}
        )

        # Should return only PENDING artists
        assert len(page['items']) == 5
        for artist in page['items']:
            assert artist['mbid'].startswith('PENDING-'), \
                f"Artist {artist['name']} has non-PENDING MBID: {artist['mbid']}"

    def test_mbid_status_filter_valid(self, test_db, sample_artists):
        """Test mbid_status filter with 'valid' value"""
        # First, create some PENDING artists
        cursor = test_db.get_cursor()
        cursor.execute("""
            UPDATE artists
            SET mbid = 'PENDING-test-' || mbid
            WHERE rowid <= 5
        """)
        test_db.conn.commit()
        cursor.close()

        # Test valid filter
        page = queries.get_artists_paginated(
            test_db,
            page=1,
            limit=50,
            filters={'mbid_status': 'valid'}
        )

        # Should return only non-PENDING, non-NULL artists
        assert len(page['items']) == 20  # 25 total - 5 PENDING
        for artist in page['items']:
            assert not artist['mbid'].startswith('PENDING-'), \
                f"Artist {artist['name']} has PENDING MBID: {artist['mbid']}"
            assert artist['mbid'] is not None, \
                f"Artist {artist['name']} has NULL MBID"

    def test_mbid_status_filter_none(self, test_db, sample_artists):
        """Test mbid_status filter with 'none' value"""
        # First, create some NULL mbid artists
        cursor = test_db.get_cursor()
        cursor.execute("""
            UPDATE artists
            SET mbid = NULL
            WHERE rowid <= 3
        """)
        test_db.conn.commit()
        cursor.close()

        # Test none filter
        page = queries.get_artists_paginated(
            test_db,
            page=1,
            limit=10,
            filters={'mbid_status': 'none'}
        )

        # Should return only NULL mbid artists
        assert len(page['items']) == 3
        for artist in page['items']:
            assert artist['mbid'] is None, \
                f"Artist {artist['name']} has non-NULL MBID: {artist['mbid']}"

    def test_mbid_status_filter_combined_with_search(self, test_db, sample_artists):
        """Test mbid_status filter combined with search filter"""
        # Create some PENDING artists
        cursor = test_db.get_cursor()
        cursor.execute("""
            UPDATE artists
            SET mbid = 'PENDING-test-' || mbid
            WHERE rowid <= 10
        """)
        test_db.conn.commit()
        cursor.close()

        # Test combined filter (PENDING + search)
        page = queries.get_artists_paginated(
            test_db,
            page=1,
            limit=10,
            filters={
                'mbid_status': 'pending',
                'search': 'Test'
            }
        )

        # Should return only PENDING artists with 'Test' in name
        assert len(page['items']) > 0
        for artist in page['items']:
            assert artist['mbid'].startswith('PENDING-'), \
                f"Artist {artist['name']} has non-PENDING MBID: {artist['mbid']}"
            assert 'Test' in artist['name'], \
                f"Artist {artist['name']} doesn't contain 'Test'"

    def test_mbid_status_filter_combined_with_station(self, test_db, sample_artists):
        """Test mbid_status filter combined with station filter"""
        # Create some PENDING artists from test-station
        cursor = test_db.get_cursor()
        cursor.execute("""
            UPDATE artists
            SET mbid = 'PENDING-test-' || mbid
            WHERE first_seen_station = 'test-station' AND rowid <= 5
        """)
        test_db.conn.commit()
        cursor.close()

        # Test combined filter (PENDING + station)
        page = queries.get_artists_paginated(
            test_db,
            page=1,
            limit=10,
            filters={
                'mbid_status': 'pending',
                'station_id': 'test-station'
            }
        )

        # Should return only PENDING artists from test-station
        assert len(page['items']) > 0
        for artist in page['items']:
            assert artist['mbid'].startswith('PENDING-'), \
                f"Artist {artist['name']} has non-PENDING MBID: {artist['mbid']}"
            assert artist['first_seen_station'] == 'test-station', \
                f"Artist {artist['name']} not from test-station"


@pytest.mark.unit
class TestActivityLogging:
    """Test activity logging system"""

    def test_log_activity(self, test_db):
        """Test logging an activity event"""
        activity.log_activity(
            test_db,
            event_type='test_event',
            title='Test Event',
            description='Test description',
            metadata={'key': 'value'}
        )

        # Verify activity was logged
        cursor = test_db.get_cursor()
        cursor.execute("SELECT COUNT(*) FROM activity_log WHERE event_type = 'test_event'")
        count = cursor.fetchone()[0]
        assert count > 0

    def test_get_activity_paginated(self, test_db):
        """Test retrieving paginated activity"""
        # Log some test activities
        for i in range(5):
            activity.log_activity(
                test_db,
                event_type='test',
                title=f'Test Event {i}',
                description=f'Description {i}'
            )

        # Get paginated results
        page = activity.get_activity_paginated(test_db, page=1, limit=3)
        assert len(page['items']) == 3

    def test_get_activity_stats(self, test_db):
        """Test activity statistics"""
        # Log different event types
        activity.log_activity(test_db, 'scrape', 'Scrape', 'Completed')
        activity.log_activity(test_db, 'import', 'Import', 'Completed')
        activity.log_activity(test_db, 'scrape', 'Scrape', 'Completed')

        stats = activity.get_activity_stats(test_db, days=1)
        assert 'by_type' in stats
        assert 'by_severity' in stats


@pytest.mark.unit
class TestNotifications:
    """Test notification storage"""

    def test_create_notification(self, test_db):
        """Test creating a notification"""
        config = {'webhook_url': 'http://test.com'}
        triggers = ['on_scrape_complete']

        notif_id = notif_db.add_notification(
            test_db,
            notification_type='discord',
            name='Test Notification',
            config=config,
            triggers=triggers
        )

        assert notif_id is not None
        assert isinstance(notif_id, int)

    def test_get_notifications(self, test_db, test_notification):
        """Test retrieving notifications"""
        notifications = notif_db.get_notifications(test_db)
        assert len(notifications) >= 1
        assert notifications[0]['name'] == 'Test Discord Notification'

    def test_update_notification(self, test_db, test_notification):
        """Test updating a notification"""
        notif_db.update_notification(
            test_db,
            test_notification,
            {'enabled': True}
        )

        notifications = notif_db.get_notifications(test_db)
        # Find the test notification
        test_notif = next(n for n in notifications if n['id'] == test_notification)
        assert test_notif['enabled'] == 1

    def test_delete_notification(self, test_db, test_notification):
        """Test deleting a notification"""
        notif_db.delete_notification(test_db, test_notification)

        notifications = notif_db.get_notifications(test_db)
        # Should be deleted
        assert not any(n['id'] == test_notification for n in notifications)

    def test_log_notification_history(self, test_db):
        """Test logging notification to history"""
        notif_db.log_notification_history(
            test_db,
            notification_id=1,
            event_type='test_event',
            title='Test',
            message='Test message',
            success=True
        )

        cursor = test_db.get_cursor()
        cursor.execute("SELECT COUNT(*) FROM notification_history")
        count = cursor.fetchone()[0]
        assert count > 0

    def test_get_notification_history(self, test_db):
        """Test retrieving notification history"""
        # Add some history entries
        for i in range(3):
            notif_db.log_notification_history(
                test_db,
                notification_id=1,
                event_type='test',
                title=f'Test {i}',
                message=f'Message {i}',
                success=True
            )

        history = notif_db.get_notification_history(test_db, limit=2)
        assert len(history) == 2

    def test_get_notification_stats(self, test_db):
        """Test notification statistics"""
        # Add some history
        notif_db.log_notification_history(
            test_db, 1, 'test', 'Test', 'Message', success=True
        )
        notif_db.log_notification_history(
            test_db, 1, 'test', 'Test', 'Message', success=False
        )

        stats = notif_db.get_notification_stats(test_db, days=1)
        assert stats['total'] >= 2
        assert stats['successful'] >= 1
        assert stats['failed'] >= 1


@pytest.mark.unit
class TestPlexFailures:
    """Test Plex failure tracking"""

    def test_log_plex_failure(self, test_db):
        """Test logging a Plex failure"""
        cursor = test_db.get_cursor()
        cursor.execute("SELECT id FROM songs LIMIT 1")
        result = cursor.fetchone()
        if result:
            from radio_monitor.database import plex_failures

            plex_failures.log_plex_failure(
                test_db,
                song_id=result[0],
                playlist_id=None,
                failure_reason='no_match',
                search_terms={'title': 'Test'}
            )

            # Verify failure was logged
            cursor.execute("SELECT COUNT(*) FROM plex_match_failures")
            count = cursor.fetchone()[0]
            assert count > 0

    def test_get_plex_failures_paginated(self, test_db, sample_plex_failures):
        """Test retrieving paginated Plex failures"""
        from radio_monitor.database import plex_failures

        page = plex_failures.get_plex_failures_paginated(test_db, page=1, limit=10)
        assert len(page['items']) >= 1

    def test_resolve_plex_failure(self, test_db, sample_plex_failures):
        """Test resolving a Plex failure"""
        from radio_monitor.database import plex_failures

        cursor = test_db.get_cursor()
        cursor.execute("SELECT id FROM plex_match_failures LIMIT 1")
        result = cursor.fetchone()
        if result:
            failure_id = result[0]
            plex_failures.resolve_plex_failure(test_db, failure_id)

            # Verify it was resolved
            cursor.execute("SELECT resolved FROM plex_match_failures WHERE id = ?", (failure_id,))
            resolved = cursor.fetchone()[0]
            assert resolved == 1

    def test_get_plex_failure_stats(self, test_db, sample_plex_failures):
        """Test Plex failure statistics"""
        from radio_monitor.database import plex_failures

        stats = plex_failures.get_plex_failure_stats(test_db)
        assert stats['total'] >= 1
        assert 'by_reason' in stats
