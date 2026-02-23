"""
Playlist Builder Routes for Radio Monitor 1.2.0

Manual playlist creation with full editing capabilities.
"""

import logging
import uuid
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, current_app, session
from radio_monitor.auth import requires_auth

logger = logging.getLogger(__name__)

playlist_builder_bp = Blueprint('playlist_builder', __name__)


def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')


def get_session_id():
    """Get or create session ID for playlist builder state"""
    if 'playlist_builder_session' not in session:
        session['playlist_builder_session'] = str(uuid.uuid4())
    return session['playlist_builder_session']


# ==================== PAGE ROUTES ====================

@playlist_builder_bp.route('/playlist-builder')
@requires_auth
def playlist_builder_page():
    """Render the playlist builder page"""
    from radio_monitor.gui import is_first_run
    from flask import redirect, url_for
    from radio_monitor.database.queries import get_all_stations

    if is_first_run():
        return redirect(url_for('wizard'))

    db = get_db()
    if not db:
        return "Database not initialized", 500

    try:
        cursor = db.get_cursor()
        try:
            stations = get_all_stations(cursor)
            return render_template('playlist_builder.html', stations=stations)
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Error loading playlist builder page: {e}")
        return f"Error loading page: {str(e)}", 500


# ==================== SELECTION MANAGEMENT ====================

@playlist_builder_bp.route('/api/playlist-builder/selections', methods=['GET'])
@requires_auth
def api_get_selections():
    """Get current session's selected songs

    Returns JSON:
        {
            "song_ids": [1, 5, 23, 45],
            "count": 4
        }
    """
    from radio_monitor.database.queries import get_builder_state_song_ids

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        session_id = get_session_id()
        cursor = db.get_cursor()

        try:
            song_ids = get_builder_state_song_ids(cursor, session_id)
            return jsonify({
                'song_ids': song_ids,
                'count': len(song_ids)
            })
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Error getting selections: {e}")
        return jsonify({'error': str(e)}), 500


@playlist_builder_bp.route('/api/playlist-builder/selections', methods=['POST'])
@requires_auth
def api_update_selection():
    """Add or remove song selection

    Expects JSON:
        {
            "song_id": 123,
            "selected": true
        }

    Returns JSON:
        {
            "success": true,
            "count": 5
        }
    """
    from radio_monitor.database.crud import add_song_to_builder_state, remove_song_from_builder_state
    from radio_monitor.database.queries import get_builder_state_song_count

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        song_id = data.get('song_id')
        selected = data.get('selected', True)

        if not song_id:
            return jsonify({'error': 'song_id is required'}), 400

        session_id = get_session_id()
        cursor = db.get_cursor()

        try:
            if selected:
                add_song_to_builder_state(cursor, db.conn, session_id, song_id)
            else:
                remove_song_from_builder_state(cursor, db.conn, session_id, song_id)

            # Get updated count
            count = get_builder_state_song_count(cursor, session_id)
            return jsonify({'success': True, 'count': count})
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Error updating selection: {e}")
        return jsonify({'error': str(e)}), 500


@playlist_builder_bp.route('/api/playlist-builder/selections/batch', methods=['POST'])
@requires_auth
def api_batch_update_selections():
    """Batch add/remove songs (for artist checkbox or select all)

    Expects JSON:
        {
            "song_ids": [1, 2, 3],
            "selected": true
        }

    Returns JSON:
        {
            "success": true,
            "count": 156
        }
    """
    from radio_monitor.database.crud import add_songs_to_builder_state_batch, remove_songs_from_builder_state_batch
    from radio_monitor.database.queries import get_builder_state_song_count

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        song_ids = data.get('song_ids', [])
        selected = data.get('selected', True)

        if not isinstance(song_ids, list):
            return jsonify({'error': 'song_ids must be a list'}), 400

        if not song_ids:
            return jsonify({'success': True, 'count': 0})

        session_id = get_session_id()
        cursor = db.get_cursor()

        try:
            # Use batch operations for better performance
            if selected:
                add_songs_to_builder_state_batch(cursor, session_id, song_ids)
            else:
                remove_songs_from_builder_state_batch(cursor, session_id, song_ids)

            # Single commit after all operations
            db.conn.commit()

            # Get updated count
            count = get_builder_state_song_count(cursor, session_id)
            return jsonify({'success': True, 'count': count})
        except Exception as e:
            # Rollback on error
            db.conn.rollback()
            raise e
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Error batch updating selections: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@playlist_builder_bp.route('/api/playlist-builder/selections', methods=['DELETE'])
@requires_auth
def api_clear_selections():
    """Clear all selections

    Returns JSON:
        {
            "success": true,
            "count": 0
        }
    """
    from radio_monitor.database.crud import clear_builder_state

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        session_id = get_session_id()
        cursor = db.get_cursor()

        try:
            clear_builder_state(cursor, db.conn, session_id)
            return jsonify({'success': True, 'count': 0})
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Error clearing selections: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== SONG/ARTIST LISTING ====================

