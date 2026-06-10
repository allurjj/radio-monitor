"""
Cleanup functions for Radio Monitor 1.0

This module provides scheduled cleanup functions for:
- Activity log entries (keep 90 days)
- Old log files (keep 30 days)
- Old backup files (enforce retention policy)
"""

import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def cleanup_activity_logs(db, days=90):
    """Clean up old activity log entries

    Args:
        db: RadioDatabase instance
        days: Retention period in days (default: 90)

    Returns:
        int: Number of entries deleted
    """
    if not db:
        logger.warning("Database not provided for activity cleanup")
        return 0

    try:
        from radio_monitor.database.activity import cleanup_old_activity

        with db.conn:
            deleted = cleanup_old_activity(db.get_cursor(), days=days)

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old activity log entries (older than {days} days)")

        return deleted

    except Exception as e:
        logger.error(f"Error during activity log cleanup: {e}")
        return 0


def cleanup_log_files(days=30):
    """Clean up old rotated log files

    Args:
        days: Retention period in days (default: 30)

    Returns:
        int: Number of files deleted
    """
    try:
        deleted_count = 0
        cutoff_date = datetime.now() - timedelta(days=days)

        # Find all log files in project root
        project_root = Path.cwd()
        log_files = list(project_root.glob('*.log*'))
        log_files.extend(list(project_root.glob('logs/*.log*')))

        for log_file in log_files:
            # Skip the main log file (radio_monitor.log)
            if log_file.name == 'radio_monitor.log':
                continue

            # Check if file is old enough to delete
            if log_file.stat().st_mtime < cutoff_date.timestamp():
                try:
                    log_file.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old log file: {log_file}")
                except Exception as e:
                    logger.error(f"Error deleting log file {log_file}: {e}")

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old log files (older than {days} days)")

        return deleted_count

    except Exception as e:
        logger.error(f"Error during log file cleanup: {e}")
        return 0


def cleanup_old_backups(backup_path='backups/', retention_days=7):
    """Clean up old backup files (enforce retention policy)

    Args:
        backup_path: Path to backups directory (default: 'backups/')
        retention_days: Number of days to keep backups (default: 7)

    Returns:
        int: Number of backups deleted
    """
    try:
        from radio_monitor.backup import enforce_retention_policy

        deleted = enforce_retention_policy(backup_path, retention_days)
        return deleted

    except Exception as e:
        logger.error(f"Error during backup cleanup: {e}")
        return 0


def run_all_cleanup(db, settings=None):
    """Run all cleanup jobs

    Args:
        db: RadioDatabase instance
        settings: Settings dict (optional, will load if not provided)

    Returns:
        dict: Cleanup results
    """
    if not settings:
        from radio_monitor.gui import load_settings
        settings = load_settings()

    # Get retention settings
    activity_retention = settings.get('logging', {}).get('activity_retention_days', 90) if settings else 90
    log_retention = settings.get('logging', {}).get('log_retention_days', 30) if settings else 30
    backup_retention = settings.get('database', {}).get('backup_retention_days', 7) if settings else 7
    backup_path = settings.get('database', {}).get('backup_path', 'backups/') if settings else 'backups/'

    results = {
        'activity_deleted': 0,
        'log_files_deleted': 0,
        'backups_deleted': 0,
        'timestamp': datetime.now().isoformat()
    }

    # Clean up activity logs
    try:
        results['activity_deleted'] = cleanup_activity_logs(db, days=activity_retention)
    except Exception as e:
        logger.error(f"Error in activity cleanup: {e}")

    # Clean up log files
    try:
        results['log_files_deleted'] = cleanup_log_files(days=log_retention)
    except Exception as e:
        logger.error(f"Error in log file cleanup: {e}")

    # Clean up old backups
    try:
        results['backups_deleted'] = cleanup_old_backups(backup_path, retention_days=backup_retention)
    except Exception as e:
        logger.error(f"Error in backup cleanup: {e}")

    logger.info(f"Cleanup complete: {results}")
    return results
