"""
Settings Routes for Radio Monitor 1.0

Settings management and configuration.
"""

import logging
from flask import Blueprint, render_template, jsonify, request, current_app
from radio_monitor.auth import requires_auth

from radio_monitor.gui import app, load_settings, save_settings_to_file

logger = logging.getLogger(__name__)

settings_bp = Blueprint('settings', __name__)


def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')


@settings_bp.route('/settings')
@requires_auth
def settings():
    """Settings page"""
    from radio_monitor.gui import is_first_run
    from flask import redirect, url_for

    if is_first_run():
        return redirect(url_for('wizard'))

    return render_template('settings.html')


@settings_bp.route('/api/settings')
@requires_auth
def api_settings():
    """Get current settings

    Returns JSON: Complete settings object
    """
    settings = load_settings()
    if settings:
        return jsonify(settings)

    return jsonify({}), 404


@settings_bp.route('/api/settings/update', methods=['POST'])
@requires_auth
def api_settings_update():
    """Update settings

    Expects JSON:
        {
            "lidarr": {...},
            "plex": {...},
            "monitor": {...},
            ...
        }

    Returns JSON:
        {
            "success": true,
            "message": "Settings saved successfully"
        }
    """
    try:
        data = request.json

        # Load current settings
        settings = load_settings()
        if not settings:
            settings = {}

        # Check if GUI settings changed (requires restart)
        restart_required = False
        restart_reasons = []

        if data.get('gui'):
            current_gui = settings.get('gui', {})
            new_gui = data['gui']

            # Check if host changed
            if new_gui.get('host') != current_gui.get('host'):
                restart_required = True
                restart_reasons.append('GUI host address changed')

            # Check if port changed
            if new_gui.get('port') != current_gui.get('port'):
                restart_required = True
                restart_reasons.append('GUI port changed')

            # Check if debug mode changed
            if new_gui.get('debug') != current_gui.get('debug'):
                restart_required = True
                restart_reasons.append('Debug mode changed')

        # Update with new values
        for section in ['lidarr', 'plex', 'monitor', 'database', 'gui', 'logging', 'openrouter']:
            if section in data:
                settings[section] = {**settings.get(section, {}), **data[section]}

        # Save API key directly in settings if provided
        if 'lidarr' in data and 'api_key' in data['lidarr']:
            api_key = data['lidarr']['api_key']
            settings['lidarr']['api_key'] = api_key
            # Remove old api_key_file reference if it exists
            if 'api_key_file' in settings['lidarr']:
                del settings['lidarr']['api_key_file']

        # Save settings
        if save_settings_to_file(settings):
            logger.info("Settings updated successfully")

            # Update Flask app.config with new settings
            from flask import current_app
            current_app.config['settings'] = settings
            logger.info("Updated app.config with new settings")

            # Return restart warning if needed
            return jsonify({
                'success': True,
                'message': 'Settings saved successfully',
                'restart_required': restart_required,
                'restart_reasons': restart_reasons
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Error saving settings file'
            }), 500

    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@settings_bp.route('/api/settings/test-musicbrainz', methods=['POST'])
