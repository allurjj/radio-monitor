"""
Artists routes for Radio Monitor GUI

Provides list and detail views for artists with pagination, filtering, and sorting.
"""

import logging
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, current_app
from radio_monitor.auth import requires_auth

logger = logging.getLogger(__name__)

artists_bp = Blueprint('artists', __name__)


def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')


@artists_bp.route('/artists')
@requires_auth
def artists_list():
    """Artists list page with pagination and filtering"""
    db = get_db()
    from radio_monitor.database.queries import get_all_stations

    if not db:
        return render_template('error.html', error='Database not initialized'), 500

    # Get query parameters
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 50))
    search = request.args.get('search', '')
    needs_import = request.args.get('needs_import', '')
    station_id = request.args.get('station_id', '')
    sort = request.args.get('sort', 'name')
    direction = request.args.get('direction', 'asc')

    # Validate direction
    if direction not in ['asc', 'desc']:
        direction = 'asc'

    # Validate sort column (whitelist)
    valid_columns = ['name', 'song_count', 'total_plays', 'last_seen', 'first_seen']
    if sort not in valid_columns:
        sort = 'name'

    # Advanced filters
    first_seen_after = request.args.get('first_seen_after', '')
    last_seen_after = request.args.get('last_seen_after', '')
    total_plays_min = request.args.get('total_plays_min', '')
    total_plays_max = request.args.get('total_plays_max', '')

    # Build filters dict
    filters = {}
    if search:
        filters['search'] = search
    if needs_import:
        filters['needs_import'] = needs_import
    if station_id:
        filters['station_id'] = station_id
    if first_seen_after:
        filters['first_seen_after'] = first_seen_after
    if last_seen_after:
        filters['last_seen_after'] = last_seen_after
    if total_plays_min:
        filters['total_plays_min'] = total_plays_min
    if total_plays_max:
        filters['total_plays_max'] = total_plays_max

    # Get artists
    cursor = db.get_cursor()
    try:
        from radio_monitor.database.queries import get_artists_paginated
        result = get_artists_paginated(cursor, page, limit, filters, sort, direction)
        stations = get_all_stations(cursor)
    finally:
        cursor.close()

    return render_template('artists.html',
                          artists=result['items'],
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


@artists_bp.route('/artists/<mbid>')
@requires_auth
def artist_detail(mbid):
    """Artist detail page with tabs for overview, songs, history"""
    db = get_db()
    from radio_monitor.database.queries import get_artist_detail, get_artist_songs, get_artist_play_history

    if not db:
        return render_template('error.html', error='Database not initialized'), 500

    cursor = db.get_cursor()
    try:
        # Get artist details
        artist = get_artist_detail(cursor, mbid)
        if not artist:
            return render_template('error.html', error=f"Artist not found: {mbid}"), 404

        # Get artist's songs
        songs = get_artist_songs(cursor, mbid, limit=100)

        # Get play history
        history = get_artist_play_history(cursor, mbid, days=90)
    finally:
        cursor.close()

    return render_template('artist_detail.html',
                          artist=artist,
                          songs=songs,
                          history=history)


# ==================== API ENDPOINTS ====================

@artists_bp.route('/api/artists')
@requires_auth
def api_artists():
    """API endpoint for artists with filtering and pagination"""
    db = get_db()
    from radio_monitor.database.queries import get_artists_paginated

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    # Get query parameters
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 50))
    search = request.args.get('search', '')
    needs_import = request.args.get('needs_import', '')
    station_id = request.args.get('station_id', '')
    sort = request.args.get('sort', 'name')
    direction = request.args.get('direction', 'asc')

    # Validate direction
    if direction not in ['asc', 'desc']:
        direction = 'asc'

    # Validate sort column (whitelist)
    valid_columns = ['name', 'song_count', 'total_plays', 'last_seen', 'first_seen']
    if sort not in valid_columns:
        sort = 'name'

    # Advanced filters
    first_seen_after = request.args.get('first_seen_after', '')
    last_seen_after = request.args.get('last_seen_after', '')
    total_plays_min = request.args.get('total_plays_min', '')
    total_plays_max = request.args.get('total_plays_max', '')

    # Build filters dict
    filters = {}
    if search:
        filters['search'] = search
    if needs_import:
        filters['needs_import'] = needs_import
    if station_id:
        filters['station_id'] = station_id
    if first_seen_after:
        filters['first_seen_after'] = first_seen_after
    if last_seen_after:
        filters['last_seen_after'] = last_seen_after
    if total_plays_min:
        filters['total_plays_min'] = total_plays_min
    if total_plays_max:
        filters['total_plays_max'] = total_plays_max

    # Get artists
    cursor = db.get_cursor()
    try:
        result = get_artists_paginated(cursor, page, limit, filters, sort, direction)
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


