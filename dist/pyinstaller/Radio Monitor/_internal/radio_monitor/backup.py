"""
Database Backup and Restore Module for Radio Monitor 1.0

This module provides:
- Timestamped database backups
- Validated restore with automatic rollback
- Backup listing and management
- Retention policy enforcement
- Database vacuuming

Key Principle: Safety first - always validate before and after operations.
"""

import os
import shutil
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def is_valid_sqlite_db(file_path):
    """Validate that a file is a valid SQLite database

    Args:
        file_path: Path to database file

    Returns:
        True if valid SQLite database, False otherwise
    """
    try:
        if not os.path.exists(file_path):
            return False

        # Check file size (must be > 0)
        if os.path.getsize(file_path) == 0:
            return False

        # Try to open and query the database
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()

        # Check if it has our schema (sqlite_master table)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
        result = cursor.fetchone()

        conn.close()

        return result is not None

    except sqlite3.Error as e:
        logger.error(f"SQLite validation error: {e}")
        return False
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return False


def backup_database(db_path, backup_dir='backups/', settings=None):
    """Create a timestamped backup of the database

    Args:
        db_path: Path to database file
        backup_dir: Directory for backups (default: backups/)
        settings: Settings dict (optional, for retention policy)

    Returns:
        Path to backup file if successful, None otherwise
    """
    try:
        # Create backup directory if it doesn't exist
        Path(backup_dir).mkdir(parents=True, exist_ok=True)

        # Generate timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        db_name = os.path.basename(db_path)
        backup_name = f"{db_name.replace('.db', '')}_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_name)

        # Copy database
        shutil.copy2(db_path, backup_path)

        # Validate backup
        if not is_valid_sqlite_db(backup_path):
            logger.error(f"Backup validation failed: {backup_path}")
            os.remove(backup_path)
            return None

        logger.info(f"Database backed up to {backup_path}")

        # Enforce retention policy if settings provided
        if settings:
            enforce_retention_policy(backup_dir, settings)

        return backup_path

    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return None


def restore_database(backup_path, db_path, backup_dir='backups/'):
    """Restore database from backup with validation and rollback

    Args:
        backup_path: Path to backup file
        db_path: Path where database should be restored
        backup_dir: Directory for pre-restore backup

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Starting database restore from {backup_path}")

        # Step 1: Validate backup is a valid SQLite database
        if not is_valid_sqlite_db(backup_path):
            logger.error(f"Error: {backup_path} is not a valid SQLite database")
            return False

        # Create backup directory if it doesn't exist
        Path(backup_dir).mkdir(parents=True, exist_ok=True)

        # Step 2: Backup current database (pre-restore backup)
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        db_name = os.path.basename(db_path)
        pre_restore_backup = os.path.join(
            backup_dir,
            f"{db_name.replace('.db', '')}_pre-restore_{timestamp}.db"
        )

        if os.path.exists(db_path):
            shutil.copy2(db_path, pre_restore_backup)
            logger.info(f"Pre-restore backup created: {pre_restore_backup}")
        else:
            logger.warning(f"Database file not found: {db_path}")
            return False

        # Step 3: Restore from backup
        shutil.copy2(backup_path, db_path)
        logger.info(f"Database copied from {backup_path}")

        # Step 4: Validate restored database
        if not is_valid_sqlite_db(db_path):
            logger.error("Error: Restore failed, restoring from pre-restore backup")
            shutil.copy2(pre_restore_backup, db_path)
            return False

        logger.info(f"[OK] Database restored successfully")
        logger.info(f"[OK] Pre-restore backup: {pre_restore_backup}")
        return True

    except Exception as e:
        logger.error(f"Restore failed: {e}")

        # Attempt rollback
        try:
            if os.path.exists(pre_restore_backup):
                shutil.copy2(pre_restore_backup, db_path)
                logger.info("Restored from pre-restore backup after failure")
        except:
            logger.error("Rollback failed")

        return False


def import_database_from_backup(source_path, db_path, backup_dir='backups/'):
    """Import a shared database from a friend

    This is a wrapper around restore_database() with clearer naming.
    Creates a pre-import backup before importing.

    Args:
        source_path: Path to shared database file
        db_path: Path where database should be imported (main database path)
        backup_dir: Directory for pre-import backup

    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Importing shared database from {source_path}")
    return restore_database(source_path, db_path, backup_dir)