@playlist_builder_bp.route('/api/playlist-builder/songs', methods=['GET'])
@requires_auth
def api_get_songs():
    """Get songs for listing (with filters, pagination)

    Query params:
        - page: Page number (default: 1)
        - per_page: Items per page (default: 50)
        - sort: Sort column (default: title)
        - direction: asc or desc (default: asc)
        - stations: Comma-separated station IDs
        - date_field: first_seen_at or last_seen_at
        - date_start: Start date (ISO format)
        - date_end: End date (ISO format)
        - min_plays: Minimum play count
        - max_plays: Maximum play count
        - search: Search term (title or artist)
        - show: all, selected, or unselected

    Returns JSON:
        {
            "songs": [...],
            "total": 1234,
            "page": 1,
            "per_page": 50
        }
    """
    from radio_monitor.database.queries import get_songs_paginated

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        # Parse query parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 50)), 500)  # Max 500
        sort = request.args.get('sort', 'title')
        direction = request.args.get('direction', 'asc')

        if direction not in ['asc', 'desc']:
            direction = 'asc'

        # Build filters
        filters = {}

        # Station filter - convert to station_id for query
        stations = request.args.get('stations')
        if stations:
            station_list = [s.strip() for s in stations.split(',')]
            if len(station_list) == 1:
                filters['station_id'] = station_list[0]
            else:
                # Multiple stations - use IN clause
                filters['station_ids'] = station_list

        # Date range filter - convert to query format
        date_field = request.args.get('date_field', 'last_seen_at')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        if date_start and date_end:
            if date_field == 'last_seen_at':
                filters['last_seen_after'] = date_start
                filters['last_seen_before'] = date_end
            else:  # first_seen_at
                filters['first_seen_after'] = date_start
                filters['first_seen_before'] = date_end

        # Play count filter - convert to query format
        min_plays = request.args.get('min_plays')
        if min_plays:
            filters['plays_min'] = int(min_plays)

        max_plays = request.args.get('max_plays')
        if max_plays:
            filters['plays_max'] = int(max_plays)

        # Search filter
        search = request.args.get('search')
        if search:
            filters['search'] = search.strip()

        # Selection filter (requires session)
        show = request.args.get('show', 'all')
        session_id = get_session_id()
        cursor = db.get_cursor()

        try:
            # Get selected song IDs first
            from radio_monitor.database.queries import get_builder_state_song_ids
            selected_ids = get_builder_state_song_ids(cursor, session_id)
            selected_set = set(selected_ids)

            # If filtering by selection, add to filters
            if show == 'selected' and selected_ids:
                # Add a filter for selected songs
                filters['selected_song_ids'] = selected_ids
            elif show == 'unselected' and selected_ids:
                # Add filter for unselected songs (this is trickier - need NOT IN)
                filters['unselected_song_ids'] = selected_ids

            # Get songs
            result = get_songs_paginated(
                cursor,
                page=page,
                limit=per_page,
                filters=filters,
                sort=sort,
                direction=direction
            )

            # Mark songs as selected/unselected
            for song in result['items']:
                song['selected'] = song['id'] in selected_set

            return jsonify({
                'songs': result['items'],
                'total': result['total'],
                'page': page,
                'per_page': per_page
            })
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Error getting songs: {e}")
        return jsonify({'error': str(e)}), 500


