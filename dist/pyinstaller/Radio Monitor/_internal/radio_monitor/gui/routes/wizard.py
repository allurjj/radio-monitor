"""
Wizard Routes for Radio Monitor 1.0

Setup wizard routes for first-time configuration.
"""

import os
import logging
from flask import render_template, jsonify, request, redirect, url_for

from radio_monitor.lidarr import test_lidarr_connection, get_lidarr_root_folders, get_lidarr_quality_profiles, get_lidarr_metadata_profiles
from radio_monitor.plex import test_plex_connection, get_plex_libraries
from radio_monitor.gui import load_settings, save_settings_to_file, is_first_run, app
from flask import current_app

logger = logging.getLogger(__name__)


@app.route('/wizard')
def wizard():
    """Setup wizard page"""
    return render_template('wizard.html')


@app.route('/api/wizard/test/lidarr', methods=['POST'])
def api_wizard_test_lidarr():
    """Test Lidarr connection (wizard)

    *** VERSION 2.0 - WITH CONFIG FETCH ***

    Expects JSON:
        {
            "url": "http://localhost:8686",
            "api_key": "your-api-key"
        }

    Returns JSON:
        {
            "success": true/false,
            "message": "Connected (Lidarr v3.1.0.4875)"
        }
    """
    logger.info("=== NEW VERSION 2.0 WIZARD LIDARR TEST CALLED ===")
    try:
        import time
        start_time = time.time()

        data = request.json
        url = data.get('url', 'http://localhost:8686')
        api_key = data.get('api_key', '')

        logger.info(f"Testing Lidarr connection to {url}")

        if not api_key:
            return jsonify({
                'success': False,
                'message': 'API key is required'
            })

        # Create temporary settings with API key
        temp_settings = {
            'lidarr': {
                'url': url,
                'api_key': api_key
            }
        }

        # Test connection
        success, message = test_lidarr_connection(temp_settings)

        elapsed = time.time() - start_time
        logger.info(f"Lidarr test completed in {elapsed:.2f}s: success={success}")

        response_data = {
            'success': success,
            'message': message
        }

        # If connection successful, fetch configuration
        if success:
            try:
                logger.info("Fetching Lidarr configuration...")

                # Get root folders
                root_folders = get_lidarr_root_folders(temp_settings)
                logger.info(f"Root folders response: {root_folders}")
                if root_folders and len(root_folders) > 0:
                    response_data['root_folders'] = root_folders
                    response_data['default_root_folder'] = root_folders[0].get('path', '')
                    logger.info(f"Set default_root_folder to: {response_data['default_root_folder']}")

                # Get quality profiles
                quality_profiles = get_lidarr_quality_profiles(temp_settings)
                logger.info(f"Quality profiles response: {quality_profiles}")
                if quality_profiles and len(quality_profiles) > 0:
                    response_data['quality_profiles'] = quality_profiles
                    response_data['default_quality_profile'] = quality_profiles[0].get('id', 1)
                    logger.info(f"Set default_quality_profile to: {response_data['default_quality_profile']}")

                # Get metadata profiles
                metadata_profiles = get_lidarr_metadata_profiles(temp_settings)
                logger.info(f"Metadata profiles response: {metadata_profiles}")
                if metadata_profiles and len(metadata_profiles) > 0:
                    response_data['metadata_profiles'] = metadata_profiles
                    response_data['default_metadata_profile'] = metadata_profiles[0].get('id', 1)
                    logger.info(f"Set default_metadata_profile to: {response_data['default_metadata_profile']}")

                logger.info(f"Final response_data keys: {list(response_data.keys())}")

            except Exception as e:
                logger.error(f"Error fetching Lidarr configuration: {e}", exc_info=True)
                # Don't fail the test if config fetch fails
                pass

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error testing Lidarr connection: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f"Server error: {str(e)}"
        })


@app.route('/api/wizard/test/plex', methods=['POST'])
def api_wizard_test_plex():
    """Test Plex connection (wizard)

    Expects JSON:
        {
            "url": "http://localhost:32400",
            "token": "your-plex-token"
        }

    Returns JSON:
        {
            "success": true/false,
            "message": "Connected to MyServer (Plex 1.32.0)"
        }
    """
    try:
        import time
        start_time = time.time()

        data = request.json
        url = data.get('url', 'http://localhost:32400')
        token = data.get('token', '')

        logger.info(f"Testing Plex connection to {url}")

        if not token:
            return jsonify({
                'success': False,
                'message': 'Plex token is required'
            })

        # Create temporary settings for testing
        temp_settings = {
            'plex': {
                'url': url,
                'token': token
            }
        }

        # Test connection
        success, message = test_plex_connection(temp_settings)

        elapsed = time.time() - start_time
        logger.info(f"Plex test completed in {elapsed:.2f}s: success={success}")

        response_data = {
            'success': success,
            'message': message
        }

        # If connection successful, fetch libraries
        if success:
            try:
                logger.info("Fetching Plex libraries...")
                libraries = get_plex_libraries(temp_settings)

                if libraries and len(libraries) > 0:
                    response_data['libraries'] = libraries
                    # All libraries returned are music libraries (type='artist' in Plex)
                    # Default to the first one
                    response_data['default_library'] = libraries[0].get('name')
                    logger.info(f"Fetched {len(libraries)} Plex libraries, default: {response_data['default_library']}")
                else:
                    logger.warning("No Plex libraries found")

            except Exception as e:
                logger.error(f"Error fetching Plex libraries: {e}", exc_info=True)
                # Don't fail the test if library fetch fails
                pass

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error testing Plex connection: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f"Server error: {str(e)}"
        })