@requires_auth
def api_test_musicbrainz():
    """Test MusicBrainz connection

    Returns JSON:
        {
            "success": true/false,
            "message": "MusicBrainz API is reachable"
        }
    """
    try:
        import musicbrainzngs

        # Try to search for something (doesn't matter if it exists)
        try:
            musicbrainzngs.search_artists('test', limit=1)
            return jsonify({
                'success': True,
                'message': 'MusicBrainz API is reachable'
            })
        except musicbrainzngs.WebServiceError as e:
            # Accept any non-500 status as "reachable"
            if hasattr(e, 'status') and e.status != 500:
                return jsonify({
                    'success': True,
                    'message': 'MusicBrainz API is reachable'
                })
            raise

    except Exception as e:
        logger.error(f"Error testing MusicBrainz: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        })


@settings_bp.route('/api/settings/export-db', methods=['POST'])
@requires_auth
def api_export_database():
    """Export database for sharing with friends

    Expects JSON:
        {
            "filename": "radio_monitor_shared.db" (optional)
        }

    Returns JSON:
        {
            "success": true/false,
            "path": "/path/to/export.db",
            "message": "Database exported successfully"
        }
    """
    try:
        from radio_monitor.database.exports import export_database_for_sharing

        data = request.json or {}
        filename = data.get('filename', 'radio_monitor_shared.db')

        # Ensure .db extension
        if not filename.endswith('.db'):
            filename += '.db'

        # Get backup directory from settings
        settings = load_settings()
        backup_dir = settings.get('database', {}).get('backup_path', 'backups/')

        # Create backup directory if it doesn't exist
        import os
        from pathlib import Path
        Path(backup_dir).mkdir(parents=True, exist_ok=True)

        # Full output path
        output_path = os.path.join(backup_dir, filename)

        # Check if file already exists
        if os.path.exists(output_path):
            return jsonify({
                'success': False,
                'message': f'File already exists: {filename}'
            }), 400

        # Get database path
        db_file = settings.get('monitor', {}).get('database_file', 'radio_songs.db')

        # Export database
        if export_database_for_sharing(db_file, output_path):
            logger.info(f"Database exported for sharing: {output_path}")
            return jsonify({
                'success': True,
                'path': output_path,
                'message': f'Database exported to {output_path}'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Export failed'
            }), 500

    except Exception as e:
        logger.error(f"Error exporting database: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@settings_bp.route('/api/settings/import-db', methods=['POST'])
@requires_auth
def api_import_database():
    """Import shared database from a friend

    WARNING: This overwrites the current database!

    Expects JSON:
        {
            "source_path": "/path/to/shared.db"
        }

    Returns JSON:
        {
            "success": true/false,
            "message": "Database imported successfully"
        }
    """
    try:
        from radio_monitor.backup import import_database_from_backup

        data = request.json or {}
        source_path = data.get('source_path')

        if not source_path:
            return jsonify({
                'success': False,
                'message': 'source_path is required'
            }), 400

        # Validate source file exists
        import os
        if not os.path.exists(source_path):
            return jsonify({
                'success': False,
                'message': f'Source file not found: {source_path}'
            }), 404

        # Get database paths
        settings = load_settings()
        db_file = settings.get('monitor', {}).get('database_file', 'radio_songs.db')
        backup_dir = settings.get('database', {}).get('backup_path', 'backups/')

        # Import database (creates pre-import backup automatically)
        if import_database_from_backup(source_path, db_file, backup_dir):
            logger.info(f"Database imported from: {source_path}")
            return jsonify({
                'success': True,
                'message': 'Database imported successfully. Please refresh the page.'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Import failed'
            }), 500

    except Exception as e:
        logger.error(f"Error importing database: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@settings_bp.route('/api/shutdown', methods=['POST'])
@requires_auth
def api_shutdown():
    """Shutdown the application gracefully

    This endpoint performs a graceful shutdown:
    - Stops APScheduler jobs
    - Closes database connections
    - Shuts down Flask server
    - On Windows with pystray: Stops tray icon

    Returns JSON:
        {
            "status": "shutting_down"
        }
    """
    import os
    import signal

    logger.info("Shutdown requested from web interface")

    try:
        # Get scheduler and database from app config
        scheduler = current_app.config.get('scheduler')
        database = current_app.config.get('db')

        # Stop scheduler if running
        if scheduler and scheduler.scheduler and scheduler.scheduler.running:
            logger.info("Stopping APScheduler...")
            scheduler.shutdown(wait=False)
            logger.info("APScheduler stopped")

        # Close database connection
        if database:
            logger.info("Closing database connection...")
            database.close()
            logger.info("Database connection closed")

        # Shutdown Flask server
        logger.info("Shutting down Flask server...")

        # Try Werkzeug shutdown (older versions)
        func = request.environ.get('werkzeug.server.shutdown')
        if func:
            func()
            logger.info("Flask server shutdown via werkzeug.server.shutdown")
        else:
            # For newer Werkzeug or production servers, use os._exit
            # Schedule the exit in a separate thread to allow response to be sent
            import threading

            def delayed_exit():
                import time
                time.sleep(0.5)  # Give time for response to be sent
                logger.info("Exiting application...")
                os._exit(0)

            exit_thread = threading.Thread(target=delayed_exit)
            exit_thread.daemon = True
            exit_thread.start()
            logger.info("Flask server shutdown scheduled (will exit in 0.5s)")

        return jsonify({
            'status': 'shutting_down',
            'message': 'Application is shutting down. You can close this tab.'
        })

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error during shutdown: {str(e)}'
        }), 500
