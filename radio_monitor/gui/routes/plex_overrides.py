"""
Plex manual override management routes
"""

from flask import Blueprint, render_template, request, jsonify, current_app
from radio_monitor.database.plex_overrides import (
    add_plex_override, get_plex_override, get_all_overrides,
    delete_override, toggle_override_active, update_override
)
from radio_monitor.auth import requires_auth

plex_overrides_bp = Blueprint('plex_overrides', __name__)


@plex_overrides_bp.route('/plex-overrides')
@requires_auth
def overrides_list():
    """Render Plex overrides management page"""
    db = current_app.config.get('db')
    cursor = db.get_cursor()
    try:
        overrides = get_all_overrides(cursor, active_only=True, limit=1000)
        return render_template('plex_overrides.html', overrides=overrides)
    finally:
        cursor.close()


@plex_overrides_bp.route('/api/plex-overrides', methods=['GET'])
@requires_auth
def api_get_overrides():
    """Get all overrides (JSON API)"""
    db = current_app.config.get('db')
    cursor = db.get_cursor()
    try:
        overrides = get_all_overrides(cursor, active_only=True)
        return jsonify({'overrides': overrides})
    finally:
        cursor.close()


@plex_overrides_bp.route('/api/plex-overrides/<int:song_id>', methods=['GET'])
@requires_auth
def api_get_override(song_id):
    """Get override for a specific song"""
    db = current_app.config.get('db')
    cursor = db.get_cursor()
    try:
        override = get_plex_override(cursor, song_id)
        return jsonify({'override': override})
    finally:
        cursor.close()


@plex_overrides_bp.route('/api/plex-overrides', methods=['POST'])
@requires_auth
def api_add_override():
    """Add a new manual override"""
    data = request.get_json()

    song_id = data.get('song_id')
    plex_track_key = data.get('plex_track_key')
    plex_track_title = data.get('plex_track_title')
    plex_artist_name = data.get('plex_artist_name')
    plex_album_title = data.get('plex_album_title')
    plex_year = data.get('plex_year')
    plex_duration_ms = data.get('plex_duration_ms')
    notes = data.get('notes')

    if not all([song_id, plex_track_key, plex_track_title, plex_artist_name]):
        return jsonify({'error': 'Missing required fields'}), 400

    db = current_app.config.get('db')
    cursor = db.get_cursor()
    try:
        override_id = add_plex_override(
            cursor, song_id, plex_track_key,
            plex_track_title, plex_artist_name,
            plex_album_title, plex_year, plex_duration_ms, notes
        )
        if override_id:
            db.conn.commit()
            return jsonify({'success': True, 'override_id': override_id})
        else:
            return jsonify({'error': 'Failed to add override'}), 500
    finally:
        cursor.close()


@plex_overrides_bp.route('/api/plex-overrides/<int:override_id>', methods=['DELETE'])
@requires_auth
def api_delete_override(override_id):
    """Delete an override"""
    db = current_app.config.get('db')
    cursor = db.get_cursor()
    try:
        if delete_override(cursor, override_id):
            db.conn.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Override not found'}), 404
    finally:
        cursor.close()


@plex_overrides_bp.route('/api/plex-overrides/<int:override_id>/toggle', methods=['PUT'])
@requires_auth
def api_toggle_override(override_id):
    """Toggle override active state"""
    data = request.get_json()
    is_active = data.get('is_active', True)

    db = current_app.config.get('db')
    cursor = db.get_cursor()
    try:
        if toggle_override_active(cursor, override_id, is_active):
            db.conn.commit()
            return jsonify({'success': True, 'is_active': is_active})
        else:
            return jsonify({'error': 'Override not found'}), 404
    finally:
        cursor.close()


@plex_overrides_bp.route('/api/plex-search-for-override', methods=['GET'])
@requires_auth
def api_search_plex_for_override():
    """Search Plex library for manual override matching"""
    song_title = request.args.get('song_title')
    artist_name = request.args.get('artist_name')

    if not song_title or not artist_name:
        return jsonify({'error': 'Missing search parameters'}), 400

    # Get Plex settings and create connection on demand
    settings = current_app.config.get('settings')
    if not settings:
        return jsonify({'error': 'Settings not loaded'}), 500

    plex_config = settings.get('plex', {})
    plex_url = plex_config.get('url')
    plex_token = plex_config.get('token')

    if not plex_url or not plex_token:
        return jsonify({'error': 'Plex not configured. Please check your Plex settings.'}), 500

    try:
        from plexapi.server import PlexServer
        plex = PlexServer(plex_url, plex_token, timeout=30)
    except Exception as e:
        logger.error(f"Failed to connect to Plex: {e}")
        return jsonify({'error': f'Failed to connect to Plex: {str(e)}'}), 500

    music_library_name = plex_config.get('library_name', 'Music')

    try:
        music_library = plex.library.section(music_library_name)
        tracks = music_library.search(title=song_title, libtype='track', maxresults=100)

        results = []
        for track in tracks:
            try:
                track_artist = track.artist().title if track.artist() else "Unknown"
                track_album = track.album().title if track.album() else None
                track_year = track.album().year if track.album() else None
                track_duration_ms = track.duration if track.duration else 0

                duration_seconds = track_duration_ms // 1000
                duration_formatted = f"{duration_seconds // 60}:{duration_seconds % 60:02d}"

                results.append({
                    'rating_key': track.ratingKey,
                    'title': track.title,
                    'artist': track_artist,
                    'album': track_album,
                    'year': track_year,
                    'duration_ms': track_duration_ms,
                    'duration_formatted': duration_formatted
                })
            except Exception:
                continue

        return jsonify({
            'search_title': song_title,
            'search_artist': artist_name,
            'results': results,
            'total': len(results)
        })
    except Exception as e:
        return jsonify({'error': f'Plex search failed: {str(e)}'}), 500
