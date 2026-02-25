"""
Playlists Routes for Radio Monitor 1.0

Unified playlist management (manual + auto).
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify, request, current_app
from radio_monitor.auth import requires_auth

logger = logging.getLogger(__name__)

playlists_bp = Blueprint('playlists', __name__)

def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')

def get_scheduler():
    """Get scheduler instance from Flask app config"""
    return current_app.config.get('scheduler')

def scheduler_alive_callback(scheduler):
    """Create a callback that checks if scheduler is alive (not if scraping is running)

    Auto playlists should run regardless of scraping status - they only need the
    scheduler to be alive, not actively scraping.

    Args:
        scheduler: RadioScheduler instance

    Returns:
        Function that returns True if scheduler is alive
    """
    def callback():
        return scheduler.scheduler.running if scheduler and scheduler.scheduler else False
    return callback

@playlists_bp.route('/playlists')
@requires_auth
def playlists():
    """Playlist management page"""
    from radio_monitor.gui import is_first_run
    from flask import redirect, url_for

    if is_first_run():
        return redirect(url_for('wizard'))

    return render_template('playlists.html')

@playlists_bp.route('/api/plex/playlists', methods=['GET'])
@requires_auth
def api_playlists():
    """Get all playlists (manual and auto)

    Returns JSON:
        {
            "playlists": [...]
        }
    """
    db = get_db()
    db = get_db()
    if db:
        try:
            playlists = db.get_playlists()
            return jsonify({'playlists': playlists})
        except Exception as e:
            logger.error(f"Error getting playlists: {e}")
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Database not initialized'}), 500

@playlists_bp.route('/api/plex/playlists', methods=['POST'])
@requires_auth
def api_create_playlist():
    """Create new playlist (manual or auto)

    Expects JSON:
        {
            "name": "Playlist Name",
            "is_auto": true/false,
            "interval_minutes": 360,  // required if is_auto=true
            "station_ids": ["us99"],
            "max_songs": 50,
            "mode": "merge",
            "min_plays": 5,
            "max_plays": 100,  // optional
            "days": 30,
            "enabled": true
        }

    Returns JSON:
        {
            "success": true,
            "playlist": {...}
        }
    """
    db = get_db()
    scheduler = get_scheduler()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        data = request.json

        # Validate required fields
        required_fields = ['name', 'station_ids', 'max_songs', 'mode', 'is_auto']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Validate is_auto requirements
        if data['is_auto'] and 'interval_minutes' not in data:
            return jsonify({'error': 'interval_minutes required when is_auto=true'}), 400

        # Validate mode
        valid_modes = ['merge', 'replace', 'append', 'create', 'snapshot', 'recent', 'random']
        if data['mode'] not in valid_modes:
            return jsonify({'error': f'Invalid mode. Must be one of: {", ".join(valid_modes)}'}), 400

        # Validate max_plays > min_plays if both provided
        min_plays = data.get('min_plays', 1)
        max_plays = data.get('max_plays')
        if max_plays is not None and min_plays > max_plays:
            return jsonify({'error': 'min_plays cannot be greater than max_plays'}), 400

        # Validate interval (minimum 10 minutes, only for auto playlists)
        if data['is_auto']:
            interval = data.get('interval_minutes')
            if interval is None:
                return jsonify({'error': 'interval_minutes required when is_auto=true'}), 400
            if interval < 10:
                return jsonify({'error': 'interval_minutes must be at least 10'}), 400

        # Import auto playlist manager
        from radio_monitor.auto_playlists import AutoPlaylistManager

        # Get Plex config
        from radio_monitor.gui import load_settings
        settings = load_settings()
        plex_config = settings.get('plex', {})

        # Create playlist
        playlist_id = db.add_playlist(
            name=data['name'],
            is_auto=data['is_auto'],
            interval_minutes=data.get('interval_minutes'),
            station_ids=data['station_ids'],
            max_songs=data['max_songs'],
            mode=data['mode'],
            min_plays=min_plays,
            max_plays=max_plays,
            days=data.get('days'),
            enabled=data.get('enabled', True)
        )

        # If auto playlist, schedule it
        if data['is_auto']:
            from apscheduler.triggers.interval import IntervalTrigger

            # Calculate and set next update
            interval_minutes = data['interval_minutes']
            next_update = datetime.now() + timedelta(minutes=interval_minutes)

            # Update next_update in database
            db.cursor.execute("""
                UPDATE playlists
                SET next_update = ?
                WHERE id = ?
            """, (next_update, playlist_id))
            db.conn.commit()

            # Create a minimal auto playlist manager for scheduling
            auto_playlist_manager = AutoPlaylistManager(
                db=db,
                plex_config=plex_config,
                monitor_running_callback=scheduler_alive_callback(scheduler)
            )
            # Don't call initialize() - just set the scheduler reference
            auto_playlist_manager.scheduler = scheduler.scheduler

            # Get the playlist to schedule
            playlist = db.get_playlist(playlist_id)

            # Schedule just this one playlist (not all of them)
            job_id = f'auto_playlist_{playlist_id}'

            # Remove existing job if any
            if scheduler.scheduler.get_job(job_id):
                scheduler.scheduler.remove_job(job_id)

            # Add new job
            scheduler.scheduler.add_job(
                func=auto_playlist_manager._execute_auto_playlist,
                trigger=IntervalTrigger(minutes=interval_minutes),
                id=job_id,
                args=[playlist_id],
                name=f"Auto Playlist: {data['name']}",
                replace_existing=True
            )

            logger.info(f"Scheduled auto playlist '{data['name']}' (ID: {playlist_id}) every {interval_minutes} minutes")

        # Execute playlist immediately in background (so API returns quickly)
        # This prevents UI hanging for large playlists
        if scheduler:
            # Get database path for thread-local connection
            db_path = db.db_path if hasattr(db, 'db_path') else 'radio_songs.db'

            scheduler.scheduler.add_job(
                func=_execute_playlist_immediate,
                args=[playlist_id, db_path, plex_config],
                id=f'immediate_create_{playlist_id}_{datetime.now().timestamp()}',
                name=f"Immediate: Create playlist {playlist_id}"
            )
            logger.info(f"Scheduled immediate execution for playlist '{data['name']}' (ID: {playlist_id})")

        # Get created playlist
        playlist = db.get_playlist(playlist_id)

        logger.info(f"Created playlist '{data['name']}' (ID: {playlist_id}, auto: {data['is_auto']})")

        # Return success message indicating background execution
        return jsonify({
            'success': True,
            'playlist': playlist,
            'message': 'Playlist created successfully. It is being populated in the background - check back in a few moments.'
        })

    except Exception as e:
        logger.error(f"Error creating playlist: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@playlists_bp.route('/api/plex/playlists/<int:playlist_id>', methods=['PUT'])
@requires_auth
def api_update_playlist(playlist_id):
    """Update existing playlist (manual or auto)

    Expects JSON:
        {
            "name": "New Name",
            "is_auto": true/false,
            "interval_minutes": 60,
            ...
        }

    Returns JSON:
        {
            "success": true,
            "playlist": {...}
        }
    """
    db = get_db()
    scheduler = get_scheduler()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        data = request.json

        # Get current playlist FIRST (needed for validation below)
        current_playlist = db.get_playlist(playlist_id)
        if not current_playlist:
            return jsonify({'error': 'Playlist not found'}), 404

        # Validate mode if provided
        if 'mode' in data:
            valid_modes = ['merge', 'replace', 'append', 'create', 'snapshot', 'recent', 'random']
            if data['mode'] not in valid_modes:
                return jsonify({'error': f'Invalid mode. Must be one of: {", ".join(valid_modes)}'}), 400

        # Validate interval if provided (only for auto playlists)
        if 'interval_minutes' in data:
            # Check if this is or will be an auto playlist
            is_auto = data.get('is_auto', current_playlist.get('is_auto'))
            if is_auto:
                interval = data['interval_minutes']
                if interval is not None and interval < 10:
                    return jsonify({'error': 'interval_minutes must be at least 10 for auto playlists'}), 400

        # Validate max_plays > min_plays if both provided and not None
        if 'max_plays' in data and 'min_plays' in data:
            min_plays = data.get('min_plays')
            max_plays = data.get('max_plays')
            if min_plays is not None and max_plays is not None and min_plays > max_plays:
                return jsonify({'error': 'min_plays cannot be greater than max_plays'}), 400

        # Import auto playlist manager
        from radio_monitor.auto_playlists import AutoPlaylistManager

        # Get Plex config
        from radio_monitor.gui import load_settings
        settings = load_settings()
        plex_config = settings.get('plex', {})

        # Check if toggling is_auto
        is_toggling_auto = 'is_auto' in data and data['is_auto'] != current_playlist.get('is_auto')

        # Update playlist in database
        db.update_playlist(
            playlist_id=playlist_id,
            name=data.get('name'),
            is_auto=data.get('is_auto'),
            interval_minutes=data.get('interval_minutes'),
            station_ids=data.get('station_ids'),
            max_songs=data.get('max_songs'),
            mode=data.get('mode'),
            min_plays=data.get('min_plays'),
            max_plays=data.get('max_plays'),
            days=data.get('days')
        )

        # If toggling is_auto, need to add/remove from scheduler
        if is_toggling_auto:
            auto_playlist_manager = AutoPlaylistManager(
                db=db,
                plex_config=plex_config,
                monitor_running_callback=scheduler_alive_callback(scheduler)
            )
            auto_playlist_manager.initialize(scheduler.scheduler)

            new_is_auto = data['is_auto']

            if new_is_auto:
                # Enabling auto: add to scheduler
                interval_minutes = data.get('interval_minutes', current_playlist.get('interval_minutes'))
                if interval_minutes:
                    db.update_playlist_next_run(playlist_id, interval_minutes)

                updated_playlist = db.get_playlist(playlist_id)
                auto_playlist_manager.add_playlist(updated_playlist)
            else:
                # Disabling auto: remove from scheduler
                job_id = f'auto_playlist_{playlist_id}'
                if scheduler.scheduler.get_job(job_id):
                    scheduler.scheduler.remove_job(job_id)

        # Get updated playlist
        playlist = db.get_playlist(playlist_id)

        logger.info(f"Updated playlist ID {playlist_id}")

        return jsonify({
            'success': True,
            'playlist': playlist
        })

    except Exception as e:
        logger.error(f"Error updating playlist: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@playlists_bp.route('/api/plex/playlists/<int:playlist_id>', methods=['DELETE'])
@requires_auth
def api_delete_playlist(playlist_id):
    """Delete playlist (manual or auto)

    Returns JSON:
        {
            "success": true,
            "message": "Playlist deleted"
        }
    """
    db = get_db()
    scheduler = get_scheduler()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        # Import auto playlist manager
        from radio_monitor.auto_playlists import AutoPlaylistManager

        # Get Plex config
        from radio_monitor.gui import load_settings
        settings = load_settings()
        plex_config = settings.get('plex', {})

        # Get playlist to check if it's auto
        playlist = db.get_playlist(playlist_id)
        if not playlist:
            return jsonify({'error': 'Playlist not found'}), 404

        # If auto playlist, remove from scheduler first
        if playlist.get('is_auto'):
            auto_playlist_manager = AutoPlaylistManager(
                db=db,
                plex_config=plex_config,
                monitor_running_callback=scheduler_alive_callback(scheduler)
            )
            auto_playlist_manager.initialize(scheduler.scheduler)

            # Remove from scheduler
            job_id = f'auto_playlist_{playlist_id}'
            if scheduler.scheduler.get_job(job_id):
                scheduler.scheduler.remove_job(job_id)

        # Delete from database
        db.delete_playlist(playlist_id)

        logger.info(f"Deleted playlist ID {playlist_id}")

        return jsonify({
            'success': True,
            'message': 'Playlist deleted'
        })

    except Exception as e:
        logger.error(f"Error deleting playlist: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@playlists_bp.route('/api/plex/playlists/<int:playlist_id>/toggle-auto', methods=['POST'])
@requires_auth
def api_toggle_playlist_auto(playlist_id):
    """Toggle playlist between manual and auto

    Expects JSON:
        {
            "is_auto": true/false,
            "interval_minutes": 360  // required when enabling auto
        }

    Returns JSON:
        {
            "success": true,
            "message": "Auto updates enabled/disabled"
        }
    """
    db = get_db()
    scheduler = get_scheduler()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        data = request.json

        # Get current playlist
        playlist = db.get_playlist(playlist_id)
        if not playlist:
            return jsonify({'error': 'Playlist not found'}), 404

        new_is_auto = data.get('is_auto')

        # Validate interval_minutes when enabling auto
        if new_is_auto and 'interval_minutes' not in data:
            return jsonify({'error': 'interval_minutes required when enabling auto'}), 400

        if new_is_auto:
            interval = data.get('interval_minutes')
            if interval is None:
                return jsonify({'error': 'interval_minutes required when enabling auto'}), 400
            if interval < 10:
                return jsonify({'error': 'interval_minutes must be at least 10'}), 400

        # Import auto playlist manager
        from radio_monitor.auto_playlists import AutoPlaylistManager

        # Get Plex config
        from radio_monitor.gui import load_settings
        settings = load_settings()
        plex_config = settings.get('plex', {})

        # Update is_auto in database
        db.update_playlist(
            playlist_id=playlist_id,
            is_auto=new_is_auto,
            interval_minutes=data.get('interval_minutes') if new_is_auto else None
        )

        # Update scheduler
        auto_playlist_manager = AutoPlaylistManager(
            db=db,
            plex_config=plex_config,
            monitor_running_callback=lambda: scheduler.is_running() if scheduler else False
        )
        auto_playlist_manager.initialize(scheduler.scheduler)

        if new_is_auto:
            # Enabling auto: add to scheduler
            interval_minutes = data['interval_minutes']
            db.update_playlist_next_run(playlist_id, interval_minutes)

            updated_playlist = db.get_playlist(playlist_id)
            auto_playlist_manager.add_playlist(updated_playlist)

            logger.info(f"Enabled auto updates for playlist {playlist_id}")
        else:
            # Disabling auto: remove from scheduler
            job_id = f'auto_playlist_{playlist_id}'
            if scheduler.scheduler.get_job(job_id):
                scheduler.scheduler.remove_job(job_id)

            logger.info(f"Disabled auto updates for playlist {playlist_id}")

        return jsonify({
            'success': True,
            'message': 'Auto updates ' + ('enabled' if new_is_auto else 'disabled')
        })

    except Exception as e:
        logger.error(f"Error toggling auto: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@playlists_bp.route('/api/plex/playlists/<int:playlist_id>/execute', methods=['POST'])
@requires_auth
def api_execute_playlist(playlist_id):
    """Execute playlist immediately (create or update)

    Works for both manual and auto playlists.
    Shows results: "Tried to add X, added Y, Z not found"

    Returns JSON:
        {
            "success": true,
            "added": 37,
            "not_found": 13,
            "not_found_list": [...]
        }
    """
    db = get_db()
    scheduler = get_scheduler()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        # Get playlist
        playlist = db.get_playlist(playlist_id)
        if not playlist:
            return jsonify({'error': 'Playlist not found'}), 404

        logger.info(f"Executing playlist '{playlist['name']}' (ID: {playlist_id})")

        # Import Plex functions
        from radio_monitor.plex import create_playlist
        from plexapi.server import PlexServer
        from radio_monitor.notifications import send_notifications

        # Get Plex config
        from radio_monitor.gui import load_settings
        settings = load_settings()
        plex_config = settings.get('plex', {})

        # Connect to Plex
        try:
            plex = PlexServer(plex_config['url'], plex_config['token'])
        except Exception as plex_error:
            # Send notification for Plex connection failure
            error_msg = f"Could not connect to Plex server at {plex_config.get('url', 'localhost:32400')}. Please check:\n"
            error_msg += f"  1. Plex is running\n"
            error_msg += f"  2. Plex URL is correct in settings\n"
            error_msg += f"  3. Plex token is valid\n"
            error_msg += f"\nTechnical details: {str(plex_error)}"

            logger.error(f"Plex connection failed: {plex_error}")

            # Try to send notification
            try:
                send_notifications(
                    db,
                    'on_playlist_error',
                    f'Plex Connection Failed',
                    f'Could not connect to Plex while executing playlist "{playlist["name"]}". Check Plex server status and settings.',
                    'error',
                    {'playlist_name': playlist['name'], 'error': str(plex_error)}
                )
            except Exception as notify_error:
                logger.error(f"Failed to send error notification: {notify_error}")

            return jsonify({
                'error': error_msg,
                'added': 0,
                'not_found': 0
            }), 500

        # Build filters from playlist config
        filters = {
            'station_ids': playlist['station_ids'],
            'days': playlist.get('days'),
            'limit': playlist['max_songs'],
            'min_plays': playlist.get('min_plays', 1),
            'max_plays': playlist.get('max_plays'),
            'music_library_name': plex_config.get('library_name', 'Music')
        }

        # Create/update playlist
        logger.info(f"Calling create_playlist for '{playlist['name']}' with mode={playlist['mode']}, max_songs={playlist['max_songs']}")
        result = create_playlist(
            db=db,
            plex=plex,
            playlist_name=playlist['name'],
            mode=playlist['mode'],
            filters=filters
        )
        logger.info(f"create_playlist returned: added={result.get('added', 0)}, not_found={result.get('not_found', 0)}, error={result.get('error', 'None')}")

        # Update last_updated if successful
        if result.get('error'):
            logger.error(f"Error executing playlist: {result.get('error')}")
        else:
            # Update last_updated directly in database
            db.cursor.execute("""
                UPDATE playlists
                SET last_updated = ?
                WHERE id = ?
            """, (datetime.now(), playlist_id))
            db.conn.commit()
            logger.info(f"Playlist '{playlist['name']}' executed: {result.get('added', 0)} songs added")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error executing playlist: {e}", exc_info=True)
        return jsonify({'error': str(e), 'added': 0, 'not_found': 0}), 500

@playlists_bp.route('/api/plex/playlists/<int:playlist_id>/trigger', methods=['POST'])
@requires_auth
def api_trigger_playlist(playlist_id):
    """Trigger immediate update of auto playlist (alias for execute)

    This is an alias for /execute that's used by the "Update Now" button.
    Only works for auto playlists.

    Returns JSON:
        {
            "success": true,
            "message": "Update triggered"
        }
    """
    db = get_db()
    scheduler = get_scheduler()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        # Get playlist to verify it's an auto playlist
        playlist = db.get_playlist(playlist_id)
        if not playlist:
            return jsonify({'error': 'Playlist not found'}), 404

        if not playlist.get('is_auto'):
            return jsonify({'error': 'This operation is only for auto playlists'}), 400

        # Import auto playlist manager
        from radio_monitor.auto_playlists import AutoPlaylistManager

        # Get Plex config
        from radio_monitor.gui import load_settings
        settings = load_settings()
        plex_config = settings.get('plex', {})

        # Create auto playlist manager
        auto_playlist_manager = AutoPlaylistManager(
            db=db,
            plex_config=plex_config,
            monitor_running_callback=lambda: scheduler.is_running() if scheduler else False
        )
        auto_playlist_manager.initialize(scheduler.scheduler)

        # Trigger update
        auto_playlist_manager.trigger_update(playlist_id)

        logger.info(f"Triggered immediate update for auto playlist ID {playlist_id}")

        return jsonify({
            'success': True,
            'message': 'Update triggered'
        })

    except Exception as e:
        logger.error(f"Error triggering playlist update: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

def _execute_playlist_immediate(playlist_id, db_path, plex_config):
    """Execute a playlist immediately (called by scheduler in background)

    This function is called by the scheduler to execute a playlist creation/update
    in the background, preventing the API from blocking on large playlists.

    IMPORTANT: Uses a thread-local database connection to avoid blocking Flask requests.

    Args:
        playlist_id: ID of playlist to execute
        db_path: Path to database file (creates its own connection)
        plex_config: Dict with Plex connection info
    """
    # Create thread-local database connection
    from radio_monitor.database import RadioDatabase

    # Create a fresh RadioDatabase instance with its own connection
    db = RadioDatabase(db_path)
    db.connect()  # This creates a new connection for this thread

    try:
        from radio_monitor.plex import create_playlist
        from plexapi.server import PlexServer

        # Get the playlist
        playlist = db.get_playlist(playlist_id)
        if not playlist:
            logger.error(f"Playlist {playlist_id} not found for immediate execution")
            return

        logger.info(f"Executing playlist '{playlist['name']}' immediately (background)")

        # Connect to Plex
        plex = PlexServer(plex_config['url'], plex_config['token'])

        # Build filters from playlist config
        filters = {
            'station_ids': playlist['station_ids'],
            'days': playlist.get('days'),
            'limit': playlist['max_songs'],
            'min_plays': playlist.get('min_plays', 1),
            'max_plays': playlist.get('max_plays'),
            'music_library_name': plex_config.get('library_name', 'Music')
        }

        # Create/update playlist in Plex
        result = create_playlist(
            db=db,
            plex=plex,
            playlist_name=playlist['name'],
            mode=playlist['mode'],
            filters=filters
        )

        # Update last_updated if successful
        if not result.get('error'):
            db.cursor.execute("""
                UPDATE playlists
                SET last_updated = ?
                WHERE id = ?
            """, (datetime.now(), playlist_id))
            db.conn.commit()
            logger.info(f"Background execution complete: '{playlist['name']}' - {result.get('added', 0)} songs added")
        else:
            logger.error(f"Background execution failed: '{playlist['name']}' - {result.get('error')}")

    except Exception as e:
        logger.error(f"Error in background playlist execution {playlist_id}: {e}", exc_info=True)
    finally:
        # Always close the thread-local connection
        try:
            db.close()
        except:
            pass
