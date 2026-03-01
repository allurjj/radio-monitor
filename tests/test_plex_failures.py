"""
Plex failure tracking tests

Tests Plex failure logging, retry logic, export functionality,
and failure analysis.
"""

import pytest
import csv
from io import StringIO
from radio_monitor.database import plex_failures


@pytest.mark.unit
class TestPlexFailureLogging:
    """Test Plex failure logging functionality"""

    def test_log_failure(self, test_db):
        """Test logging a Plex match failure"""
        # Get a song ID
        cursor = test_db.get_cursor()
        cursor.execute("SELECT id FROM songs LIMIT 1")
        result = cursor.fetchone()
        if result:
            song_id = result[0]

            # Log failure
            failure_id = plex_failures.log_plex_failure(
                test_db,
                song_id=song_id,
                playlist_id=None,
                failure_reason='no_match',
                search_terms={'title': 'Test Song', 'artist': 'Test Artist'}
            )

            assert failure_id is not None
            assert isinstance(failure_id, int)

            # Verify in database
            cursor.execute("SELECT * FROM plex_match_failures WHERE id = ?", (failure_id,))
            failure = cursor.fetchone()
            assert failure is not None

    def test_log_failure_with_playlist(self, test_db):
        """Test logging a failure with playlist context"""
        # First create a playlist
        cursor = test_db.get_cursor()
        cursor.execute("""
            INSERT INTO playlists (name, is_auto, station_ids, max_songs, mode)
            VALUES ('Test Playlist', 1, '["test-station"]', 100, 'top')
        """)
        playlist_id = cursor.lastrowid

        # Get a song ID
        cursor.execute("SELECT id FROM songs LIMIT 1")
        result = cursor.fetchone()
        if result:
            song_id = result[0]

            # Log failure with playlist
            failure_id = plex_failures.log_plex_failure(
                test_db,
                song_id=song_id,
                playlist_id=playlist_id,
                failure_reason='multiple_matches',
                search_terms={'query': 'test'}
            )

            # Verify playlist ID was saved
            cursor.execute(
                "SELECT playlist_id FROM plex_match_failures WHERE id = ?",
                (failure_id,)
            )
            playlist_id_result = cursor.fetchone()[0]
            assert playlist_id_result == playlist_id

    def test_log_different_failure_types(self, test_db):
        """Test logging different types of failures"""
        cursor = test_db.get_cursor()
        cursor.execute("SELECT id FROM songs LIMIT 1")
        result = cursor.fetchone()
        if result:
            song_id = result[0]

            failure_types = [
                'no_match',
                'multiple_matches',
                'plex_error'
            ]

            for failure_type in failure_types:
                failure_id = plex_failures.log_plex_failure(
                    test_db,
                    song_id=song_id,
                    playlist_id=None,
                    failure_reason=failure_type,
                    search_terms={}
                )
                assert failure_id is not None

            # Verify all were logged
            cursor.execute("SELECT COUNT(*) FROM plex_match_failures")
            count = cursor.fetchone()[0]
            assert count == len(failure_types)


