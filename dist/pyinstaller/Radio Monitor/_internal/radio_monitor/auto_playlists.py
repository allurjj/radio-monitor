"""
Auto Playlist Manager for Radio Monitor 1.0

This module handles scheduled Plex playlists that automatically update at specified intervals:
- Schedule management (add/remove/update jobs)
- Playlist execution on schedule
- Failure tracking and recovery
- Integration with APScheduler

Created: 2026-02-07
"""

import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class AutoPlaylistManager:
    """Manages scheduled auto playlists with APScheduler"""

    def __init__(self, db, plex_config, monitor_running_callback):
        """Initialize auto playlist manager

        Args:
            db: RadioDatabase instance
            plex_config: Dict with Plex connection info (url, token, library_name)
            monitor_running_callback: Function that returns True if monitoring is running
        """
        self.db = db
        self.plex_config = plex_config
        self.monitor_running_callback = monitor_running_callback
        self.scheduler = None

    def initialize(self, scheduler):
        """Initialize with existing APScheduler instance

        Args:
            scheduler: BackgroundScheduler instance from main app
        """
        self.scheduler = scheduler
        self._load_and_schedule_playlists()

    def _load_and_schedule_playlists(self):
        """Load all enabled auto playlists and schedule them"""

        try:
            playlists = self.db.get_playlists()

            # Only schedule enabled auto playlists
            enabled_playlists = [p for p in playlists if p.get('enabled') and p.get('is_auto')]

            logger.info(f"Loading {len(enabled_playlists)} enabled auto playlist(s)...")

            for playlist in enabled_playlists:
                self._schedule_playlist(playlist)

            logger.info("Auto playlists loaded successfully")

        except Exception as e:
            logger.error(f"Error loading auto playlists: {e}")

    def _schedule_playlist(self, playlist):
        """Add a single playlist to the scheduler

        Args:
            playlist: Dict with playlist info
        """
        try:
            playlist_id = playlist['id']
            interval_minutes = playlist['interval_minutes']

            # Calculate next run time if not set
            if not playlist.get('next_update'):
                next_update = datetime.now() + timedelta(minutes=interval_minutes)
                self.db.update_playlist_next_run(playlist_id, next_update)

            # Add job to scheduler
            job_id = f'auto_playlist_{playlist_id}'

            # Remove existing job if any
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)

            # Add new job
            self.scheduler.add_job(
                func=self._execute_auto_playlist,
                trigger=IntervalTrigger(minutes=interval_minutes),
                id=job_id,
                args=[playlist_id],
                name=f"Auto Playlist: {playlist['name']}",
                replace_existing=True
            )

            logger.info(f"Scheduled auto playlist '{playlist['name']}' (ID: {playlist_id}) every {interval_minutes} minutes")

        except Exception as e:
            logger.error(f"Error scheduling playlist {playlist.get('name')}: {e}")

    def _execute_auto_playlist(self, playlist_id):
        """Execute an auto playlist update (called by scheduler)

        Args:
            playlist_id: Auto playlist ID
        """
        try:
            # ENHANCED LOGGING - Check if monitoring is running
            monitor_running = self.monitor_running_callback()
            logger.info(f"[AUTO PLAYLIST] Starting execution for playlist {playlist_id}, monitor_running={monitor_running}")

            if not monitor_running:
                logger.warning(f"[AUTO PLAYLIST] Monitoring NOT running - skipping auto playlist {playlist_id}")
                return

            logger.info(f"[AUTO PLAYLIST] Monitoring is running, proceeding with playlist {playlist_id}")

            # Get playlist details
            playlist = self.db.get_playlist(playlist_id)
            if not playlist:
                logger.error(f"Auto playlist {playlist_id} not found")
                return

            # Check if it's still an auto playlist
            if not playlist.get('is_auto'):
                logger.info(f"Playlist {playlist_id} is now manual - skipping auto update")
                return

            if not playlist.get('enabled'):
                logger.info(f"Auto playlist {playlist_id} is disabled - skipping")
                return

            logger.info(f"Executing auto playlist: {playlist['name']}")

            # Import here to avoid circular dependency
            from radio_monitor.plex import create_playlist
            from plexapi.server import PlexServer

            # Connect to Plex
            plex = PlexServer(self.plex_config['url'], self.plex_config['token'])

            # Build filters from playlist config
            filters = {
                'station_ids': playlist['station_ids'],
                'days': playlist.get('days'),
                'limit': playlist['max_songs'],
                'min_plays': playlist.get('min_plays', 1),
                'max_plays': playlist.get('max_plays')
            }

            # Special handling for 'recent' mode
            mode = playlist['mode']

            # Create/update playlist
            result = create_playlist(
                db=self.db,
                plex=plex,
                playlist_name=playlist['name'],
                mode=mode,
                filters=filters
            )

            # Update last_updated and calculate next_update
            last_updated = datetime.now()
            interval_minutes = playlist['interval_minutes']
            next_update = last_updated + timedelta(minutes=interval_minutes)

            # ENHANCED LOGGING - About to update database
            logger.info(f"[AUTO PLAYLIST] Playlist {playlist_id} created successfully, updating database:")
            logger.info(f"[AUTO PLAYLIST]   last_updated={last_updated}, next_update={next_update}")

            # Reset consecutive failures on success
            self.db.record_playlist_update(
                playlist_id=playlist_id,
                success=True,
                last_updated=last_updated,
                next_update=next_update
            )

            logger.info(f"[AUTO PLAYLIST] Database update complete for playlist {playlist_id}")

            # ENHANCED LOGGING - Verify the update was written
            verification = self.db.get_playlist(playlist_id)
            logger.info(f"[AUTO PLAYLIST] Verification - Playlist {playlist_id} last_updated in DB: {verification['last_updated'] if verification else 'NOT FOUND'}")

            logger.info(f"Auto playlist '{playlist['name']}' updated successfully: {result['added']} songs added")

        except Exception as e:
            logger.error(f"[AUTO PLAYLIST] EXCEPTION in playlist {playlist_id}: {e}", exc_info=True)

            # Record failure (increment consecutive_failures)
            try:
                logger.info(f"[AUTO PLAYLIST] Recording failure for playlist {playlist_id}")
                self.db.record_playlist_update(
                    playlist_id=playlist_id,
                    success=False
                )
                logger.info(f"[AUTO PLAYLIST] Failure recorded for playlist {playlist_id}")
            except Exception as db_error:
                logger.error(f"[AUTO PLAYLIST] Error recording playlist failure: {db_error}", exc_info=True)

    def add_playlist(self, playlist):
        """Add a new auto playlist to the scheduler

        Args:
            playlist: Dict with playlist configuration
        """
        try:
            # Create playlist in database (unpack dict to individual parameters)
            playlist_id = self.db.add_playlist(
                name=playlist['name'],
                is_auto=True,  # Always auto for scheduled playlists
                interval_minutes=playlist['interval_minutes'],
                station_ids=playlist['station_ids'],
                max_songs=playlist['max_songs'],
                mode=playlist['mode'],
                min_plays=playlist.get('min_plays', 1),
                max_plays=playlist.get('max_plays'),
                days=playlist.get('days')
            )

            # Calculate initial next_update (method calculates from interval)
            interval_minutes = playlist['interval_minutes']
            self.db.update_playlist_next_run(playlist_id, interval_minutes)

            # Schedule the playlist if enabled
            if playlist.get('enabled', True):
                # Get full playlist details
                playlist_data = self.db.get_playlist(playlist_id)
                self._schedule_playlist(playlist_data)

            return playlist_id

        except Exception as e:
            logger.error(f"Error adding auto playlist: {e}")
            raise

    def remove_playlist(self, playlist_id):
        """Remove an auto playlist from the scheduler

        Args:
            playlist_id: Auto playlist ID
        """
        try:
            # Remove from scheduler
            job_id = f'auto_playlist_{playlist_id}'
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)

            # Delete from database
            self.db.delete_playlist(playlist_id)

            logger.info(f"Auto playlist {playlist_id} removed")

        except Exception as e:
            logger.error(f"Error removing auto playlist {playlist_id}: {e}")
            raise

    def update_playlist(self, playlist_id, updates):
        """Update an existing auto playlist

        Args:
            playlist_id: Auto playlist ID
            updates: Dict of fields to update
        """
        try:
            # Update in database (unpack dict to keyword arguments)
            self.db.update_playlist(
                playlist_id=playlist_id,
                name=updates.get('name'),
                interval_minutes=updates.get('interval_minutes'),
                station_ids=updates.get('station_ids'),
                max_songs=updates.get('max_songs'),
                mode=updates.get('mode'),
                min_plays=updates.get('min_plays'),
                max_plays=updates.get('max_plays'),
                days=updates.get('days')
            )

            # Reschedule if interval or enabled status changed
            if 'interval_minutes' in updates or 'enabled' in updates:
                playlist = self.db.get_playlist(playlist_id)

                # Remove old job
                job_id = f'auto_playlist_{playlist_id}'
                if self.scheduler.get_job(job_id):
                    self.scheduler.remove_job(job_id)

                # Add new job if enabled
                if playlist.get('enabled'):
                    self._schedule_playlist(playlist)

            logger.info(f"Auto playlist {playlist_id} updated")

        except Exception as e:
            logger.error(f"Error updating auto playlist {playlist_id}: {e}")
            raise

    def trigger_update(self, playlist_id):
        """Trigger immediate update of an auto playlist

        Args:
            playlist_id: Auto playlist ID
        """
        logger.info(f"Triggering immediate update for auto playlist {playlist_id}")

        # Execute in background
        if self.scheduler:
            self.scheduler.add_job(
                func=self._execute_auto_playlist,
                args=[playlist_id],
                id=f'trigger_{playlist_id}_{datetime.now().timestamp()}',
                name=f"Manual trigger: Auto Playlist {playlist_id}"
            )
        else:
            logger.warning("No scheduler available - cannot trigger update")

    def get_next_run_time(self, playlist_id):
        """Get the next scheduled run time for a playlist

        Args:
            playlist_id: Auto playlist ID

        Returns:
            datetime or None
        """
        try:
            job_id = f'auto_playlist_{playlist_id}'
            job = self.scheduler.get_job(job_id)

            if job and job.next_run_time:
                return job.next_run_time

            return None

        except Exception as e:
            logger.error(f"Error getting next run time: {e}")
            return None