@app.route('/api/wizard/stations')
def api_wizard_stations():
    """Get all available stations for the wizard

    Returns JSON:
        {
            "stations": [
                {"id": "us99", "name": "US99 99.5fm Chicago", "genre": "Country", "market": "Chicago"},
                ...
            ]
        }
    """
    try:
        db = current_app.config.get('db')
        if not db:
            return jsonify({'stations': []})

        cursor = db.get_cursor()
        try:
            cursor.execute("""
                SELECT id, name, genre, market
                FROM stations
                ORDER BY name
            """)

            stations = []
            for row in cursor.fetchall():
                stations.append({
                    'id': row[0],
                    'name': row[1],
                    'genre': row[2],
                    'market': row[3]
                })

            return jsonify({'stations': stations})
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Error fetching stations for wizard: {e}")
        return jsonify({'stations': []})


@app.route('/api/wizard/save', methods=['POST'])
def api_wizard_save():
    """Save wizard settings and create radio_monitor_settings.json

    Expects JSON:
        {
            "lidarr": {...},
            "plex": {...},
            "monitor": {...}
        }

    Returns JSON:
        {
            "success": true/false,
            "message": "Settings saved successfully"
        }
    """
    try:
        data = request.json

        # Build complete settings structure
        settings_dict = {
            'lidarr': data.get('lidarr', {}),
            'plex': data.get('plex', {}),
            'monitor': data.get('monitor', {}),
            'musicbrainz': {
                'rate_limit_delay': 1.0,
                'user_agent': 'RadioMonitor/2.0 (https://github.com/allurjj/radio-monitor)'
            },
            'gui': {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False
            },
            'database': {
                'backup_enabled': True,
                'backup_retention_days': 7,
                'backup_path': 'backups/'
            },
            'logging': {
                'file': 'radio_monitor.log',
                'max_bytes': 10485760,
                'backup_count': 5,
                'console_level': 'INFO',
                'file_level': 'ERROR'
            },
            'duplicate_detection_window_minutes': 75,
            'openrouter': {
                'api_key': '',
                'model': 'x-ai/grok-4-fast',
                'timeout_seconds': 90,
                'max_retries': 3,
                'rate_limit_per_minute': 1,
                'max_tokens': 200000,
                'max_songs_input': 5000
            }
        }

        # Save Lidarr API key directly in settings
        lidarr_api_key = settings_dict['lidarr'].get('api_key', '')
        if not lidarr_api_key:
            logger.warning("No Lidarr API key provided in wizard")

        # Update station enable/disable status in database based on wizard selections
        monitor_settings = data.get('monitor', {})
        selected_stations = monitor_settings.get('stations', [])

        if selected_stations:
            try:
                from flask import current_app
                db = current_app.config.get('db')
                if db:
                    cursor = db.get_cursor()
                    try:
                        # Disable all stations first
                        cursor.execute("UPDATE stations SET enabled = 0")
                        logger.info(f"Disabled all stations in database")

                        # Enable only the selected stations
                        for station_id in selected_stations:
                            cursor.execute(
                                "UPDATE stations SET enabled = 1 WHERE id = ?",
                                (station_id,)
                            )
                        logger.info(f"Enabled {len(selected_stations)} stations: {selected_stations}")

                        db.conn.commit()
                        logger.info("Station selections saved to database successfully")
                    finally:
                        cursor.close()
                else:
                    logger.warning("Database not available during wizard - station selections not saved to database")
            except Exception as e:
                logger.error(f"Error updating station selections in database: {e}")
                # Don't fail the wizard save if station update fails
                pass

        # Save settings to file
        if save_settings_to_file(settings_dict):
            logger.info("Wizard completed successfully - settings saved")
            return jsonify({
                'success': True,
                'message': 'Settings saved successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Error saving settings file'
            })

    except Exception as e:
        logger.error(f"Error saving wizard settings: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        })


# Before request handler - redirect to wizard if first run
@app.before_request
def check_first_run():
    """Redirect to wizard if this is the first run"""
    # Allow wizard, static files, all status API endpoints, and auth setup
    allowed_paths = [
        '/wizard',              # Wizard page
        '/api/wizard',         # Wizard API endpoints
        '/static',             # Static files (CSS, JS, images)
        '/api/monitor/status',  # Monitor status
        '/api/status/lidarr',   # Lidarr status
        '/api/status/plex',    # Plex status
        '/api/system/status',   # System status
        '/auth-setup'          # Auth setup page
    ]

    # Check if this is a first run
    if is_first_run():
        # Allow access to wizard and static files
        for allowed_path in allowed_paths:
            if request.path.startswith(allowed_path):
                return None

        # Redirect to wizard
        return redirect(url_for('wizard'))

    return None
