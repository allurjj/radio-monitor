"""
APScheduler wrapper for Radio Monitor 1.0

This module provides a simple interface to APScheduler for background scraping:
- BackgroundScheduler setup
- Scrape job management (start/stop/resume)
- Graceful shutdown support

Key Principle: Simple wrapper around APScheduler - don't over-engineer.
The scraping job runs at a configurable interval (default: 10 minutes).
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class RadioScheduler:
    """Wrapper for APScheduler to manage background scraping job

    Attributes:
        scheduler: BackgroundScheduler instance
        scrape_interval: Interval in minutes between scrapes
    """

    def __init__(self, scrape_func, scrape_interval_minutes=10):
        """Initialize scheduler with scraping function

        Args:
            scrape_func: Function to call for each scrape (should take no args)
            scrape_interval_minutes: Minutes between scrapes (default: 10)
        """
        self.scheduler = BackgroundScheduler()
        self.scrape_interval = scrape_interval_minutes
        self.scrape_func = scrape_func
        self.job_id = 'scrape_job'

        # Add scrape job (paused initially)
        self.scheduler.add_job(
            self._run_scrape,
            'interval',
            minutes=self.scrape_interval,
            id=self.job_id,
            name='Radio Station Scraping Job'
        )

        # Start scheduler (job is paused by default)
        self.scheduler.start()
        logger.info(f"Scheduler initialized (interval: {scrape_interval_minutes} minutes)")

    def _run_scrape(self):
        """Run the scraping function

        This wraps the scrape function for error handling.
        """
        try:
            logger.info("Starting scheduled scrape")
            if self.scrape_func:
                self.scrape_func()
            logger.info("Scheduled scrape complete")
        except Exception as e:
            logger.error(f"Error during scheduled scrape: {e}", exc_info=True)

    def start(self):
        """Start/resume the scraping job

        Returns:
            True if started, False if already running
        """
        try:
            job = self.scheduler.get_job(self.job_id)
            if job and job.next_run_time is not None:
                # Job is already running (not paused)
                logger.info("Scraping job already running")
                return False

            # Resume the job
            self.scheduler.resume_job(self.job_id)
            logger.info("Scraping job started")
            return True

        except Exception as e:
            logger.error(f"Error starting scraping job: {e}")
            return False

    def stop(self):
        """Stop/pause the scraping job

        Returns:
            True if stopped, False if already stopped
        """
        try:
            job = self.scheduler.get_job(self.job_id)
            if not job:
                logger.warning("Scraping job not found")
                return False

            # Pause the job
            self.scheduler.pause_job(self.job_id)
            logger.info("Scraping job stopped")
            return True

        except Exception as e:
            logger.error(f"Error stopping scraping job: {e}")
            return False

    def is_running(self):
        """Check if scraping job is running (not paused)

        Returns:
            True if job is running, False if paused or error
        """
        try:
            job = self.scheduler.get_job(self.job_id)
            if not job:
                return False

            # Check if job has a next run time (not paused)
            return job.next_run_time is not None

        except Exception as e:
            logger.error(f"Error checking job status: {e}")
            return False

    def shutdown(self, wait=True):
        """Shutdown scheduler (graceful shutdown)

        Args:
            wait: Wait for running jobs to complete (default: True)
        """
        try:
            logger.info("Shutting down scheduler...")
            self.scheduler.shutdown(wait=wait)
            logger.info("Scheduler shut down")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}")

    def modify_interval(self, minutes):
        """Modify the scraping interval

        Args:
            minutes: New interval in minutes
        """
        try:
            self.scheduler.reschedule_job(
                self.job_id,
                trigger=IntervalTrigger(minutes=minutes)
            )
            self.scrape_interval = minutes
            logger.info(f"Scraping interval changed to {minutes} minutes")
            return True

        except Exception as e:
            logger.error(f"Error modifying scrape interval: {e}")
            return False

    def add_backup_job(self, backup_func, hour=3, minute=0):
        """Add daily backup job to scheduler

        Args:
            backup_func: Function to call for backup (should take no args)
            hour: Hour to run backup (default: 3)
            minute: Minute to run backup (default: 0)

        Returns:
            True if added, False if already exists or error
        """
        try:
            job_id = 'backup_job'

            # Check if job already exists
            if self.scheduler.get_job(job_id):
                logger.info("Backup job already exists")
                return False

            # Add backup job (cron trigger for daily at 3 AM)
            self.scheduler.add_job(
                backup_func,
                'cron',
                hour=hour,
                minute=minute,
                id=job_id,
                name='Daily Database Backup'
            )

            logger.info(f"Backup job scheduled for {hour:02d}:{minute:02d} daily")
            return True

        except Exception as e:
            logger.error(f"Error adding backup job: {e}")
            return False

    def remove_backup_job(self):
        """Remove daily backup job from scheduler

        Returns:
            True if removed, False if not exists or error
        """
        try:
            job_id = 'backup_job'

            if not self.scheduler.get_job(job_id):
                logger.info("Backup job does not exist")
                return False

            self.scheduler.remove_job(job_id)
            logger.info("Backup job removed")
            return True

        except Exception as e:
            logger.error(f"Error removing backup job: {e}")
            return False

    def add_cleanup_jobs(self, activity_cleanup_func, log_cleanup_func, plex_cleanup_func=None, database_cleanup_func=None, hour=4, minute=0):
        """Add daily cleanup jobs for activity logs, log files, Plex failures, and database corruption

        Args:
            activity_cleanup_func: Function to call for activity cleanup (should take no args)
            log_cleanup_func: Function to call for log cleanup (should take no args)
            plex_cleanup_func: Function to call for Plex failure cleanup (should take no args, optional)
            database_cleanup_func: Function to call for database cleanup (should take no args, optional)
            hour: Hour to run cleanup (default: 4 AM - after backup at 3 AM)
            minute: Minute to run cleanup (default: 0)

        Returns:
            True if added successfully, False if already exists or error
        """
        try:
            # Add activity cleanup job
            activity_job_id = 'activity_cleanup_job'
            if not self.scheduler.get_job(activity_job_id):
                self.scheduler.add_job(
                    activity_cleanup_func,
                    'cron',
                    hour=hour,
                    minute=minute,
                    id=activity_job_id,
                    name='Activity Log Cleanup Job'
                )
                logger.info(f"Activity cleanup job scheduled for daily at {hour:02d}:{minute:02d}")
            else:
                logger.info("Activity cleanup job already exists")

            # Add Plex failure cleanup job (10 minutes after activity cleanup)
            if plex_cleanup_func:
                plex_job_id = 'plex_failure_cleanup_job'
                if not self.scheduler.get_job(plex_job_id):
                    self.scheduler.add_job(
                        plex_cleanup_func,
                        'cron',
                        hour=hour,
                        minute=minute + 10,
                        id=plex_job_id,
                        name='Plex Failure Cleanup Job'
                    )
                    logger.info(f"Plex failure cleanup job scheduled for daily at {hour:02d}:{minute + 10:02d}")
                else:
                    logger.info("Plex failure cleanup job already exists")

            # Add log cleanup job (15 minutes after activity cleanup)
            log_job_id = 'log_cleanup_job'
            if not self.scheduler.get_job(log_job_id):
                self.scheduler.add_job(
                    log_cleanup_func,
                    'cron',
                    hour=hour,
                    minute=minute + 15,
                    id=log_job_id,
                    name='Log File Cleanup Job'
                )
                logger.info(f"Log cleanup job scheduled for daily at {hour:02d}:{minute + 15:02d}")
            else:
                logger.info("Log cleanup job already exists")

            # Add database cleanup job (20 minutes after activity cleanup)
            if database_cleanup_func:
                db_cleanup_job_id = 'database_cleanup_job'
                if not self.scheduler.get_job(db_cleanup_job_id):
                    self.scheduler.add_job(
                        database_cleanup_func,
                        'cron',
                        hour=hour,
                        minute=minute + 20,
                        id=db_cleanup_job_id,
                        name='Database Corruption Cleanup Job'
                    )
                    logger.info(f"Database cleanup job scheduled for daily at {hour:02d}:{minute + 20:02d}")
                else:
                    logger.info("Database cleanup job already exists")

            return True

        except Exception as e:
            logger.error(f"Error adding cleanup jobs: {e}")
            return False

    def remove_cleanup_jobs(self):
        """Remove daily cleanup jobs from scheduler

        Returns:
            True if removed successfully, False otherwise
        """
        try:
            removed = False

            # Remove activity cleanup job
            activity_job_id = 'activity_cleanup_job'
            if self.scheduler.get_job(activity_job_id):
                self.scheduler.remove_job(activity_job_id)
                logger.info("Activity cleanup job removed")
                removed = True

            # Remove Plex failure cleanup job
            plex_job_id = 'plex_failure_cleanup_job'
            if self.scheduler.get_job(plex_job_id):
                self.scheduler.remove_job(plex_job_id)
                logger.info("Plex failure cleanup job removed")
                removed = True

            # Remove log cleanup job
            log_job_id = 'log_cleanup_job'
            if self.scheduler.get_job(log_job_id):
                self.scheduler.remove_job(log_job_id)
                logger.info("Log cleanup job removed")
                removed = True

            return removed

        except Exception as e:
            logger.error(f"Error removing cleanup jobs: {e}")
            return False
