"""
Search Routes for Radio Monitor 1.0

Global search across all entities (artists, songs, stations, playlists).
"""

import logging
from flask import Blueprint, jsonify, request, current_app
from radio_monitor.auth import requires_auth

logger = logging.getLogger(__name__)

search_bp = Blueprint('search', __name__)


def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')


@search_bp.route('/api/search')
@requires_auth
def api_search():
    """Global search across all entities

    Query params:
        q: Search query
        types: Comma-separated list of types to search (artists, songs, stations, playlists)
        limit: Maximum results per type (default: 10)

    Returns JSON:
        {
            "query": "taylor",
            "results": {
                "artists": [...],
                "songs": [...],
                "stations": [...],
                "playlists": [...]
            }
        }
    """
    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Search query is required'}), 400

    types_param = request.args.get('types', 'artists,songs,stations,playlists')
    types = [t.strip() for t in types_param.split(',') if t.strip()]
    limit = request.args.get('limit', 10, type=int)
    limit = min(max(1, limit), 50)  # Cap at 50

    results = {
        'query': query,
        'results': {}
    }

    cursor = db.get_cursor()
    try:
        # Search artists
        if 'artists' in types:
            cursor.execute("""
                SELECT mbid, name,
                       COUNT(DISTINCT s.id) as song_count,
                       MAX(a.last_seen_at) as last_seen
                FROM artists a
                LEFT JOIN songs s ON a.mbid = s.artist_mbid
                WHERE a.name LIKE ?
                GROUP BY a.mbid
                ORDER BY a.name
                LIMIT ?
            """, (f'%{query}%', limit))

            results['results']['artists'] = [
                {
                    'type': 'artist',
                    'id': row[0],
                    'name': row[1],
                    'song_count': row[2],
                    'last_seen': row[3],
                    'url': f'/artists/{row[0]}'
                }
                for row in cursor.fetchall()
            ]

        # Search songs
        if 'songs' in types:
            cursor.execute("""
                SELECT s.id, s.song_title, s.artist_name, s.play_count, s.last_seen_at
                FROM songs s
                WHERE s.song_title LIKE ? OR s.artist_name LIKE ?
                ORDER BY s.play_count DESC
                LIMIT ?
            """, (f'%{query}%', f'%{query}%', limit))

            results['results']['songs'] = [
                {
                    'type': 'song',
                    'id': row[0],
                    'title': row[1],
                    'artist': row[2],
                    'play_count': row[3],
                    'last_seen': row[4],
                    'url': f'/songs/{row[0]}'
                }
                for row in cursor.fetchall()
            ]

        # Search stations
        if 'stations' in types:
            cursor.execute("""
                SELECT id, name, genre, market, enabled
                FROM stations
                WHERE name LIKE ? OR genre LIKE ? OR market LIKE ?
                ORDER BY name
                LIMIT ?
            """, (f'%{query}%', f'%{query}%', f'%{query}%', limit))

            results['results']['stations'] = [
                {
                    'type': 'station',
                    'id': row[0],
                    'name': row[1],
                    'genre': row[2],
                    'market': row[3],
                    'enabled': bool(row[4]),
                    'url': f'/stations/{row[0]}'
                }
                for row in cursor.fetchall()
            ]

        # Search playlists
        if 'playlists' in types:
            cursor.execute("""
                SELECT id, name, is_auto, enabled, mode
                FROM playlists
                WHERE name LIKE ?
                ORDER BY name
                LIMIT ?
            """, (f'%{query}%', limit))

            results['results']['playlists'] = [
                {
                    'type': 'playlist',
                    'id': row[0],
                    'name': row[1],
                    'is_auto': bool(row[2]),
                    'enabled': bool(row[3]),
                    'mode': row[4],
                    'url': '/plex'
                }
                for row in cursor.fetchall()
            ]

        # Add total count
        total_results = sum(len(v) for v in results['results'].values())
        results['total'] = total_results

        return jsonify(results)

    except Exception as e:
        logger.error(f"Error performing search: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


@search_bp.route('/api/search/artists')
@requires_auth
def api_search_artists():
    """Quick search for artists (autocomplete)

    Query params:
        q: Search query
        limit: Maximum results (default: 10)

    Returns JSON:
        [
            {"id": "...", "name": "Taylor Swift", "song_count": 15},
            ...
        ]
    """
    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    limit = request.args.get('limit', 10, type=int)
    limit = min(max(1, limit), 50)

    cursor = db.get_cursor()
    try:
        cursor.execute("""
            SELECT mbid, name, COUNT(DISTINCT sp.song_id) as song_count
            FROM artists a
            LEFT JOIN songs sp ON a.mbid = sp.artist_mbid
            WHERE a.name LIKE ?
            GROUP BY a.mbid
            ORDER BY a.name
            LIMIT ?
        """, (f'%{query}%', limit))

        results = [
            {
                'id': row[0],
                'name': row[1],
                'song_count': row[2]
            }
            for row in cursor.fetchall()
        ]

        return jsonify(results)

    except Exception as e:
        logger.error(f"Error searching artists: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


@search_bp.route('/api/search/songs')
@requires_auth
def api_search_songs():
    """Quick search for songs (autocomplete)

    Query params:
        q: Search query
        limit: Maximum results (default: 10)

    Returns JSON:
        [
            {"id": 1, "title": "Anti-Hero", "artist": "Taylor Swift"},
            ...
        ]
    """
    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    limit = request.args.get('limit', 10, type=int)
    limit = min(max(1, limit), 50)

    cursor = db.get_cursor()
    try:
        cursor.execute("""
            SELECT id, song_title, artist_name
            FROM songs
            WHERE song_title LIKE ? OR artist_name LIKE ?
            ORDER BY play_count DESC
            LIMIT ?
        """, (f'%{query}%', f'%{query}%', limit))

        results = [
            {
                'id': row[0],
                'title': row[1],
                'artist': row[2]
            }
            for row in cursor.fetchall()
        ]

        return jsonify(results)

    except Exception as e:
        logger.error(f"Error searching songs: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