@pytest.mark.unit
class TestPlexFailureRetrieval:
    """Test Plex failure retrieval and querying"""

    def test_get_failures_paginated(self, test_db, sample_plex_failures):
        """Test retrieving paginated failures"""
        page = plex_failures.get_plex_failures_paginated(
            test_db,
            page=1,
            limit=10
        )

        assert 'items' in page
        assert 'total' in page
        assert 'pages' in page
        assert isinstance(page['items'], list)

    def test_filter_failures_by_reason(self, test_db, sample_plex_failures):
        """Test filtering failures by reason"""
        page = plex_failures.get_plex_failures_paginated(
            test_db,
            page=1,
            limit=10,
            filters={'failure_reason': 'no_match'}
        )

        # All failures should have the specified reason
        for failure in page['items']:
            assert failure['failure_reason'] == 'no_match'

    def test_filter_failures_by_resolved_status(self, test_db, sample_plex_failures):
        """Test filtering failures by resolved status"""
        # Get unresolved failures
        page_unresolved = plex_failures.get_plex_failures_paginated(
            test_db,
            page=1,
            limit=10,
            filters={'resolved': False}
        )

        # All should be unresolved
        for failure in page_unresolved['items']:
            assert failure['resolved'] == 0

    def test_filter_failures_by_playlist(self, test_db):
        """Test filtering failures by playlist"""
        # Create a playlist and failures
        cursor = test_db.get_cursor()
        cursor.execute("""
            INSERT INTO playlists (name, is_auto, station_ids, max_songs, mode)
            VALUES ('Test Playlist', 1, '["test-station"]', 100, 'top')
        """)
        playlist_id = cursor.lastrowid

        cursor.execute("SELECT id FROM songs LIMIT 1")
        result = cursor.fetchone()
        if result:
            # Log a failure for this playlist
            plex_failures.log_plex_failure(
                test_db,
                song_id=result[0],
                playlist_id=playlist_id,
                failure_reason='no_match',
                search_terms={}
            )

            # Get failures for this playlist
            page = plex_failures.get_plex_failures_paginated(
                test_db,
                page=1,
                limit=10,
                filters={'playlist_id': playlist_id}
            )

            # All failures should be for this playlist
            for failure in page['items']:
                assert failure['playlist_id'] == playlist_id


@pytest.mark.unit
class TestPlexFailureResolution:
    """Test Plex failure resolution and retry logic"""

    def test_resolve_failure(self, test_db, sample_plex_failures):
        """Test marking a failure as resolved"""
        cursor = test_db.get_cursor()
        cursor.execute("SELECT id FROM plex_match_failures LIMIT 1")
        result = cursor.fetchone()
        if result:
            failure_id = result[0]

            # Resolve the failure
            plex_failures.resolve_plex_failure(test_db, failure_id)

            # Verify it's resolved
            cursor.execute(
                "SELECT resolved, resolved_at FROM plex_match_failures WHERE id = ?",
                (failure_id,)
            )
            resolved, resolved_at = cursor.fetchone()
            assert resolved == 1
            assert resolved_at is not None

    def test_bulk_resolve_failures(self, test_db, sample_plex_failures):
        """Test resolving multiple failures at once"""
        # Get failure IDs
        cursor = test_db.get_cursor()
        cursor.execute("SELECT id FROM plex_match_failures")
        failure_ids = [row[0] for row in cursor.fetchall()]

        if failure_ids:
            # Resolve all
            resolved_count = plex_failures.bulk_resolve_failures(test_db, failure_ids)

            # Verify all are resolved
            cursor.execute(
                "SELECT COUNT(*) FROM plex_match_failures WHERE resolved = 1"
            )
            count = cursor.fetchone()[0]
            assert count == len(failure_ids)

    def test_retry_failure(self, test_db):
        """Test retrying a failed Plex match"""
        # This would typically call Plex matching logic again
        # For now, just test the function exists and handles the attempt

        cursor = test_db.get_cursor()
        cursor.execute("SELECT id FROM plex_match_failures LIMIT 1")
        result = cursor.fetchone()
        if result:
            failure_id = result[0]

            # Mock the Plex retry
            # In real implementation, this would retry the Plex match
            with patch('radio_monitor.plex.match_song_in_plex') as mock_match:
                mock_match.return_value = {'matched': True, 'rating_key': 123}

                result = plex_failures.retry_plex_failure(test_db, failure_id)
                # Verify based on your implementation


@pytest.mark.unit
class TestPlexFailureStatistics:
    """Test Plex failure statistics and analysis"""

    def test_get_failure_stats(self, test_db, sample_plex_failures):
        """Test getting failure statistics"""
        stats = plex_failures.get_plex_failure_stats(test_db)

        assert 'total' in stats
        assert 'by_reason' in stats
        assert 'resolved' in stats
        assert 'unresolved' in stats
        assert stats['total'] >= 1

    def test_failure_breakdown_by_reason(self, test_db, sample_plex_failures):
        """Test failure breakdown by reason"""
        stats = plex_failures.get_plex_failure_stats(test_db)

        by_reason = stats['by_reason']
        # Should have all our test failure types
        assert 'no_match' in by_reason
        assert 'multiple_matches' in by_reason
        assert 'plex_error' in by_reason

    def test_failure_rate_by_playlist(self, test_db):
        """Test failure rate per playlist"""
        # Create playlist and add failures
        cursor = test_db.get_cursor()
        cursor.execute("""
            INSERT INTO playlists (name, is_auto, station_ids, max_songs, mode)
            VALUES ('Test Playlist', 1, '["test-station"]', 100, 'top')
        """)
        playlist_id = cursor.lastrowid

        cursor.execute("SELECT id FROM songs LIMIT 1")
        result = cursor.fetchone()
        if result:
            # Log some failures
            for _ in range(3):
                plex_failures.log_plex_failure(
                    test_db,
                    song_id=result[0],
                    playlist_id=playlist_id,
                    failure_reason='no_match',
                    search_terms={}
                )

            # Get playlist stats
            stats = plex_failures.get_playlist_failure_stats(test_db, playlist_id)
            assert stats['total_failures'] == 3


@pytest.mark.unit
class TestPlexFailureExport:
    """Test Plex failure export functionality"""

    def test_export_to_csv(self, test_db, sample_plex_failures):
        """Test exporting failures to CSV"""
        csv_data = plex_failures.export_failures_to_csv(test_db)

        # Parse CSV
        reader = csv.DictReader(StringIO(csv_data))
        rows = list(reader)

        assert len(rows) >= 1
        # Verify headers
        assert 'id' in rows[0]
        assert 'song_id' in rows[0]
        assert 'failure_reason' in rows[0]
        assert 'failure_date' in rows[0]

    def test_export_filtered_failures(self, test_db):
        """Test exporting only filtered failures"""
        # Create specific failure
        cursor = test_db.get_cursor()
        cursor.execute("SELECT id FROM songs LIMIT 1")
        result = cursor.fetchone()
        if result:
            plex_failures.log_plex_failure(
                test_db,
                song_id=result[0],
                playlist_id=None,
                failure_reason='no_match',
                search_terms={}
            )

        # Export only 'no_match' failures
        # Note: This depends on your implementation
        # csv_data = plex_failures.export_failures_to_csv(
        #     test_db,
        #     filters={'failure_reason': 'no_match'}
        # )


@pytest.mark.integration
class TestPlexFailureIntegration:
    """Integration tests for Plex failure system"""

    def test_complete_failure_workflow(self, test_db):
        """Test complete workflow: log -> retrieve -> resolve -> export"""
        # 1. Create a song and playlist
        cursor = test_db.get_cursor()
        cursor.execute("""
            INSERT INTO songs (artist_mbid, artist_name, song_title)
            VALUES ('test-mbid', 'Test Artist', 'Test Song')
        """)
        song_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO playlists (name, is_auto, station_ids, max_songs, mode)
            VALUES ('Test Playlist', 1, '["test-station"]', 100, 'top')
        """)
        playlist_id = cursor.lastrowid

        # 2. Log failure
        failure_id = plex_failures.log_plex_failure(
            test_db,
            song_id=song_id,
            playlist_id=playlist_id,
            failure_reason='no_match',
            search_terms={'title': 'Test Song'}
        )

        # 3. Retrieve failure
        failures = plex_failures.get_plex_failures_paginated(test_db, page=1, limit=10)
        assert len(failures['items']) >= 1

        # 4. Resolve failure
        plex_failures.resolve_plex_failure(test_db, failure_id)

        # 5. Verify resolved
        cursor.execute("SELECT resolved FROM plex_match_failures WHERE id = ?", (failure_id,))
        resolved = cursor.fetchone()[0]
        assert resolved == 1

        # 6. Export
        csv_data = plex_failures.export_failures_to_csv(test_db)
        assert len(csv_data) > 0

    def test_failure_cleanup_old_entries(self, test_db):
        """Test cleaning up old failure entries"""
        # This would test cleanup of old resolved failures
        # Implementation depends on your cleanup strategy
        pass
