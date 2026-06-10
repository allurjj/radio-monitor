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


@songs_bp.route('/api/songs/<int:song_id>/change-artist', methods=['POST'])
@requires_auth
def api_change_song_artist(song_id):
    """API endpoint to change a song's artist assignment

    Updates the song's artist_mbid and artist_name to point to a different
    existing artist. Handles blocklist updates and validates for duplicates.

    Request JSON:
        new_artist_mbid: MusicBrainz ID of the new artist (required)

    Returns:
        JSON response with success status and details
    """
    from radio_monitor.database.activity import log_activity

    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    data = request.get_json()
    new_artist_mbid = data.get('new_artist_mbid', '').strip()

    if not new_artist_mbid:
        return jsonify({'error': 'new_artist_mbid is required'}), 400

    cursor = db.get_cursor()
    try:
        # Step 1: Get current song details
        cursor.execute("""
            SELECT id, artist_mbid, artist_name, song_title
            FROM songs
            WHERE id = ?
        """, (song_id,))
        song = cursor.fetchone()

        if not song:
            return jsonify({'error': 'Song not found'}), 404

        current_song_id, current_artist_mbid, current_artist_name, song_title = song

        # Step 2: Validate - can't select the same artist
        if current_artist_mbid == new_artist_mbid:
            return jsonify({'error': 'Song is already assigned to this artist'}), 400

        # Step 3: Get new artist details
        cursor.execute("""
            SELECT mbid, name
            FROM artists
            WHERE mbid = ?
        """, (new_artist_mbid,))
        new_artist = cursor.fetchone()

        if not new_artist:
            return jsonify({'error': 'Selected artist not found in database'}), 404

        new_artist_mbid_actual, new_artist_name = new_artist

        # Step 4: Check for duplicate song (same artist + title)
        cursor.execute("""
            SELECT id
            FROM songs
            WHERE artist_mbid = ? AND song_title = ?
        """, (new_artist_mbid, song_title))
        duplicate = cursor.fetchone()

        if duplicate:
            duplicate_id = duplicate[0]
            return jsonify({
                'error': f'Duplicate song detected. The artist "{new_artist_name}" already has a song titled "{song_title}" (ID: {duplicate_id}). '
                        f'Please delete the duplicate song first or merge them manually.',
                'duplicate_song_id': duplicate_id,
                'duplicate_artist_name': new_artist_name,
                'duplicate_song_title': song_title
            }), 409

        # Step 5: All validations passed - perform the update
        # Use connection as context manager for automatic transaction
        with db.conn:
            # Update the song's artist assignment
            cursor.execute("""
                UPDATE songs
                SET artist_mbid = ?, artist_name = ?
                WHERE id = ?
            """, (new_artist_mbid, new_artist_name, song_id))

            # Update any blocklist entries that reference the old artist_mbid for this song
            cursor.execute("""
                UPDATE blocklist
                SET artist_mbid = ?
                WHERE song_id = ? AND artist_mbid = ?
            """, (new_artist_mbid, song_id, current_artist_mbid))

            blocklist_updated = cursor.rowcount

            # Note: We DO NOT delete the old artist even if no songs remain
            # User decision: Keep old artist records for safety

            # Log activity
            log_activity(
                cursor=cursor,
                event_type='song_artist_changed',
                title=f'Song "{song_title}" reassigned to artist "{new_artist_name}"',
                description=f'Moved from "{current_artist_name}" to "{new_artist_name}". '
                           f'{blocklist_updated} blocklist entries updated.',
                metadata={
                    'song_id': song_id,
                    'song_title': song_title,
                    'old_artist_mbid': current_artist_mbid,
                    'old_artist_name': current_artist_name,
                    'new_artist_mbid': new_artist_mbid,
                    'new_artist_name': new_artist_name,
                    'blocklist_updated': blocklist_updated
                },
                severity='info',
                source='user'
            )

        logger.info(f"Changed artist for song '{song_title}' (ID: {song_id}) "
                   f"from '{current_artist_name}' to '{new_artist_name}'")

        # Build success message
        message = f'Song "{song_title}" reassigned to "{new_artist_name}"'
        if blocklist_updated > 0:
            message += f'. {blocklist_updated} blocklist entr{"y" if blocklist_updated == 1 else "ies"} updated.'

        return jsonify({
            'success': True,
            'message': message,
            'song_title': song_title,
            'old_artist_name': current_artist_name,
            'new_artist_name': new_artist_name,
            'blocklist_updated': blocklist_updated
        })

    except Exception as e:
        logger.error(f"Error changing artist for song {song_id}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


@songs_bp.route('/api/songs/<int:song_id>/verify', methods=['POST'])
@requires_auth
def verify_song_api(song_id):
    """Verify a single song using MusicBrainz + Lidarr"""
    import json
    from radio_monitor.song_validation import verify_artist_song
    from radio_monitor.database.crud import (
        add_song_verification,
        get_song_verification,
        update_song_verification_status
    )

    db = get_db()
    settings = current_app.config.get('settings')

    # Get song details
    cursor = db.get_cursor()
    cursor.execute("""
        SELECT s.id, s.song_title, s.artist_mbid, a.name as artist_name
        FROM songs s
        JOIN artists a ON s.artist_mbid = a.mbid
        WHERE s.id = ?
    """, (song_id,))
    song = cursor.fetchone()

    if not song:
        cursor.close()
        return jsonify({'error': 'Song not found'}), 404

    try:
        # Run verification
        # song is a tuple: (id, song_title, artist_mbid, artist_name)
        result = verify_artist_song(
            artist_name=song[3],  # artist_name
            song_title=song[1],    # song_title
            artist_mbid=song[2],   # artist_mbid
            settings=settings,
            sources=['musicbrainz', 'lidarr']
        )

        # Store MusicBrainz verification
        if 'musicbrainz' in result['sources']:
            mb_result = result['sources']['musicbrainz']
            add_song_verification(
                cursor,
                song_id,
                'musicbrainz',
                mb_result['is_verified'],
                json.dumps(mb_result)
            )

        # Store Lidarr verification
        if 'lidarr' in result['sources']:
            lidarr_result = result['sources']['lidarr']
            add_song_verification(
                cursor,
                song_id,
                'lidarr',
                lidarr_result['is_verified'],
                json.dumps(lidarr_result)
            )

        # Update overall status
        update_song_verification_status(cursor, song_id, result['overall_status'])

        db.conn.commit()
        cursor.close()

        return jsonify(result)

    except Exception as e:
        logger.error(f"Song verification error: {e}")
        cursor.close()
        return jsonify({'error': str(e)}), 500


@songs_bp.route('/api/artists/<artist_mbid>/verify-all', methods=['POST'])
@requires_auth
def verify_artist_all_songs(artist_mbid):
    """Verify all songs for an artist"""
    import json
    from radio_monitor.song_validation import verify_artist_song
    from radio_monitor.database.crud import (
        add_song_verification,
        update_song_verification_status
    )

    db = get_db()
    settings = current_app.config.get('settings')

    # Get artist's songs
    cursor = db.get_cursor()
    cursor.execute("""
        SELECT s.id, s.song_title, s.artist_mbid, a.name as artist_name
        FROM songs s
        JOIN artists a ON s.artist_mbid = a.mbid
        WHERE a.mbid = ?
        ORDER BY s.play_count DESC
    """, (artist_mbid,))
    songs = cursor.fetchall()

    if not songs:
        cursor.close()
        return jsonify({'error': 'No songs found for artist'}), 404

    results = []
    verified_count = 0
    not_found_count = 0

    for song in songs:
        try:
            # Run verification
            # song is a tuple: (id, song_title, artist_mbid, artist_name)
            result = verify_artist_song(
                artist_name=song[3],  # artist_name
                song_title=song[1],    # song_title
                artist_mbid=song[2],   # artist_mbid
                settings=settings,
                sources=['musicbrainz', 'lidarr']
            )

            # Store verification results
            if 'musicbrainz' in result['sources']:
                mb_result = result['sources']['musicbrainz']
                add_song_verification(
                    cursor,
                    song[0],  # song id
                    'musicbrainz',
                    mb_result['is_verified'],
                    json.dumps(mb_result)
                )

            if 'lidarr' in result['sources']:
                lidarr_result = result['sources']['lidarr']
                add_song_verification(
                    cursor,
                    song[0],  # song id
                    'lidarr',
                    lidarr_result['is_verified'],
                    json.dumps(lidarr_result)
                )

            # Update overall status
            update_song_verification_status(cursor, song[0], result['overall_status'])

            if result['overall_status'] in ['VERIFIED_MB', 'VERIFIED_LIDARR']:
                verified_count += 1
            elif result['overall_status'] == 'NOT_FOUND':
                not_found_count += 1

            results.append({
                'song_id': song[0],
                'title': song[1],
                'status': result['overall_status']
            })

        except Exception as e:
            logger.error(f"Verification failed for song {song[0]}: {e}")

    db.conn.commit()
    cursor.close()

    return jsonify({
        'total': len(songs),
        'verified': verified_count,
        'not_found': not_found_count,
        'results': results
    })
