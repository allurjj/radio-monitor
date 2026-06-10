"""
Lidarr Routes for Radio Monitor 1.0

Artist import interface for Lidarr.
"""

import logging
from flask import Blueprint, render_template, jsonify, request, current_app
from radio_monitor.auth import requires_auth

logger = logging.getLogger(__name__)

lidarr_bp = Blueprint('lidarr', __name__)


def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')


@lidarr_bp.route('/lidarr')
@requires_auth
def lidarr():
    """Lidarr import page"""
    from radio_monitor.gui import is_first_run
    from flask import redirect, url_for

    if is_first_run():
        return redirect(url_for('wizard'))

    return render_template('lidarr.html')


@lidarr_bp.route('/api/lidarr/artists')
@requires_auth
def api_lidarr_artists():
    """Get artists that need Lidarr import

    Query params:
        min_plays: Minimum total plays (default: 5)
        station: Optional station ID to filter by (default: "all")
        sort: Column to sort by - 'name' | 'total_plays' (default: 'total_plays')
        direction: Sort direction - 'asc' | 'desc' (default: 'desc')

    Returns JSON:
        [
            {
                "mbid": "20244d07-534f-4eff-b4d4-930878889970",
                "name": "Taylor Swift",
                "total_plays": 15
            },
            ...
        ]
    """
    db = get_db()
    if db:
        try:
            min_plays = request.args.get('min_plays', 5, type=int)
            station = request.args.get('station', 'all')
            sort = request.args.get('sort', 'total_plays')
            direction = request.args.get('direction', 'desc')

            # Validate direction
            if direction not in ['asc', 'desc']:
                direction = 'desc'

            artists = db.get_artists_for_import(
                min_plays=min_plays,
                station_id=station,
                sort=sort,
                direction=direction
            )
            return jsonify(artists)
        except Exception as e:
            import traceback
            logger.error(f"Error getting artists for import: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Database not initialized'}), 500


@lidarr_bp.route('/api/lidarr/import', methods=['POST'])
@requires_auth
def api_lidarr_import():
    """Import selected artists to Lidarr

    Expects JSON:
        {
            "mbids": ["mbid1", "mbid2", ...]
        }

    Returns JSON:
        {
            "results": [
                {
                    "mbid": "mbid1",
                    "success": true,
                    "message": "Imported successfully"
                },
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
        from radio_monitor.lidarr import import_artist_to_lidarr

        data = request.json
        mbids = data.get('mbids', [])

        if not mbids:
            return jsonify({'error': 'No MBIDs provided'}), 400

        results = []

        # Import each artist
        for mbid in mbids:
            # Get artist details from database
            artist = db.get_artist_by_mbid(mbid)
            if not artist:
                results.append({
                    'mbid': mbid,
                    'success': False,
                    'message': 'Artist not found in database'
                })
                continue

            # Import to Lidarr
            success, message = import_artist_to_lidarr(mbid, artist['name'], settings)

            result = {
                'mbid': mbid,
                'success': success,
                'message': message
            }
            results.append(result)

            # Mark as imported in database if successful
            if success:
                db.mark_artist_imported_to_lidarr(mbid)

        # Calculate summary counts
        imported = sum(1 for r in results if r['success'] and 'Imported' in r.get('message', ''))
        already_exists = sum(1 for r in results if r['success'] and 'exists' in r.get('message', '').lower())
        failed = sum(1 for r in results if not r['success'])

        return jsonify({
            'success': failed == 0,
            'imported': imported,
            'already_exists': already_exists,
            'failed': failed,
            'results': results
        })

    except Exception as e:
        logger.error(f"Error importing to Lidarr: {e}")
        return jsonify({'error': str(e)}), 500


@lidarr_bp.route('/api/test/lidarr', methods=['POST'])
@requires_auth
def api_test_lidarr():
    """Test Lidarr connection (from settings page)

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
    from radio_monitor.lidarr import test_lidarr_connection

    try:
        data = request.json
        url = data.get('url', '')
        api_key = data.get('api_key', '')

        if not url or not api_key:
            return jsonify({
                'success': False,
                'message': 'URL and API key are required'
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

        return jsonify({
            'success': success,
            'message': message
        })

    except Exception as e:
        logger.error(f"Error testing Lidarr: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        })


@lidarr_bp.route('/api/lidarr/root-folders', methods=['GET'])
@requires_auth
def api_lidarr_root_folders():
    """Get available root folders from Lidarr

    Returns JSON:
        {
            "success": true/false,
            "folders": [
                {"path": "/data/music", "freeSpace": 1000000000, "id": 1},
                ...
            ] or {"error": "error message"}
        }
    """
    from radio_monitor.gui import load_settings
    from radio_monitor.lidarr import get_lidarr_root_folders

    try:
        # Load current settings
        current_settings = load_settings()
        if not current_settings:
            return jsonify({
                'success': False,
                'error': 'Settings not configured'
            })

        # Get root folders from Lidarr
        folders = get_lidarr_root_folders(current_settings)

        if folders is None:
            return jsonify({
                'success': False,
                'error': 'Failed to connect to Lidarr'
            })

        return jsonify({
            'success': True,
            'folders': folders
        })

    except Exception as e:
        logger.error(f"Error getting Lidarr root folders: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@lidarr_bp.route('/api/lidarr/quality-profiles', methods=['GET'])
@requires_auth
def api_lidarr_quality_profiles():
    """Get available quality profiles from Lidarr

    Returns JSON:
        {
            "success": true/false,
            "profiles": [
                {"id": 1, "name": "Lossless"},
                {"id": 2, "name": "High Quality"},
                ...
            ] or {"error": "error message"}
        }
    """
    from radio_monitor.gui import load_settings
    from radio_monitor.lidarr import get_lidarr_quality_profiles

    try:
        # Load current settings
        current_settings = load_settings()
        if not current_settings:
            return jsonify({
                'success': False,
                'error': 'Settings not configured'
            })

        # Get quality profiles from Lidarr
        profiles = get_lidarr_quality_profiles(current_settings)

        if profiles is None:
            return jsonify({
                'success': False,
                'error': 'Failed to connect to Lidarr'
            })

        return jsonify({
            'success': True,
            'profiles': profiles
        })

    except Exception as e:
        logger.error(f"Error getting Lidarr quality profiles: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@lidarr_bp.route('/api/lidarr/metadata-profiles', methods=['GET'])
@requires_auth
def api_lidarr_metadata_profiles():
    """Get available metadata profiles from Lidarr

    Returns JSON:
        {
            "success": true/false,
            "profiles": [
                {"id": 1, "name": "Standard"},
                {"id": 2, "name": "Strict"},
                ...
            ] or {"error": "error message"}
        }
    """
    from radio_monitor.gui import load_settings
    from radio_monitor.lidarr import get_lidarr_metadata_profiles

    try:
        # Load current settings
        current_settings = load_settings()
        if not current_settings:
            return jsonify({
                'success': False,
                'error': 'Settings not configured'
            })

        # Get metadata profiles from Lidarr
        profiles = get_lidarr_metadata_profiles(current_settings)

        if profiles is None:
            return jsonify({
                'success': False,
                'error': 'Failed to connect to Lidarr'
            })

        return jsonify({
            'success': True,
            'profiles': profiles
        })

    except Exception as e:
        logger.error(f"Error getting Lidarr metadata profiles: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@lidarr_bp.route('/api/lidarr/reset-import-status', methods=['POST'])
@requires_auth
def api_reset_import_status():
    """Reset all artists to "Needs Import" status

    Useful when sharing databases with friends or re-importing to Lidarr.

    Returns JSON:
        {
            "success": true,
            "count": 453,
            "message": "Reset 453 artists to 'Needs Import'"
        }
    """
    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        # Reset all artists
        count = db.reset_all_lidarr_import_status()

        logger.info(f"Reset import status for {count} artists")

        return jsonify({
            'success': True,
            'count': count,
            'message': f"Reset {count} artists to 'Needs Import'"
        })

    except Exception as e:
        logger.error(f"Error resetting import status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@lidarr_bp.route('/api/lidarr/import/<mbid>', methods=['POST'])
@requires_auth
def api_lidarr_import_artist(mbid):
    """Import a single artist to Lidarr

    Returns JSON:
        {
            "success": true/false,
            "message": "Imported successfully" or error message,
            "already_exists": true/false
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
        from radio_monitor.lidarr import import_artist_to_lidarr

        # Get artist details from database
        artist = db.get_artist_by_mbid(mbid)
        if not artist:
            return jsonify({
                'success': False,
                'message': 'Artist not found in database'
            }), 404

        # Check if artist has PENDING MBID
        if mbid.startswith('PENDING-'):
            return jsonify({
                'success': False,
                'message': 'Cannot import artist with pending MBID lookup'
            }), 400

        # Import to Lidarr
        success, message = import_artist_to_lidarr(mbid, artist['name'], settings)

        if success:
            # Mark as imported in database
            db.mark_artist_imported_to_lidarr(mbid)

            # Check if it was already in Lidarr
            already_exists = "already exists" in message.lower()

            logger.info(f"Imported artist {artist['name']} to Lidarr: {message}")

            return jsonify({
                'success': True,
                'message': message,
                'already_exists': already_exists
            })
        else:
            logger.warning(f"Failed to import {artist['name']}: {message}")
            return jsonify({
                'success': False,
                'message': message
            }), 400

    except Exception as e:
        logger.error(f"Error importing artist to Lidarr: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
