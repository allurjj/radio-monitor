#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 8 Testing Script - Manual Playlist Builder

Comprehensive testing for all phases of the manual playlist builder.
Tests selection persistence, performance, edge cases, and error handling.
"""

import sys
import os
import json
import time
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from radio_monitor.database import RadioDatabase
from radio_monitor.database.queries import (
    get_builder_state_song_ids,
    get_songs_paginated,
    get_artists_paginated,
    get_manual_playlist
)
from radio_monitor.database.crud import (
    create_manual_playlist,
    update_manual_playlist,
    delete_manual_playlist
)


class Phase8Tester:
    """Comprehensive test suite for Phase 8"""

    def __init__(self):
        self.db_path = project_root / "radio_songs.db"
        self.test_results = []
        self.test_session_id = "TEST_SESSION_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        self.db = None
        self._init_database()

    def _init_database(self):
        """Initialize database connection"""
        try:
            self.db = RadioDatabase(str(self.db_path))
            self.db.connect()  # CRITICAL: Must call connect() to initialize conn
            print(f"Database connected: {self.db_path}")
        except Exception as e:
            print(f"Error initializing database: {e}")
            self.db = None

    def log_test(self, test_name, passed, message, duration_ms=0):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        result = {
            'test': test_name,
            'passed': passed,
            'message': message,
            'duration_ms': duration_ms,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        print(f"{status}: {test_name}")
        if message:
            print(f"   {message}")
        if duration_ms > 0:
            print(f"   Duration: {duration_ms:.2f}ms")

    def test_8_1_selection_persistence(self):
        """Test 8.1: Selection persistence across pagination and operations"""
        print("\n" + "="*80)
        print("TEST 8.1: Selection Persistence")
        print("="*80)

        db = self.db
        if not db:
            self.log_test("Database Connection", False, "Database not initialized")
            return

        cursor = db.get_cursor()

        try:
            # Test 1.1: Get songs for testing
            start_time = time.time()
            cursor.execute("SELECT id FROM songs LIMIT 20")
            song_ids = [row[0] for row in cursor.fetchall()]
            duration = (time.time() - start_time) * 1000

            if len(song_ids) < 10:
                self.log_test("Get Test Songs", False, f"Only {len(song_ids)} songs in database")
                return

            self.log_test("Get Test Songs", True, f"Found {len(song_ids)} songs", duration)

            # Test 1.2: Select 10 songs
            start_time = time.time()
            first_10 = song_ids[:10]

            # Clear any existing selections for test session
            cursor.execute("""
                DELETE FROM playlist_builder_state
                WHERE session_id = ?
            """, (self.test_session_id,))

            # Add selections
            for song_id in first_10:
                cursor.execute("""
                    INSERT INTO playlist_builder_state (session_id, song_id, created_at)
                    VALUES (?, ?, ?)
                """, (self.test_session_id, song_id, datetime.now().isoformat()))

            db.conn.commit()
            duration = (time.time() - start_time) * 1000

            self.log_test("Select 10 Songs", True, f"Inserted {len(first_10)} selections", duration)

            # Test 1.3: Verify selections persist
            start_time = time.time()
            selections = get_builder_state_song_ids(cursor, self.test_session_id)
            duration = (time.time() - start_time) * 1000

            if len(selections) != 10:
                self.log_test("Verify Selections Persist", False,
                            f"Expected 10, got {len(selections)}")
                return

            self.log_test("Verify Selections Persist", True,
                        f"All 10 selections found", duration)

            # Test 1.4: Toggle selection (remove 5)
            start_time = time.time()
            for song_id in first_10[:5]:
                cursor.execute("""
                    DELETE FROM playlist_builder_state
                    WHERE session_id = ? AND song_id = ?
                """, (self.test_session_id, song_id))

            db.conn.commit()
            duration = (time.time() - start_time) * 1000

            self.log_test("Toggle Selection (Remove 5)", True,
                        f"Removed 5 selections", duration)

            # Test 1.5: Verify 5 remain
            start_time = time.time()
            selections = get_builder_state_song_ids(cursor, self.test_session_id)
            duration = (time.time() - start_time) * 1000

            if len(selections) != 5:
                self.log_test("Verify 5 Remain", False,
                            f"Expected 5, got {len(selections)}")
                return

            self.log_test("Verify 5 Remain", True, f"Correct count", duration)

            # Test 1.6: Clear all selections
            start_time = time.time()
            cursor.execute("""
                DELETE FROM playlist_builder_state
                WHERE session_id = ?
            """, (self.test_session_id,))
            db.conn.commit()
            duration = (time.time() - start_time) * 1000

            self.log_test("Clear All Selections", True, "All selections removed", duration)

            # Test 1.7: Verify empty
            start_time = time.time()
            selections = get_builder_state_song_ids(cursor, self.test_session_id)
            duration = (time.time() - start_time) * 1000

            if len(selections) != 0:
                self.log_test("Verify Empty", False,
                            f"Expected 0, got {len(selections)}")
                return

            self.log_test("Verify Empty", True, "All selections cleared", duration)

        finally:
            cursor.close()

    def test_8_2_performance(self):
        """Test 8.2: Performance testing with large datasets"""
        print("\n" + "="*80)
        print("TEST 8.2: Performance Testing")
        print("="*80)

        db = self.db
        if not db:
            self.log_test("Database Connection", False, "Database not initialized")
            return

        cursor = db.get_cursor()

        try:
            # Test 2.1: Large selection (500 songs)
            start_time = time.time()
            cursor.execute("SELECT id FROM songs LIMIT 500")
            song_ids = [row[0] for row in cursor.fetchall()]

            if len(song_ids) < 500:
                self.log_test("Get 500 Songs", True,
                            f"Only {len(song_ids)} songs available (test limited)")
                test_count = len(song_ids)
            else:
                test_count = 500
                self.log_test("Get 500 Songs", True, f"Found {test_count} songs")

            # Measure batch insert performance
            start_time = time.time()

            # Clear test session
            cursor.execute("""
                DELETE FROM playlist_builder_state
                WHERE session_id = ?
            """, (self.test_session_id,))

            # Batch insert
            for song_id in song_ids[:test_count]:
                cursor.execute("""
                    INSERT INTO playlist_builder_state (session_id, song_id, created_at)
                    VALUES (?, ?, ?)
                """, (self.test_session_id, song_id, datetime.now().isoformat()))

            db.conn.commit()
            duration = (time.time() - start_time) * 1000

            avg_per_song = duration / test_count

            if duration > 5000:  # 5 seconds threshold
                self.log_test("Large Selection (500 songs)", False,
                            f"Too slow: {duration:.2f}ms ({avg_per_song:.2f}ms per song)")
            else:
                self.log_test("Large Selection (500 songs)", True,
                            f"{duration:.2f}ms total ({avg_per_song:.2f}ms per song)", duration)

            # Test 2.2: Query performance
            start_time = time.time()
            selections = get_builder_state_song_ids(cursor, self.test_session_id)
            duration = (time.time() - start_time) * 1000

            if duration > 1000:  # 1 second threshold
                self.log_test("Query Selections Performance", False,
                            f"Too slow: {duration:.2f}ms")
            else:
                self.log_test("Query Selections Performance", True,
                            f"{duration:.2f}ms for {len(selections)} selections", duration)

            # Test 2.3: Pagination performance (By Artist view)
            start_time = time.time()
            artists = get_artists_paginated(
                cursor,
                page=1,
                limit=50,
                filters={}
            )
            duration = (time.time() - start_time) * 1000

            if duration > 2000:  # 2 seconds threshold
                self.log_test("Pagination Performance (By Artist)", False,
                            f"Too slow: {duration:.2f}ms")
            else:
                self.log_test("Pagination Performance (By Artist)", True,
                            f"{duration:.2f}ms for page 1", duration)

            # Test 2.4: Pagination performance (By Song view)
            start_time = time.time()
            songs = get_songs_paginated(
                cursor,
                page=1,
                limit=50,
                filters={}
            )
            duration = (time.time() - start_time) * 1000

            if duration > 2000:  # 2 seconds threshold
                self.log_test("Pagination Performance (By Song)", False,
                            f"Too slow: {duration:.2f}ms")
            else:
                self.log_test("Pagination Performance (By Song)", True,
                            f"{duration:.2f}ms for page 1", duration)

            # Cleanup
            cursor.execute("""
                DELETE FROM playlist_builder_state
                WHERE session_id = ?
            """, (self.test_session_id,))
            db.conn.commit()

        finally:
            cursor.close()

    def test_8_3_edge_cases(self):
        """Test 8.3: Edge case handling"""
        print("\n" + "="*80)
        print("TEST 8.3: Edge Case Testing")
        print("="*80)

        db = self.db
        if not db:
            self.log_test("Database Connection", False, "Database not initialized")
            return

        cursor = db.get_cursor()

        try:
            # Test 3.1: Empty selection handling
            start_time = time.time()
            cursor.execute("""
                DELETE FROM playlist_builder_state
                WHERE session_id = ?
            """, (self.test_session_id,))

            selections = get_builder_state_song_ids(cursor, self.test_session_id)
            duration = (time.time() - start_time) * 1000

            if len(selections) != 0:
                self.log_test("Empty Selection", False, f"Expected 0, got {len(selections)}")
            else:
                self.log_test("Empty Selection", True, "Returns empty list", duration)

            # Test 3.2: Special characters in playlist name
            start_time = time.time()

            # Get some song IDs
            cursor.execute("SELECT id FROM songs LIMIT 5")
            song_ids = [row[0] for row in cursor.fetchall()]

            # Create playlist with special characters
            special_name = "Test's Playlist & More! - SpecialChars: @#$%"
            playlist_id = create_manual_playlist(
                cursor,
                db.conn,
                name=special_name,
                plex_playlist_name=special_name
            )

            # Add songs using CRUD function
            from radio_monitor.database.crud import add_song_to_manual_playlist
            for song_id in song_ids:
                add_song_to_manual_playlist(cursor, db.conn, playlist_id, song_id)
            duration = (time.time() - start_time) * 1000

            # Verify
            playlist = get_manual_playlist(cursor, playlist_id)
            if playlist and playlist['name'] == special_name:
                self.log_test("Special Characters in Name", True,
                            f"Saved correctly: {special_name[:30]}...", duration)
            else:
                self.log_test("Special Characters in Name", False,
                            "Name not saved correctly")

            # Test 3.3: Very long playlist name
            start_time = time.time()
            long_name = "A" * 200

            playlist_id2 = create_manual_playlist(
                cursor,
                db.conn,
                name=long_name,
                plex_playlist_name=long_name
            )

            playlist = get_manual_playlist(cursor, playlist_id2)
            duration = (time.time() - start_time) * 1000

            if playlist and len(playlist['name']) == 200:
                self.log_test("Very Long Name (200 chars)", True,
                            f"Saved full length: {len(playlist['name'])} chars", duration)
            else:
                self.log_test("Very Long Name (200 chars)", False,
                            f"Truncated to {len(playlist['name']) if playlist else 0} chars")

            # Test 3.4: Duplicate playlist names (should allow)
            start_time = time.time()
            duplicate_name = "Duplicate Test Playlist"

            pid1 = create_manual_playlist(cursor, db.connection, name=duplicate_name)
            pid2 = create_manual_playlist(cursor, db.connection, name=duplicate_name)

            db.conn.commit()
            duration = (time.time() - start_time) * 1000

            if pid1 and pid2 and pid1 != pid2:
                self.log_test("Duplicate Playlist Names", True,
                            f"Allowed: {pid1} != {pid2}", duration)
            else:
                self.log_test("Duplicate Playlist Names", False,
                            "Should allow duplicates")

            # Cleanup test playlists
            cursor.execute("""
                DELETE FROM manual_playlists
                WHERE name LIKE 'Test%' OR name LIKE 'Duplicate%'
                OR name LIKE 'A%A%A%A%A%A%A%A%A%A%'
            """)
            cursor.execute("DELETE FROM manual_playlist_songs WHERE playlist_id NOT IN (SELECT id FROM manual_playlists)")
            db.conn.commit()

        finally:
            cursor.close()

    def test_8_4_database_operations(self):
        """Test 8.4: Database CRUD operations"""
        print("\n" + "="*80)
        print("TEST 8.4: Database CRUD Operations")
        print("="*80)

        db = self.db
        if not db:
            self.log_test("Database Connection", False, "Database not initialized")
            return

        cursor = db.get_cursor()

        try:
            # Test 4.1: Create playlist
            start_time = time.time()
            cursor.execute("SELECT id FROM songs LIMIT 3")
            song_ids = [row[0] for row in cursor.fetchall()]

            playlist_id = create_manual_playlist(
                cursor,
                db.conn,
                name="Test CRUD Playlist",
                plex_playlist_name="Plex CRUD Playlist"
            )

            for song_id in song_ids:
                cursor.execute("""
                    INSERT INTO manual_playlist_songs (playlist_id, song_id, added_at)
                    VALUES (?, ?, ?)
                """, (playlist_id, song_id, datetime.now().isoformat()))

            db.conn.commit()
            duration = (time.time() - start_time) * 1000

            self.log_test("Create Playlist", True,
                        f"Created playlist {playlist_id} with 3 songs", duration)

            # Test 4.2: Read playlist
            start_time = time.time()
            playlist = get_manual_playlist(cursor, playlist_id)
            duration = (time.time() - start_time) * 1000

            if playlist and playlist['name'] == "Test CRUD Playlist":
                self.log_test("Read Playlist", True,
                            f"Retrieved: {playlist['name']}", duration)
            else:
                self.log_test("Read Playlist", False, "Not found or incorrect")

            # Test 4.3: Update playlist
            start_time = time.time()
            update_manual_playlist(
                cursor,
                db.conn,
                playlist_id=playlist_id,
                name="Updated CRUD Playlist",
                plex_playlist_name="Updated Plex Playlist"
            )

            playlist = get_manual_playlist(cursor, playlist_id)
            duration = (time.time() - start_time) * 1000

            if playlist and playlist['name'] == "Updated CRUD Playlist":
                self.log_test("Update Playlist", True,
                            f"Name updated to: {playlist['name']}", duration)
            else:
                self.log_test("Update Playlist", False, "Update failed")

            # Test 4.4: Delete playlist
            start_time = time.time()
            delete_manual_playlist(cursor, db.connection, playlist_id)

            playlist = get_manual_playlist(cursor, playlist_id)
            duration = (time.time() - start_time) * 1000

            if playlist is None:
                self.log_test("Delete Playlist", True, "Playlist removed", duration)
            else:
                self.log_test("Delete Playlist", False, "Still exists")

        finally:
            cursor.close()

    def test_8_5_concurrent_sessions(self):
        """Test 8.5: Concurrent session isolation"""
        print("\n" + "="*80)
        print("TEST 8.5: Concurrent Session Isolation")
        print("="*80)

        db = self.db
        if not db:
            self.log_test("Database Connection", False, "Database not initialized")
            return

        cursor = db.get_cursor()

        try:
            # Test 5.1: Create two sessions
            session1 = "TEST_SESSION_1"
            session2 = "TEST_SESSION_2"

            # Get songs
            cursor.execute("SELECT id FROM songs LIMIT 10")
            song_ids = [row[0] for row in cursor.fetchall()]

            # Session 1: Select first 5
            for song_id in song_ids[:5]:
                cursor.execute("""
                    INSERT INTO playlist_builder_state (session_id, song_id, selected_at)
                    VALUES (?, ?, ?)
                """, (session1, song_id, datetime.now().isoformat()))

            # Session 2: Select last 5
            for song_id in song_ids[5:]:
                cursor.execute("""
                    INSERT INTO playlist_builder_state (session_id, song_id, selected_at)
                    VALUES (?, ?, ?)
                """, (session2, song_id, datetime.now().isoformat()))

            db.conn.commit()

            # Verify sessions don't interfere
            selections1 = get_builder_state_song_ids(cursor, session1)
            selections2 = get_builder_state_song_ids(cursor, session2)

            if len(selections1) == 5 and len(selections2) == 5:
                # Check for overlap
                ids1 = set(selections1)
                ids2 = set(selections2)

                if ids1.isdisjoint(ids2):
                    self.log_test("Session Isolation", True,
                                f"Session1: {len(selections1)}, Session2: {len(selections2)}, No overlap")
                else:
                    self.log_test("Session Isolation", False,
                                "Sessions have overlapping selections")
            else:
                self.log_test("Session Isolation", False,
                            f"Session1: {len(selections1)}, Session2: {len(selections2)}")

            # Cleanup
            cursor.execute("""
                DELETE FROM playlist_builder_state
                WHERE session_id IN (?, ?)
            """, (session1, session2))
            db.conn.commit()

        finally:
            cursor.close()

    def run_all_tests(self):
        """Run all Phase 8 tests"""
        print("\n" + "="*80)
        print("PHASE 8: TESTING & POLISH - Comprehensive Test Suite")
        print("="*80)
        print(f"Test Session ID: {self.test_session_id}")
        print(f"Database: {self.db_path}")
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            self.test_8_1_selection_persistence()
            self.test_8_2_performance()
            self.test_8_3_edge_cases()
            self.test_8_4_database_operations()
            self.test_8_5_concurrent_sessions()

        finally:
            self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)

        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r['passed'])
        failed = total - passed

        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")
        print(f"Success Rate: {(passed/total*100):.1f}%")

        if failed > 0:
            print("\nFailed Tests:")
            for result in self.test_results:
                if not result['passed']:
                    print(f"  ❌ {result['test']}: {result['message']}")

        print(f"\nEnd Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Save results to file
        results_file = project_root / "tests" / f"phase8_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(self.test_results, f, indent=2)

        print(f"\nResults saved to: {results_file}")


if __name__ == "__main__":
    tester = Phase8Tester()
    tester.run_all_tests()