@artists_bp.route('/api/artists/<mbid>')
@requires_auth
def api_artist_detail(mbid):
    """API endpoint for single artist details"""
    db = get_db()
    from radio_monitor.database.queries import get_artist_detail

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()
    try:
        artist = get_artist_detail(cursor, mbid)
    finally:
        cursor.close()

    if not artist:
        return jsonify({'error': 'Artist not found'}), 404

    return jsonify(artist)


@artists_bp.route('/api/artists/<mbid>/songs')
@requires_auth
def api_artist_songs(mbid):
    """API endpoint for artist's songs"""
    db = get_db()
    from radio_monitor.database.queries import get_artist_songs

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    limit = int(request.args.get('limit', 100))

    cursor = db.get_cursor()
    try:
        songs = get_artist_songs(cursor, mbid, limit)
    finally:
        cursor.close()

    return jsonify({
        'items': songs,
        'count': len(songs)
    })


@artists_bp.route('/api/artists/<mbid>/history')
@requires_auth
def api_artist_history(mbid):
    """API endpoint for artist's play history"""
    db = get_db()
    from radio_monitor.database.queries import get_artist_play_history

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    days = int(request.args.get('days', 30))

    cursor = db.get_cursor()
    try:
        history = get_artist_play_history(cursor, mbid, days)
    finally:
        cursor.close()

    return jsonify({
        'items': history,
        'count': len(history),
        'days': days
    })