@playlist_builder_bp.route('/api/playlist-builder/artists', methods=['GET'])
@requires_auth
def api_get_artists():
    """Get artists for "By Artist" view (with song counts, selection counts)

    Query params: same as /api/playlist-builder/songs

    Returns JSON:
        {
            "artists": [...],
            "total": 456,
            "page": 1,
            "per_page": 50
        }
    """
    from radio_monitor.database.queries import get_artists_paginated

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        # Parse query parameters (same as songs)
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 50)), 500)
        sort = request.args.get('sort', 'name')
        direction = request.args.get('direction', 'asc')

        if direction not in ['asc', 'desc']:
            direction = 'asc'

        # Build filters
        filters = {}

        # Station filter - for artists, post-filter by stations where songs were played
        stations = request.args.get('stations')
        station_list = []
        if stations:
            station_list = [s.strip() for s in stations.split(',')]

        # Date range filter - convert to query format
        date_field = request.args.get('date_field', 'last_seen_at')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        if date_start and date_end:
            if date_field == 'last_seen_at':
                filters['last_seen_after'] = date_start
                filters['last_seen_before'] = date_end
            else:  # first_seen_at
                filters['first_seen_after'] = date_start
                # Note: first_seen_before not supported in artists query

        # Play count filter - convert to query format (artists use total_plays)
        min_plays = request.args.get('min_plays')
        if min_plays:
            filters['total_plays_min'] = int(min_plays)

        max_plays = request.args.get('max_plays')
        if max_plays:
            filters['total_plays_max'] = int(max_plays)

        # Search filter
        search = request.args.get('search')
        if search:
            filters['search'] = search.strip()

        session_id = get_session_id()
        cursor = db.get_cursor()

        try:
            # Get selected song IDs first
            from radio_monitor.database.queries import get_builder_state_song_ids, get_artist_song_ids
            selected_ids = get_builder_state_song_ids(cursor, session_id)
            selected_set = set(selected_ids)

            # Get show parameter
            show = request.args.get('show', 'all')

            # For playlist builder, we need custom logic because:
            # 1. Station filter should find artists with songs played on those stations (not first_seen_station)
            # 2. Show only selected needs to filter BEFORE pagination

            # Build custom query for playlist builder
            offset = (page - 1) * per_page

            # Build WHERE conditions
            conditions = []
            params = []

            # Search filter
            if filters.get('search'):
                conditions.append("a.name LIKE ?")
                params.append(f"%{filters['search']}%")

            # Date filters
            if filters.get('last_seen_after'):
                conditions.append("a.last_seen_at >= ?")
                params.append(filters['last_seen_after'])
            if filters.get('first_seen_after'):
                conditions.append("a.first_seen_at >= ?")
                params.append(filters['first_seen_after'])

            # Play count filters (HAVING clause)
            having_conditions = []
            if filters.get('total_plays_min'):
                having_conditions.append("COALESCE(SUM(s.play_count), 0) >= ?")
                params.append(int(filters['total_plays_min']))
            if filters.get('total_plays_max'):
                having_conditions.append("COALESCE(SUM(s.play_count), 0) <= ?")
                params.append(int(filters['total_plays_max']))

            # Station filter - use subquery to find artists with songs played on these stations
            if station_list:
                placeholders = ','.join(['?' for _ in station_list])
                conditions.append(f"EXISTS (SELECT 1 FROM song_plays_daily spd JOIN songs s2 ON spd.song_id = s2.id WHERE s2.artist_mbid = a.mbid AND spd.station_id IN ({placeholders}))")
                params.extend(station_list)

            # Show only selected filter - use subquery to find artists with selected songs
            if show == 'selected':
                if selected_ids:
                    placeholders_selected = ','.join(['?' for _ in selected_ids])
                    conditions.append(f"a.mbid IN (SELECT DISTINCT artist_mbid FROM songs WHERE id IN ({placeholders_selected}))")
                    params.extend(selected_ids)
                else:
                    # No songs selected, return empty result
                    return jsonify({
                        'artists': [],
                        'total': 0,
                        'page': page,
                        'per_page': per_page
                    })

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            having_clause = "HAVING " + " AND ".join(having_conditions) if having_conditions else ""

            # Build ORDER BY
            sort_column_mapping = {
                'name': 'a.name',
                'song_count': 'song_count',
                'total_plays': 'total_plays',
                'last_seen': 'a.last_seen_at'
            }
            sort_column = sort_column_mapping.get(sort, 'a.name')
            if sort == 'name':
                order_by = f"{sort_column} COLLATE NOCASE {direction.upper()}"
            else:
                order_by = f"{sort_column} {direction.upper()}"

            # Get total count
            count_query = f"""
                SELECT COUNT(DISTINCT a.mbid)
                FROM artists a
                LEFT JOIN songs s ON a.mbid = s.artist_mbid
                {where_clause}
            """
            if having_conditions:
                count_query += " GROUP BY a.mbid " + having_clause
                count_query = f"SELECT COUNT(*) FROM ({count_query})"

            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Get paginated results
            query = f"""
                SELECT
                    a.mbid,
                    a.name,
                    a.first_seen_station,
                    a.first_seen_at,
                    a.last_seen_at,
                    COALESCE(SUM(s.play_count), 0) as total_plays,
                    COUNT(s.id) as song_count
                FROM artists a
                LEFT JOIN songs s ON a.mbid = s.artist_mbid
                {where_clause}
                GROUP BY a.mbid
                {having_clause}
                ORDER BY {order_by}
                LIMIT ? OFFSET ?
            """
            params.extend([per_page, offset])
            cursor.execute(query, params)

            columns = ['mbid', 'name', 'first_seen_station',
                      'first_seen_at', 'last_seen_at',
                      'total_plays', 'song_count']
            items = [dict(zip(columns, row)) for row in cursor.fetchall()]

            # Count selected songs per artist
            for artist in items:
                artist_song_ids = get_artist_song_ids(cursor, artist['mbid'])
                selected_count = len([sid for sid in artist_song_ids if sid in selected_set])
                artist['selected_count'] = selected_count
                artist['total_count'] = artist.get('song_count', 0)

            result = {
                'items': items,
                'total': total,
                'page': page,
                'per_page': per_page
            }

            return jsonify({
                'artists': result['items'],
                'total': result['total'],
                'page': page,
                'per_page': per_page
            })
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Error getting artists: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== MANUAL PLAYLIST CRUD ====================

@playlist_builder_bp.route('/api/playlists/manual', methods=['GET'])
@requires_auth
def api_get_manual_playlists():
    """Get all manual playlists (for dropdown)

    Returns JSON:
        {
            "playlists": [
                {"id": 1, "name": "Road Trip", "song_count": 23},
                ...
            ]
        }
    """
    from radio_monitor.database.queries import get_manual_playlists

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        cursor = db.get_cursor()

        try:
            playlists = get_manual_playlists(cursor)

            # Add song counts
            from radio_monitor.database.queries import get_song_count_in_manual_playlist
            for playlist in playlists:
                playlist['song_count'] = get_song_count_in_manual_playlist(cursor, playlist['id'])

            return jsonify({'playlists': playlists})
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Error getting manual playlists: {e}")
        return jsonify({'error': str(e)}), 500


@playlist_builder_bp.route('/api/playlists/manual', methods=['POST'])
@requires_auth
def api_create_manual_playlist():
    """Create new manual playlist

    Expects JSON:
        {
            "name": "Road Trip",
            "plex_playlist_name": "Road Trip 2026"  // optional
        }

    Returns JSON:
        {
            "success": true,
            "playlist_id": 5,
            "song_count": 23
        }
    """
    from radio_monitor.database.crud import create_manual_playlist, add_song_to_manual_playlist
    from radio_monitor.database.queries import get_builder_state_songs, get_song_count_in_manual_playlist

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        name = data.get('name')
        plex_playlist_name = data.get('plex_playlist_name')

        if not name:
            return jsonify({'error': 'name is required'}), 400

        cursor = db.get_cursor()

        try:
            # Create playlist
            playlist_id = create_manual_playlist(cursor, db.conn, name, plex_playlist_name)

            # Add current selections to playlist
            session_id = get_session_id()
            songs = get_builder_state_songs(cursor, session_id)

            for song in songs:
                add_song_to_manual_playlist(cursor, db.conn, playlist_id, song['id'])

            # Get song count
            song_count = get_song_count_in_manual_playlist(cursor, playlist_id)

            return jsonify({
                'success': True,
                'playlist_id': playlist_id,
                'song_count': song_count
            })
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Error creating manual playlist: {e}")
        return jsonify({'error': str(e)}), 500


