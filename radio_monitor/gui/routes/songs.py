"""
Songs routes for Radio Monitor GUI

Provides list and detail views for songs with pagination, filtering, and sorting.
"""

import logging
from flask import Blueprint, render_template, jsonify, request, current_app
from radio_monitor.auth import requires_auth

logger = logging.getLogger(__name__)

songs_bp = Blueprint('songs', __name__)


def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')


@songs_bp.route('/songs')
@requires_auth
def songs_list():
    """Songs list page with pagination and filtering"""
    db = get_db()
    from radio_monitor.database.queries import get_all_stations

    if not db:
        return render_template('error.html', error='Database not initialized'), 500

    # Get query parameters
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 50))
    search = request.args.get('search', '')
    artist_name = request.args.get('artist_name', '')
    station_id = request.args.get('station_id', '')
    sort = request.args.get('sort', 'title')
    direction = request.args.get('direction', 'asc')

    # Validate direction
    if direction not in ['asc', 'desc']:
        direction = 'asc'

    # Validate sort column (whitelist)
    valid_columns = ['title', 'artist_name', 'play_count', 'last_seen']
    if sort not in valid_columns:
        sort = 'title'

    # Advanced filters
    last_seen_after = request.args.get('last_seen_after', '')
    last_seen_before = request.args.get('last_seen_before', '')
    plays_min = request.args.get('plays_min', '')
    plays_max = request.args.get('plays_max', '')

    # Build filters dict
    filters = {}
    if search:
        filters['search'] = search
    if artist_name:
        filters['artist_name'] = artist_name
    if station_id:
        filters['station_id'] = station_id
    if last_seen_after:
        filters['last_seen_after'] = last_seen_after
    if last_seen_before:
        filters['last_seen_before'] = last_seen_before
    if plays_min:
        filters['plays_min'] = plays_min
    if plays_max:
        filters['plays_max'] = plays_max

    # Get songs
    cursor = db.get_cursor()
    try:
        from radio_monitor.database.queries import get_songs_paginated
        result = get_songs_paginated(cursor, page, limit, filters, sort, direction)
        stations = get_all_stations(cursor)
    finally:
        cursor.close()

    return render_template('songs.html',
                          songs=result['items'],
                          pagination={
                              'page': page,
                              'pages': result['pages'],
                              'total': result['total'],
                              'limit': limit
                          },
                          filters=filters,
                          sort=sort,
                          direction=direction,
                          stations=stations)


@songs_bp.route('/songs/<int:song_id>')
@requires_auth
def song_detail(song_id):
    """Song detail page with tabs for overview, history, Plex status"""
    db = get_db()
    from radio_monitor.database.queries import get_song_detail, get_song_play_history

    if not db:
        return render_template('error.html', error='Database not initialized'), 500

    cursor = db.get_cursor()
    try:
        # Get song details
        song = get_song_detail(cursor, song_id)
        if not song:
            return render_template('error.html', error=f"Song not found: {song_id}"), 404

        # Get play history
        history = get_song_play_history(cursor, song_id, days=90)
    finally:
        cursor.close()

    return render_template('song_detail.html',
                          song=song,
                          history=history)


# ==================== API ENDPOINTS ====================

@songs_bp.route('/api/songs')
@requires_auth
def api_songs():
    """API endpoint for songs with filtering and pagination"""
    db = get_db()
    from radio_monitor.database.queries import get_songs_paginated

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    # Get query parameters
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 50))
    search = request.args.get('search', '')
    artist_name = request.args.get('artist_name', '')
    station_id = request.args.get('station_id', '')
    sort = request.args.get('sort', 'title')
    direction = request.args.get('direction', 'asc')

    # Validate direction
    if direction not in ['asc', 'desc']:
        direction = 'asc'

    # Validate sort column (whitelist)
    valid_columns = ['title', 'artist_name', 'play_count', 'last_seen']
    if sort not in valid_columns:
        sort = 'title'

    # Advanced filters
    last_seen_after = request.args.get('last_seen_after', '')
    last_seen_before = request.args.get('last_seen_before', '')
    plays_min = request.args.get('plays_min', '')
    plays_max = request.args.get('plays_max', '')

    # Build filters dict
    filters = {}
    if search:
        filters['search'] = search
    if artist_name:
        filters['artist_name'] = artist_name
    if station_id:
        filters['station_id'] = station_id
    if last_seen_after:
        filters['last_seen_after'] = last_seen_after
    if last_seen_before:
        filters['last_seen_before'] = last_seen_before
    if plays_min:
        filters['plays_min'] = plays_min
    if plays_max:
        filters['plays_max'] = plays_max

    # Get songs
    cursor = db.get_cursor()
    try:
        result = get_songs_paginated(cursor, page, limit, filters, sort, direction)
    finally:
        cursor.close()

    return jsonify({
        'items': result['items'],
        'pagination': {
            'page': page,
            'pages': result['pages'],
            'total': result['total'],
            'limit': limit
        }
    })


@songs_bp.route('/api/songs/<int:song_id>')
@requires_auth
def api_song_detail(song_id):
    """API endpoint for single song details"""
    db = get_db()
    from radio_monitor.database.queries import get_song_detail

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()
    try:
        song = get_song_detail(cursor, song_id)
    finally:
        cursor.close()

    if not song:
        return jsonify({'error': 'Song not found'}), 404

    return jsonify(song)


@songs_bp.route('/api/songs/<int:song_id>/history')
@requires_auth
def api_song_history(song_id):
    """API endpoint for song's play history"""
    db = get_db()
    from radio_monitor.database.queries import get_song_play_history

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    days = int(request.args.get('days', 30))

    cursor = db.get_cursor()
    try:
        history = get_song_play_history(cursor, song_id, days)
    finally:
        cursor.close()

    return jsonify({
        'items': history,
        'count': len(history),
        'days': days
    })
