"""
Plex Routes for Radio Monitor 1.0

Plex playlist generation interface.
"""

import logging
from flask import Blueprint, render_template, jsonify, request, current_app
from radio_monitor.auth import requires_auth

logger = logging.getLogger(__name__)

plex_bp = Blueprint('plex', __name__)

def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')

@plex_bp.route('/plex')
@requires_auth
def plex():
    """Plex playlist page"""
    from radio_monitor.gui import is_first_run
    from flask import redirect, url_for

    if is_first_run():
        return redirect(url_for('wizard'))

    return render_template('plex.html')

@plex_bp.route('/api/plex/preview', methods=['POST'])
@requires_auth
def api_plex_preview():
    """Preview songs for Plex playlist

    Expects JSON:
        {
            "filters": {
                "days": 7,
                "station_ids": ["us99"],  // Array of station IDs
                "limit": 50
            }
        }

    Returns JSON:
        {
            "songs": [
                {
                    "artist_name": "Taylor Swift",
                    "song_title": "Anti-Hero",
                    "play_count": 15
                },
                ...
            ]
        }
    """
    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        data = request.json
        filters = data.get('filters', {})

        days = filters.get('days', 7)
        station_ids = filters.get('station_ids')  # Now accepts array
        limit = filters.get('limit')

        # Get top songs (returns tuples: song_id, song_title, artist_name, play_count)
        songs = db.get_top_songs(days=days, station_ids=station_ids, limit=limit)

        # Convert tuples to dictionaries for JSON response
        songs_dict = [
            {
                'song_id': song[0],
                'song_title': song[1],
                'artist_name': song[2],
                'play_count': song[3]
            }
            for song in songs
        ]

        return jsonify({'songs': songs_dict})

    except Exception as e:
        logger.error(f"Error previewing playlist: {e}")
        return jsonify({'error': str(e)}), 500

@plex_bp.route('/api/plex/create', methods=['POST'])
@requires_auth
def api_plex_create():
    """Create Plex playlist

    Expects JSON:
        {
            "name": "Radio Hits",
            "mode": "merge",
            "filters": {
                "days": 7,
                "station_id": "limit": 50
            }
        }

    Returns JSON:
        {
            "added": 45,
            "not_found": 5,
            "not_found_list": [
                {"artist_name": "Artist", "song_title": "Song"},
                ...
            ]
        }
    """
    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    from radio_monitor.gui import load_settings
    settings = load_settings()
    if not settings:
        return jsonify({'error': 'Settings not loaded'}), 500

    try:
        from radio_monitor.plex import create_playlist
        from plexapi.server import PlexServer

        data = request.json
        playlist_name = data.get('name')
        mode = data.get('mode', 'merge')
        filters = data.get('filters', {})

        logger.info(f"Creating Plex playlist: name={playlist_name}, mode={mode}, filters={filters}")

        if not playlist_name:
            logger.warning("Playlist name is required")
            return jsonify({'error': 'Playlist name is required'}), 400

        # Connect to Plex
        plex_url = settings.get('plex', {}).get('url', 'http://localhost:32400')
        plex_token = settings.get('plex', {}).get('token', '')

        logger.info(f"Connecting to Plex at {plex_url}")

        if not plex_token:
            logger.error("Plex token not configured")
            return jsonify({'error': 'Plex token not configured'}), 400

        plex = PlexServer(plex_url, plex_token, timeout=30)
        music_library_name = settings.get('plex', {}).get('music_library_name', 'Music')
        music_library = plex.library.section(music_library_name)

        logger.info(f"Using Plex music library: {music_library_name}")

        # Get top songs
        days = filters.get('days', 7)
        station_ids = filters.get('station_ids')  # Now accepts array
        limit = filters.get('limit')

        logger.info(f"Fetching songs: days={days}, station_ids={station_ids}, limit={limit}")

        songs = db.get_top_songs(days=days, station_ids=station_ids, limit=limit)

        logger.info(f"Found {len(songs)} songs in database")

        # Create playlist
        logger.info("Calling create_playlist function...")
        result = create_playlist(db, plex, playlist_name, mode, filters)

        logger.info(f"Playlist created: added={result.get('added')}, not_found={result.get('not_found')}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error creating Plex playlist: {e}", exc_info=True)
        return jsonify({
            'added': 0,
            'not_found': 0,
            'error': str(e)
        }), 500

@plex_bp.route('/api/test/plex', methods=['POST'])
@requires_auth
def api_test_plex():
    """Test Plex connection (from settings page)

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
    from radio_monitor.plex import test_plex_connection

    try:
        data = request.json
        url = data.get('url', '')
        token = data.get('token', '')

        if not url or not token:
            return jsonify({
                'success': False,
                'message': 'URL and token are required'
            })

        # Create temporary settings
        temp_settings = {
            'plex': {
                'url': url,
                'token': token
            }
        }

        # Test connection
        success, message = test_plex_connection(temp_settings)

        return jsonify({
            'success': success,
            'message': message
        })

    except Exception as e:
        logger.error(f"Error testing Plex: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        })

@plex_bp.route('/api/plex/libraries', methods=['GET'])
@requires_auth
def api_plex_libraries():
    """Get available music libraries from Plex

    Returns JSON:
        {
            "success": true/false,
            "libraries": [
                {"name": "Music", "key": "/library/sections/1"},
                {"name": "Music Library", "key": "/library/sections/2"},
                ...
            ] or {"error": "error message"}
        }
    """
    from radio_monitor.gui import load_settings
    from radio_monitor.plex import get_plex_libraries

    try:
        # Load current settings
        current_settings = load_settings()
        if not current_settings:
            return jsonify({
                'success': False,
                'error': 'Settings not configured'
            })

        # Get libraries from Plex
        libraries = get_plex_libraries(current_settings)

        if libraries is None:
            return jsonify({
                'success': False,
                'error': 'Failed to connect to Plex'
            })

        return jsonify({
            'success': True,
            'libraries': libraries
        })

    except Exception as e:
        logger.error(f"Error getting Plex libraries: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })
