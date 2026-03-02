"""
Blocklist routes for Radio Monitor GUI

Provides management interface for blocking artists and songs from playlist generation.
"""

import logging
from flask import Blueprint, render_template, jsonify, request, current_app
from radio_monitor.auth import requires_auth
from radio_monitor.database.queries import (
    get_blocklist_items, get_blocklist_stats, search_artists_songs_for_blocklist
)
from radio_monitor.database.crud import (
    add_to_blocklist, remove_from_blocklist, export_blocklist, import_blocklist,
    get_blocklist_preview
)

logger = logging.getLogger(__name__)

blocklist_bp = Blueprint('blocklist', __name__)


def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')


# ==================== PAGE ROUTES ====================

@blocklist_bp.route('/blocklist')
@requires_auth
def blocklist_page():
    """Blocklist management page"""
    db = get_db()

    if not db:
        return render_template('error.html', error='Database not initialized'), 500

    return render_template('blocklist.html')


# ==================== API ENDPOINTS ====================

@blocklist_bp.route('/api/blocklist')
@requires_auth
def api_get_blocklist():
    """API endpoint for getting blocklist items (paginated)

    Query params:
        - entity_type: 'artist', 'song', or None (all)
        - page: Page number (default: 1)
        - limit: Items per page (default: 50)
    """
    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    entity_type = request.args.get('entity_type')
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 50, type=int)

    # Validate entity_type
    if entity_type and entity_type not in ['artist', 'song']:
        return jsonify({'error': 'Invalid entity_type. Must be "artist" or "song"'}), 400

    cursor = db.get_cursor()
    try:
        result = get_blocklist_items(cursor, entity_type, page, limit)
    finally:
        cursor.close()

    return jsonify(result)


@blocklist_bp.route('/api/blocklist/stats')
@requires_auth
def api_get_blocklist_stats():
    """API endpoint for getting blocklist statistics"""
    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()
    try:
        stats = get_blocklist_stats(cursor)
    finally:
        cursor.close()

    return jsonify(stats)


@blocklist_bp.route('/api/blocklist/add', methods=['POST'])
@requires_auth
def api_add_to_blocklist():
    """API endpoint for adding artist or song to blocklist

    Request body (JSON):
        - items: Array of items to block, each with:
            - type: 'artist' or 'song'
            - id: Artist MBID or song ID
            - block_all: Boolean (for artists, true = block all songs)
            - reason: Optional reason for blocking
    """
    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    data = request.get_json()
    items = data.get('items', [])

    if not items:
        return jsonify({'error': 'No items provided'}), 400

    cursor = db.get_cursor()
    try:
        added_count = 0
        skipped_count = 0
        for item in items:
            entity_type = item.get('type')
            reason = item.get('reason', '')

            if entity_type == 'artist':
                artist_mbid = item.get('id')
                if not artist_mbid:
                    continue

                # entity_id format: "artist:{mbid}"
                entity_id = f"artist:{artist_mbid}"
                blocklist_id = add_to_blocklist(
                    cursor, db.conn, 'artist', entity_id,
                    artist_mbid=artist_mbid, reason=reason
                )
                if blocklist_id:
                    added_count += 1
                else:
                    skipped_count += 1

            elif entity_type == 'song':
                song_id = item.get('id')
                if not song_id:
                    continue

                # Get artist_mbid for this song
                cursor.execute("SELECT artist_mbid FROM songs WHERE id = ?", (song_id,))
                row = cursor.fetchone()
                if not row:
                    continue

                artist_mbid = row[0]

                # entity_id format: "song:{song_id}"
                entity_id = f"song:{song_id}"
                blocklist_id = add_to_blocklist(
                    cursor, db.conn, 'song', entity_id,
                    artist_mbid=artist_mbid, song_id=song_id, reason=reason
                )
                if blocklist_id:
                    added_count += 1
                else:
                    skipped_count += 1

        # Note: add_to_blocklist already commits, so no need to commit again

        message = f'Added {added_count} items to blocklist'
        if skipped_count > 0:
            message += f' ({skipped_count} already blocked)'

        return jsonify({
            'success': True,
            'added': added_count,
            'skipped': skipped_count,
            'message': message
        })

    except Exception as e:
        logger.error(f"Error adding to blocklist: {e}")
        db.conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


