"""
Backup Routes for Radio Monitor 1.0

Database backup and restore functionality.
"""

import os
import logging
from flask import Blueprint, jsonify, request, current_app

from radio_monitor.gui import app, load_settings
from radio_monitor.auth import requires_auth

logger = logging.getLogger(__name__)

backup_bp = Blueprint('backup', __name__)


def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')


def get_settings():
    """Get settings from file (ensures fresh load)"""
    return load_settings() or {}


@backup_bp.route('/api/backups')
@requires_auth
def api_backups_list():
    """Get list of all database backups

    Returns JSON:
        [
            {
                "name": "radio_songs_2025-02-06_143022.db",
                "size_mb": 2.5,
                "created_at": "2025-02-06T14:30:22",
                "is_valid": true
            },
            ...
        ]
    """
    from radio_monitor.backup import list_backups

    try:
        settings = get_settings()
        backup_dir = settings.get('database', {}).get('backup_path', 'backups/')
        backups = list_backups(backup_dir)

        # Convert datetime objects to strings
        for backup in backups:
            backup['created_at'] = backup['created_at'].isoformat()

        return jsonify(backups)

    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        return jsonify({'error': str(e)}), 500


@backup_bp.route('/api/backups/stats')
@requires_auth
def api_backups_stats():
    """Get backup statistics

    Returns JSON:
        {
            "total_count": 5,
            "total_size_mb": 12.5,
            "oldest": "2025-02-01T03:00:00",
            "newest": "2025-02-06T14:30:22",
            "invalid_count": 0
        }
    """
    from radio_monitor.backup import get_backup_stats

    try:
        settings = get_settings()
        backup_dir = settings.get('database', {}).get('backup_path', 'backups/')
        stats = get_backup_stats(backup_dir)

        # Convert datetime objects to strings
        if stats.get('oldest'):
            stats['oldest'] = stats['oldest'].isoformat()
        if stats.get('newest'):
            stats['newest'] = stats['newest'].isoformat()

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error getting backup stats: {e}")
        return jsonify({'error': str(e)}), 500


@backup_bp.route('/api/backup/create', methods=['POST'])
@requires_auth
def api_backup_create():
    """Create a manual database backup

    Returns JSON:
        {
            "success": true,
            "backup_path": "backups/radio_songs_2025-02-06_143022.db"
        }
    """
    from radio_monitor.backup import backup_database

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        settings = get_settings()
        db_file = settings.get('monitor', {}).get('database_file', 'radio_songs.db')
        backup_dir = settings.get('database', {}).get('backup_path', 'backups/')

        backup_path = backup_database(db_file, backup_dir, settings)

        if backup_path:
            return jsonify({
                'success': True,
                'backup_path': backup_path
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Backup failed'
            }), 500

    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@backup_bp.route('/api/backup/restore', methods=['POST'])
@requires_auth
def api_backup_restore():
    """Restore database from backup

    Expects JSON:
        {
            "backup_path": "backups/radio_songs_2025-02-06_143022.db"
        }

    Returns JSON:
        {
            "success": true,
            "message": "Database restored successfully"
        }
    """
    from radio_monitor.backup import restore_database

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        data = request.json
        backup_path = data.get('backup_path')

        if not backup_path:
            return jsonify({'error': 'backup_path is required'}), 400

        settings = get_settings()
        db_file = settings.get('monitor', {}).get('database_file', 'radio_songs.db')
        backup_dir = settings.get('database', {}).get('backup_path', 'backups/')

        if not os.path.exists(backup_path):
            return jsonify({'error': 'Backup file not found'}), 404

        success = restore_database(backup_path, db_file, backup_dir)

        if success:
            return jsonify({
                'success': True,
                'message': 'Database restored successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Restore failed'
            }), 500

    except Exception as e:
        logger.error(f"Error restoring backup: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@backup_bp.route('/api/backup/download/<path:filename>')
@requires_auth
def api_backup_download(filename):
    """Download a backup file

    Args:
        filename: Name of the backup file

    Returns:
        File download response
    """
    try:
        from flask import send_file

        settings = get_settings()
        backup_dir = settings.get('database', {}).get('backup_path', 'backups/')
        backup_path = os.path.join(backup_dir, filename)

        if not os.path.exists(backup_path):
            return jsonify({'error': 'Backup file not found'}), 404

        return send_file(backup_path, as_attachment=True)

    except Exception as e:
        logger.error(f"Error downloading backup: {e}")
        return jsonify({'error': str(e)}), 500


@backup_bp.route('/api/backup/delete', methods=['DELETE'])
@requires_auth
def api_backup_delete():
    """Delete a backup file

    Expects JSON:
        {
            "backup_path": "backups/radio_songs_2025-02-06_143022.db"
        }

    Returns JSON:
        {
            "success": true,
            "message": "Backup deleted successfully"
        }
    """
    try:
        data = request.json
        backup_path = data.get('backup_path')

        if not backup_path:
            return jsonify({'error': 'backup_path is required'}), 400

        if not os.path.exists(backup_path):
            return jsonify({'error': 'Backup file not found'}), 404

        # Delete the file
        os.remove(backup_path)

        logger.info(f"Deleted backup: {backup_path}")

        return jsonify({
            'success': True,
            'message': 'Backup deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting backup: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