def list_backups(backup_dir='backups/'):
    """List all backups in the backup directory

    Args:
        backup_dir: Directory containing backups

    Returns:
        List of dicts with keys: name, path, size, created_at, is_valid
    """
    try:
        Path(backup_dir).mkdir(parents=True, exist_ok=True)

        backups = []

        for filename in os.listdir(backup_dir):
            if filename.startswith('radio_songs') and filename.endswith('.db'):
                file_path = os.path.join(backup_dir, filename)

                # Parse timestamp from filename
                try:
                    # Format: radio_songs_2025-02-06_143022.db
                    parts = filename.replace('.db', '').split('_')
                    if len(parts) >= 3:
                        date_str = parts[-2]
                        time_str = parts[-1]
                        created_at = datetime.strptime(f"{date_str}_{time_str}", '%Y-%m-%d_%H%M%S')
                    else:
                        created_at = datetime.fromtimestamp(os.path.getctime(file_path))
                except:
                    created_at = datetime.fromtimestamp(os.path.getctime(file_path))

                # Validate backup
                is_valid = is_valid_sqlite_db(file_path)

                # Get file size
                size_mb = os.path.getsize(file_path) / (1024 * 1024)

                backups.append({
                    'name': filename,
                    'path': file_path,
                    'size_mb': round(size_mb, 2),
                    'created_at': created_at,
                    'is_valid': is_valid
                })

        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x['created_at'], reverse=True)

        return backups

    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        return []


def enforce_retention_policy(backup_dir='backups/', settings=None):
    """Enforce backup retention policy - delete old backups

    Args:
        backup_dir: Directory containing backups
        settings: Settings dict with retention policy

    Returns:
        Number of backups deleted
    """
    if not settings:
        return 0

    try:
        retention_days = settings.get('database', {}).get('backup_retention_days', 7)

        if retention_days <= 0:
            logger.info("Retention policy disabled (retention_days <= 0)")
            return 0

        # Get all backups
        backups = list_backups(backup_dir)

        if not backups:
            return 0

        # Calculate cutoff date
        cutoff_date = datetime.now().timestamp() - (retention_days * 24 * 60 * 60)

        # Delete old backups
        deleted_count = 0
        for backup in backups:
            if backup['created_at'].timestamp() < cutoff_date:
                try:
                    os.remove(backup['path'])
                    logger.info(f"Deleted old backup: {backup['name']}")
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting old backup {backup['name']}: {e}")

        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} old backup(s) (retention: {retention_days} days)")

        return deleted_count

    except Exception as e:
        logger.error(f"Error enforcing retention policy: {e}")
        return 0


def vacuum_database(db_path):
    """Vacuum/optimize the database

    Args:
        db_path: Path to database file

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info("Starting database vacuum...")

        conn = sqlite3.connect(db_path)
        conn.execute('VACUUM')
        conn.close()

        logger.info("[OK] Database vacuumed successfully")
        return True

    except Exception as e:
        logger.error(f"Vacuum failed: {e}")
        return False


def export_to_json(db_path, output_file):
    """Export database to JSON file

    Args:
        db_path: Path to database
        output_file: Output JSON file path

    Returns:
        Number of songs exported, or -1 on error
    """
    try:
        from radio_monitor.database import RadioDatabase

        db = RadioDatabase(db_path)

        # Export using existing method
        count = db.export_to_json(output_file)

        logger.info(f"Exported {count} songs to {output_file}")
        return count

    except Exception as e:
        logger.error(f"Export to JSON failed: {e}")
        return -1


def get_backup_stats(backup_dir='backups/'):
    """Get backup statistics

    Args:
        backup_dir: Directory containing backups

    Returns:
        Dict with keys: total_count, total_size_mb, oldest, newest, invalid_count
    """
    try:
        backups = list_backups(backup_dir)

        if not backups:
            return {
                'total_count': 0,
                'total_size_mb': 0,
                'oldest': None,
                'newest': None,
                'invalid_count': 0
            }

        total_count = len(backups)
        total_size_mb = sum(b['size_mb'] for b in backups)
        invalid_count = sum(1 for b in backups if not b['is_valid'])
        newest = backups[0]['created_at'] if backups else None
        oldest = backups[-1]['created_at'] if backups else None

        return {
            'total_count': total_count,
            'total_size_mb': round(total_size_mb, 2),
            'oldest': oldest,
            'newest': newest,
            'invalid_count': invalid_count
        }

    except Exception as e:
        logger.error(f"Error getting backup stats: {e}")
        return {
            'total_count': 0,
            'total_size_mb': 0,
            'oldest': None,
            'newest': None,
            'invalid_count': 0
        }