@playlist_builder_bp.route('/api/playlists/manual/<int:playlist_id>', methods=['PUT'])
@requires_auth
def api_update_manual_playlist(playlist_id):
    """Update existing manual playlist

    Expects JSON:
        {
            "name": "Road Trip Updated",
            "plex_playlist_name": "Road Trip 2026"  // optional
        }

    Returns JSON:
        {
            "success": true,
            "song_count": 25
        }
    """
    from radio_monitor.database.crud import update_manual_playlist, clear_manual_playlist, add_song_to_manual_playlist
    from radio_monitor.database.queries import get_builder_state_songs, get_song_count_in_manual_playlist, get_manual_playlist

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        name = data.get('name')
        plex_playlist_name = data.get('plex_playlist_name')

        # Verify playlist exists
        cursor = db.get_cursor()

        try:
            playlist = get_manual_playlist(cursor, playlist_id)
            if not playlist:
                return jsonify({'error': 'Playlist not found'}), 404

            # Update playlist metadata
            update_manual_playlist(cursor, db.conn, playlist_id, name, plex_playlist_name)

            # Replace songs with current selections
            clear_manual_playlist(cursor, db.conn, playlist_id)

            session_id = get_session_id()
            songs = get_builder_state_songs(cursor, session_id)

            for song in songs:
                add_song_to_manual_playlist(cursor, db.conn, playlist_id, song['id'])

            # Get song count
            song_count = get_song_count_in_manual_playlist(cursor, playlist_id)

            return jsonify({
                'success': True,
                'song_count': song_count
            })
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Error updating manual playlist: {e}")
        return jsonify({'error': str(e)}), 500


@playlist_builder_bp.route('/api/playlists/manual/<int:playlist_id>', methods=['DELETE'])
@requires_auth
def api_delete_manual_playlist(playlist_id):
    """Delete manual playlist

    Returns JSON:
        {
            "success": true
        }
    """
    from radio_monitor.database.crud import delete_manual_playlist
    from radio_monitor.database.queries import get_manual_playlist

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        cursor = db.get_cursor()

        try:
            # Verify playlist exists
            playlist = get_manual_playlist(cursor, playlist_id)
            if not playlist:
                return jsonify({'error': 'Playlist not found'}), 404

            # Delete playlist
            delete_manual_playlist(cursor, db.conn, playlist_id)

            return jsonify({'success': True})
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Error deleting manual playlist: {e}")
        return jsonify({'error': str(e)}), 500


@playlist_builder_bp.route('/api/playlists/manual/<int:playlist_id>/load', methods=['POST'])
@requires_auth
def api_load_manual_playlist(playlist_id):
    """Load playlist into builder state (for editing)

    Clears current selections and loads playlist songs.

    Returns JSON:
        {
            "success": true,
            "song_count": 23
        }
    """
    from radio_monitor.database.crud import clear_builder_state, add_song_to_builder_state
    from radio_monitor.database.queries import get_manual_playlist_songs, get_manual_playlist

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        cursor = db.get_cursor()

        try:
            # Verify playlist exists
            playlist = get_manual_playlist(cursor, playlist_id)
            if not playlist:
                return jsonify({'error': 'Playlist not found'}), 404

            # Clear current selections
            session_id = get_session_id()
            clear_builder_state(cursor, db.conn, session_id)

            # Load playlist songs
            songs = get_manual_playlist_songs(cursor, playlist_id)
            for song in songs:
                add_song_to_builder_state(cursor, db.conn, session_id, song['id'])

            return jsonify({
                'success': True,
                'song_count': len(songs)
            })
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Error loading manual playlist: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== PLEX INTEGRATION ====================

