"""
MBID Retry Manager for Radio Monitor 1.0

This module handles automatic retry of PENDING artists:
- Daily retry of all PENDING artists
- Automatic cleanup of old PENDING artists (30+ days)
- Integration with APScheduler
- Statistics tracking

Created: 2026-02-08 (Phase 5 Enhancement)
"""

import logging
from datetime import datetime
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class MBIDRetryManager:
    """Manages automatic retry of PENDING artists with APScheduler"""

    def __init__(self, db):
        """Initialize MBID retry manager

        Args:
            db: RadioDatabase instance
        """
        self.db = db
        self.scheduler = None
        self.last_retry_time = None
        self.retry_stats = {
            'total_retried': 0,
            'resolved': 0,
            'failed': 0,
            'deleted_old': 0
        }

    def initialize(self, scheduler):
        """Initialize with existing APScheduler instance

        Args:
            scheduler: BackgroundScheduler instance from main app
        """
        self.scheduler = scheduler
        self._schedule_retry_job()

    def _schedule_retry_job(self):
        """Schedule daily MBID retry job"""
        try:
            # Remove existing job if any
            if self.scheduler.get_job('mbid_retry'):
                self.scheduler.remove_job('mbid_retry')

            # Add daily job (runs every 24 hours from app start)
            self.scheduler.add_job(
                func=self._retry_all_pending_artists,
                trigger=IntervalTrigger(hours=24),
                id='mbid_retry',
                name='Retry PENDING Artists',
                replace_existing=True
            )

            logger.info("Scheduled MBID retry job (every 24 hours)")

        except Exception as e:
            logger.error(f"Error scheduling MBID retry job: {e}")

    def _retry_all_pending_artists(self):
        """Retry all PENDING artists and clean up old ones

        Called automatically by scheduler every 24 hours.
        """
        logger.info("Starting daily PENDING artist retry...")

        try:
            # Import retry function
            from radio_monitor.mbid import retry_pending_artists

            # Get all PENDING artists from database
            pending_artists = self.db.get_pending_artists()

            if not pending_artists:
                logger.info("No PENDING artists to retry")
                # Still cleanup old ones
                deleted = self.db.delete_pending_artists_older_than(days=30)
                if deleted > 0:
                    logger.info(f"Deleted {deleted} old PENDING artists (cleanup)")
                return

            logger.info(f"Found {len(pending_artists)} PENDING artists to retry")

            # Retry all PENDING artists
            results = retry_pending_artists(
                db=self.db,
                max_artists=None  # Retry all of them
            )

            # Log results
            logger.info(
                f"MBID retry complete: "
                f"{results.get('resolved', 0)} resolved, "
                f"{results.get('failed', 0)} still failed"
            )

            # Update statistics
            self.retry_stats['total_retried'] += len(pending_artists)
            self.retry_stats['resolved'] += results.get('resolved', 0)
            self.retry_stats['failed'] += results.get('failed', 0)
            self.last_retry_time = datetime.now()

            # Clean up old PENDING artists (30+ days)
            deleted = self.db.delete_pending_artists_older_than(days=30)
            self.retry_stats['deleted_old'] += deleted

            if deleted > 0:
                logger.info(f"Deleted {deleted} old PENDING artists (30+ days)")

            # Log summary
            logger.info(
                f"Daily MBID retry summary: "
                f"Retried {len(pending_artists)}, "
                f"Resolved {results.get('resolved', 0)}, "
                f"Failed {results.get('failed', 0)}, "
                f"Deleted old {deleted}"
            )

        except Exception as e:
            logger.error(f"Error during MBID retry job: {e}")

    def trigger_retry_now(self):
        """Trigger immediate retry of PENDING artists (for testing)"""
        logger.info("Triggering immediate MBID retry...")
        if self.scheduler:
            self.scheduler.add_job(
                func=self._retry_all_pending_artists,
                id=f'manual_retry_{datetime.now().timestamp()}',
                name='Manual MBID Retry'
            )
        else:
            logger.warning("No scheduler available - cannot trigger retry")

    def get_stats(self):
        """Get retry statistics

        Returns:
            Dict with retry statistics
        """
        # Get current PENDING count
        pending_artists = self.db.get_pending_artists()
        pending_count = len(pending_artists) if pending_artists else 0

        return {
            'pending_count': pending_count,
            'last_retry_time': self.last_retry_time,
            'total_retried': self.retry_stats['total_retried'],
            'resolved': self.retry_stats['resolved'],
            'failed': self.retry_stats['failed'],
            'deleted_old': self.retry_stats['deleted_old']
        }