@blocklist_bp.route('/api/blocklist/preview', methods=['POST'])
@requires_auth
def api_preview_blocklist():
    """API endpoint for previewing impact of blocking items

    Request body (JSON):
        - items: Array of items to block (same format as /add)

    Returns:
        - total_songs: Number of songs that will be blocked
    """
    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    data = request.get_json()
    items = data.get('items', [])

    cursor = db.get_cursor()
    try:
        total_songs = get_blocklist_preview(cursor, items)
    finally:
        cursor.close()

    return jsonify({
        'total_songs': total_songs
    })


@blocklist_bp.route('/api/blocklist/<int:blocklist_id>', methods=['DELETE'])
@requires_auth
def api_remove_from_blocklist(blocklist_id):
    """API endpoint for removing item from blocklist

    Path params:
        - blocklist_id: ID of blocklist entry to remove
    """
    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()
    try:
        success = remove_from_blocklist(cursor, db.conn, blocklist_id)
        db.conn.commit()

        if not success:
            return jsonify({'error': 'Blocklist entry not found'}), 404

        return jsonify({
            'success': True,
            'message': 'Removed from blocklist'
        })

    except Exception as e:
        logger.error(f"Error removing from blocklist: {e}")
        db.conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


@blocklist_bp.route('/api/blocklist/export', methods=['POST'])
@requires_auth
def api_export_blocklist():
    """API endpoint for exporting blocklist to JSON

    Returns:
        JSON export of blocklist data
    """
    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()
    try:
        export_data = export_blocklist(cursor)
    finally:
        cursor.close()

    return jsonify(export_data)


@blocklist_bp.route('/api/blocklist/import', methods=['POST'])
@requires_auth
def api_import_blocklist():
    """API endpoint for importing blocklist from JSON

    Request body (JSON):
        - version: Export format version
        - exported_at: Export timestamp
        - items: Array of blocklist items

    Returns:
        Import results with counts of imported, skipped, and errors
    """
    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    data = request.get_json()

    if not data or 'items' not in data:
        return jsonify({'error': 'Invalid import data format'}), 400

    cursor = db.get_cursor()
    try:
        result = import_blocklist(cursor, db.conn, data)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error importing blocklist: {e}")
        db.conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


@blocklist_bp.route('/api/blocklist/search')
@requires_auth
def api_search_blocklist():
    """API endpoint for searching artists and songs to add to blocklist

    Query params:
        - q: Search query (matches artist name or song title)
        - limit: Maximum results per type (default: 20)

    Returns:
        Dict with keys: artists, songs
    """
    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 20, type=int)

    if not query:
        return jsonify({'error': 'Search query required'}), 400

    if len(query) < 2:
        return jsonify({'error': 'Search query must be at least 2 characters'}), 400

    cursor = db.get_cursor()
    try:
        results = search_artists_songs_for_blocklist(cursor, query, limit)
    finally:
        cursor.close()

    return jsonify(results)


@blocklist_bp.route('/api/blocklist/debug')
@requires_auth
def api_debug_blocklist():
    """Debug endpoint to check blocklist status"""
    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()
    try:
        # Count all blocklist entries
        cursor.execute("SELECT COUNT(*) FROM blocklist")
        total_count = cursor.fetchone()[0]

        # Get all entries
        cursor.execute("""
            SELECT bl.entity_type, bl.entity_id, bl.song_id, a.name as artist_name, s.song_title
            FROM blocklist bl
            LEFT JOIN artists a ON bl.artist_mbid = a.mbid
            LEFT JOIN songs s ON bl.song_id = s.id
            ORDER BY bl.created_at DESC
            LIMIT 10
        """)
        entries = cursor.fetchall()

        return jsonify({
            'total_entries': total_count,
            'recent_entries': entries,
            'database_path': db.db_path
        })
    finally:
        cursor.close()