@playlist_builder_bp.route('/api/playlists/manual/<int:playlist_id>/create-in-plex', methods=['POST'])
@requires_auth
def api_create_playlist_in_plex(playlist_id):
    """Create playlist in Plex

    Returns JSON:
        {
            "success": true,
            "added": 23,
            "not_found": 2,
            "not_found_list": [...]
        }
    """
    from radio_monitor.gui import load_settings
    from radio_monitor.database.queries import get_manual_playlist, get_manual_playlist_songs
    from radio_monitor.plex import create_plex_manual_playlist

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        cursor = db.get_cursor()

        try:
            # Get playlist
            playlist = get_manual_playlist(cursor, playlist_id)
            if not playlist:
                return jsonify({'error': 'Playlist not found'}), 404

            # Get playlist songs
            songs = get_manual_playlist_songs(cursor, playlist_id)
            if not songs:
                return jsonify({'error': 'Playlist has no songs'}), 400

            # Get Plex settings
            settings = load_settings()
            plex_url = settings.get('plex', {}).get('url', 'http://localhost:32400')
            plex_token = settings.get('plex', {}).get('token', '')

            if not plex_token:
                return jsonify({'error': 'Plex token not configured'}), 500

            # Create playlist in Plex
            playlist_name = playlist.get('plex_playlist_name') or playlist['name']
            music_library_name = settings.get('plex', {}).get('music_library_name', 'Music')

            result = create_plex_manual_playlist(
                playlist_name=playlist_name,
                songs=songs,
                plex_url=plex_url,
                plex_token=plex_token,
                music_library_name=music_library_name
            )

            if result.get('success'):
                return jsonify(result)
            else:
                return jsonify({'error': result.get('error', 'Failed to create Plex playlist')}), 500
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Error creating playlist in Plex: {e}")
        return jsonify({'error': str(e)}), 500


@playlist_builder_bp.route('/api/playlists/manual/<int:playlist_id>/update-in-plex', methods=['POST'])
@requires_auth
def api_update_playlist_in_plex(playlist_id):
    """Update playlist in Plex (delete and recreate)

    Returns JSON:
        {
            "success": true,
            "added": 23,
            "not_found": 2,
            "not_found_list": [...]
        }
    """
    from radio_monitor.gui import load_settings
    from radio_monitor.database.queries import get_manual_playlist, get_manual_playlist_songs
    from radio_monitor.plex import update_plex_manual_playlist

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        cursor = db.get_cursor()

        try:
            # Get playlist
            playlist = get_manual_playlist(cursor, playlist_id)
            if not playlist:
                return jsonify({'error': 'Playlist not found'}), 404

            # Get playlist songs
            songs = get_manual_playlist_songs(cursor, playlist_id)
            if not songs:
                return jsonify({'error': 'Playlist has no songs'}), 400

            # Get Plex settings
            settings = load_settings()
            plex_url = settings.get('plex', {}).get('url', 'http://localhost:32400')
            plex_token = settings.get('plex', {}).get('token', '')

            if not plex_token:
                return jsonify({'error': 'Plex token not configured'}), 500

            # Update playlist in Plex (delete and recreate)
            playlist_name = playlist.get('plex_playlist_name') or playlist['name']
            music_library_name = settings.get('plex', {}).get('music_library_name', 'Music')

            result = update_plex_manual_playlist(
                playlist_name=playlist_name,
                songs=songs,
                plex_url=plex_url,
                plex_token=plex_token,
                old_playlist_name=None,  # Will use playlist_name
                music_library_name=music_library_name
            )

            if result.get('success'):
                return jsonify(result)
            else:
                return jsonify({'error': result.get('error', 'Failed to update Plex playlist')}), 500
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Error updating playlist in Plex: {e}")
        return jsonify({'error': str(e)}), 500