@artists_bp.route('/api/artists/update-mbid', methods=['POST'])
@requires_auth
def api_update_artist_mbid():
    """API endpoint to update an artist's MBID and name"""
    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    data = request.get_json()
    artist_name = data.get('artist_name', '').strip()
    new_mbid = data.get('mbid', '').strip()

    if not artist_name or not new_mbid:
        return jsonify({'error': 'artist_name and mbid are required'}), 400

    # Get the correct artist name from MusicBrainz
    from radio_monitor.mbid import get_artist_from_mbid

    try:
        artist_info = get_artist_from_mbid(new_mbid)
        if artist_info and isinstance(artist_info, dict) and artist_info.get('name'):
            correct_artist_name = artist_info['name']
            logger.info(f"Fetched artist name from MusicBrainz: '{correct_artist_name}'")
        else:
            logger.warning(f"Could not fetch artist name from MusicBrainz for MBID {new_mbid}")
            # Continue anyway - user might have correct MBID from offline source
            correct_artist_name = artist_name
    except Exception as e:
        logger.warning(f"Error fetching artist name from MusicBrainz: {e}")
        correct_artist_name = artist_name

    cursor = db.get_cursor()
    try:
        # Normalize artist name for database lookup
        from radio_monitor.normalization import normalize_artist_name
        normalized_name = normalize_artist_name(artist_name)

        # Try multiple search strategies to find the artist
        # 1. Exact match
        cursor.execute("SELECT mbid, first_seen_station, first_seen_at FROM artists WHERE name = ?", (artist_name,))
        result = cursor.fetchone()

        # 2. Normalized name
        if not result and normalized_name != artist_name:
            cursor.execute("SELECT mbid, first_seen_station, first_seen_at FROM artists WHERE name = ?", (normalized_name,))
            result = cursor.fetchone()
            if result:
                artist_name = normalized_name

        # 3. Case-insensitive LIKE search
        if not result:
            cursor.execute("SELECT mbid, first_seen_station, first_seen_at FROM artists WHERE name LIKE ?", (f'%{artist_name}%',))
            result = cursor.fetchone()

        # 4. MusicBrainz name (handles Unicode differences like "A-ha" vs "a‐ha")
        if not result and correct_artist_name != artist_name:
            cursor.execute("SELECT mbid, first_seen_station, first_seen_at FROM artists WHERE name = ?", (correct_artist_name,))
            result = cursor.fetchone()
            if result:
                artist_name = correct_artist_name

        if not result:
            # Try to find similar artists for helpful error message
            search_term = artist_name.replace('-', '').replace(' ', '')
            cursor.execute("SELECT name FROM artists WHERE REPLACE(REPLACE(name, '-', ''), ' ', '') LIKE ? LIMIT 10", (f'%{search_term}%',))
            similar = cursor.fetchall()
            logger.error(f"Artist not found: '{artist_name}'. Similar artists: {[r[0] for r in similar]}")
            return jsonify({'error': f'Artist not found: {artist_name}. Check that the artist name matches exactly.'}), 404

        old_mbid = result[0]
        first_seen_station = result[1]
        first_seen_at = result[2]

        # Check if new MBID already exists in artists table
        cursor.execute("SELECT mbid, name FROM artists WHERE mbid = ?", (new_mbid,))
        existing_new_artist = cursor.fetchone()

        if existing_new_artist:
            # Scenario 1: New MBID already exists - merge into existing artist
            # Update all songs to point to the existing artist
            cursor.execute("""
                UPDATE songs
                SET artist_mbid = ?, artist_name = ?
                WHERE artist_mbid = ?
            """, (new_mbid, existing_new_artist[1], old_mbid))

            songs_updated = cursor.rowcount

            # Delete the old artist record (PENDING artist being replaced)
            cursor.execute("DELETE FROM artists WHERE mbid = ?", (old_mbid,))

            db.conn.commit()

            logger.info(f"Merged {songs_updated} songs from '{artist_name}' (MBID: {old_mbid}) into existing artist '{existing_new_artist[1]}' (MBID: {new_mbid})")

            return jsonify({
                'success': True,
                'message': f'MBID override saved! Merged {songs_updated} song(s) into existing artist "{existing_new_artist[1]}".',
                'old_name': artist_name,
                'new_name': existing_new_artist[1],
                'mbid': new_mbid,
                'songs_updated': songs_updated
            })
        else:
            # Scenario 2: New MBID doesn't exist - need to create it first

            # Step 1: Insert new artist with the correct MBID
            try:
                cursor.execute("""
                    INSERT INTO artists (mbid, name, first_seen_station, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (new_mbid, correct_artist_name, first_seen_station, first_seen_at))
            except Exception as insert_err:
                # Try without first_seen_station if foreign key constraint fails
                logger.warning(f"Could not insert artist with station reference, trying without: {insert_err}")
                cursor.execute("""
                    INSERT INTO artists (mbid, name, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (new_mbid, correct_artist_name, first_seen_at))

            # Step 2: Update all songs to point to the new MBID
            cursor.execute("""
                UPDATE songs
                SET artist_mbid = ?, artist_name = ?
                WHERE artist_mbid = ?
            """, (new_mbid, correct_artist_name, old_mbid))
            songs_updated = cursor.rowcount

            # Step 3: Delete the old artist record
            cursor.execute("DELETE FROM artists WHERE mbid = ?", (old_mbid,))

            db.conn.commit()

            logger.info(f"Updated artist '{artist_name}' (MBID: {old_mbid}) to '{correct_artist_name}' (MBID: {new_mbid}) with {songs_updated} songs")

            return jsonify({
                'success': True,
                'message': f'Artist updated successfully! {songs_updated} song(s) updated.',
                'old_name': artist_name,
                'new_name': correct_artist_name,
                'mbid': new_mbid,
                'songs_updated': songs_updated
            })
    except Exception as e:
        db.conn.rollback()
        logger.error(f"Error updating artist MBID: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


@artists_bp.route('/api/artists/<mbid>', methods=['DELETE'])
@requires_auth
def api_delete_artist(mbid):
    """API endpoint to delete an artist and all related data

    Deletes:
    - Artist record
    - All songs by this artist
    - All play history for those songs
    - All Plex match failures for those songs
    - Manual MBID overrides for this artist

    Args:
        mbid: Artist MusicBrainz ID (from URL path)

    Returns:
        JSON response with deletion statistics
    """
    from radio_monitor.database.crud import delete_artist
    from radio_monitor.database.activity import log_activity
    import json

    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()
    try:
        # Use connection as context manager for transaction
        with db.conn:
            # Call CRUD function
            result = delete_artist(cursor, db.conn, mbid)

            if not result['success']:
                # Return appropriate error status
                if 'not found' in result.get('error', '').lower():
                    return jsonify({'error': result['error']}), 404
                else:
                    return jsonify({'error': result['error']}), 500

            # Add activity log entry (within same transaction)
            log_activity(
                cursor=cursor,
                event_type='artist_deleted',
                title=f"Deleted artist: {result['artist_name']}",
                description=f"Deleted {result['songs_deleted']} songs, {result['plays_deleted']} plays, "
                            f"{result['plex_failures_deleted']} Plex failures, "
                            f"{result['overrides_deleted']} MBID overrides",
                metadata={
                    'mbid': result['mbid'],
                    'artist_name': result['artist_name'],
                    'songs_deleted': result['songs_deleted'],
                    'plays_deleted': result['plays_deleted'],
                    'plex_failures_deleted': result['plex_failures_deleted'],
                    'overrides_deleted': result['overrides_deleted']
                },
                severity='info',
                source='user'
            )

        # Build success message
        message = (
            f"Deleted '{result['artist_name']}' and {result['songs_deleted']} "
            f"song{'s' if result['songs_deleted'] != 1 else ''} "
            f"({result['plays_deleted']} play{'s' if result['plays_deleted'] != 1 else ''})"
        )

        return jsonify({
            'success': True,
            'message': message,
            'artist_name': result['artist_name'],
            'mbid': result['mbid'],
            'songs_deleted': result['songs_deleted'],
            'plays_deleted': result['plays_deleted'],
            'plex_failures_deleted': result['plex_failures_deleted'],
            'overrides_deleted': result['overrides_deleted']
        })

    except Exception as e:
        logger.error(f"Unexpected error deleting artist {mbid}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


@artists_bp.route('/api/artists/retry-pending', methods=['POST'])
@requires_auth
def api_retry_pending_artists():
    """Retry MBID lookup for all PENDING artists

    Triggers a background job to retry MusicBrainz lookup for all artists
    with PENDING MBIDs. This is useful after fixing MusicBrainz data or
    network issues.

    Returns JSON:
        {
            "success": true,
            "message": "MBID retry started for 15 PENDING artists",
            "pending_count": 15,
            "estimated_time_seconds": 120
        }
    """
    from radio_monitor.mbid import retry_pending_artists

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        # Get count of PENDING artists
        cursor = db.get_cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM artists WHERE mbid LIKE 'PENDING-%'")
            pending_count = cursor.fetchone()[0]
        finally:
            cursor.close()

        if pending_count == 0:
            return jsonify({
                'success': True,
                'message': 'No PENDING artists to retry',
                'pending_count': 0
            })

        # Estimate time (8 seconds per artist due to MusicBrainz rate limiting)
        estimated_time = pending_count * 8

        # Trigger retry in background
        from radio_monitor.gui import scheduler
        if scheduler and scheduler.scheduler:
            scheduler.scheduler.add_job(
                func=lambda: retry_pending_artists(db, max_artists=None),
                id=f'manual_retry_pending_{datetime.now().timestamp()}',
                name='Manual MBID Retry (PENDING Artists)'
            )
            logger.info(f"Triggered manual MBID retry for {pending_count} PENDING artists")

            return jsonify({
                'success': True,
                'message': f'MBID retry started for {pending_count} PENDING artist(s)',
                'pending_count': pending_count,
                'estimated_time_seconds': estimated_time
            })
        else:
            # No scheduler available, run synchronously
            logger.warning("No scheduler available, running MBID retry synchronously")
            results = retry_pending_artists(db, max_artists=None)

            return jsonify({
                'success': True,
                'message': f'MBID retry complete: {results.get("resolved", 0)} resolved, {results.get("failed", 0)} still failed',
                'pending_count': pending_count,
                'resolved': results.get('resolved', 0),
                'failed': results.get('failed', 0)
            })

    except Exception as e:
        logger.error(f"Error triggering MBID retry: {e}")
        return jsonify({'error': str(e)}), 500


@artists_bp.route('/api/artists/pending-count')
@requires_auth
def api_pending_count():
    """Get count of PENDING artists

    Returns JSON:
        {
            "pending_count": 15
        }
    """
    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        cursor = db.get_cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM artists WHERE mbid LIKE 'PENDING-%'")
            pending_count = cursor.fetchone()[0]
        finally:
            cursor.close()

        return jsonify({'pending_count': pending_count})

    except Exception as e:
        logger.error(f"Error getting PENDING count: {e}")
        return jsonify({'error': str(e)}), 500
