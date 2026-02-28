"""
Stations routes for Radio Monitor GUI

Provides list and detail views for radio stations with health tracking.
"""

import logging
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, current_app
from radio_monitor.auth import requires_auth
from radio_monitor.database.queries import get_station_detail, get_station_stats, get_station_top_songs, get_all_stations_with_health

logger = logging.getLogger(__name__)

stations_bp = Blueprint('stations', __name__)


def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')


@stations_bp.route('/stations')
@requires_auth
def stations_list():
    """Stations list page with health status"""
    db = get_db()

    if not db:
        return render_template('error.html', error='Database not initialized'), 500

    cursor = db.get_cursor()
    try:
        stations = get_all_stations_with_health(cursor)
    finally:
        cursor.close()

    return render_template('stations.html', stations=stations)


@stations_bp.route('/stations/<station_id>')
@requires_auth
def station_detail(station_id):
    """Station detail page with stats and recent plays"""
    db = get_db()

    if not db:
        return render_template('error.html', error='Database not initialized'), 500

    days = request.args.get('days', 30, type=int)

    cursor = db.get_cursor()
    try:
        # Get station details
        station = get_station_detail(cursor, station_id)
        if not station:
            return render_template('error.html', error=f"Station not found: {station_id}"), 404

        # Get station stats
        stats = get_station_stats(cursor, station_id, days)

        # Get top songs
        top_songs = get_station_top_songs(cursor, station_id, limit=100, days=days)
    finally:
        cursor.close()

    return render_template('station_detail.html',
                          station=station,
                          stats=stats,
                          top_songs=top_songs,
                          days=days)


# ==================== API ENDPOINTS ====================

@stations_bp.route('/api/stations')
@requires_auth
def api_stations():
    """API endpoint for all stations"""
    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()
    try:
        stations = get_all_stations_with_health(cursor)
    finally:
        cursor.close()

    return jsonify({
        'items': stations,
        'count': len(stations)
    })


@stations_bp.route('/api/stations/<station_id>')
@requires_auth
def api_station_detail(station_id):
    """API endpoint for single station details"""
    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    days = request.args.get('days', 30, type=int)

    cursor = db.get_cursor()
    try:
        station = get_station_detail(cursor, station_id)
        if not station:
            return jsonify({'error': 'Station not found'}), 404

        stats = get_station_stats(cursor, station_id, days)
        top_songs = get_station_top_songs(cursor, station_id, limit=100, days=days)
    finally:
        cursor.close()

    return jsonify({
        'station': station,
        'stats': stats,
        'top_songs': top_songs
    })


@stations_bp.route('/api/stations/<station_id>', methods=['PUT'])
@requires_auth
def api_update_station(station_id):
    """API endpoint to update station settings"""
    import sqlite3

    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    data = request.get_json()

    # Use a fresh connection to avoid transaction conflicts
    conn = sqlite3.connect(db.db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        # Get current enabled state to preserve it if not specified
        cursor.execute("SELECT enabled FROM stations WHERE id = ?", (station_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Station not found'}), 404
        current_enabled = result[0]

        # Build dynamic UPDATE query based on provided fields
        update_fields = []
        params = []

        # Handle enabled field
        if 'enabled' in data:
            update_fields.append("enabled = ?")
            params.append(1 if data['enabled'] else 0)
        else:
            # Preserve current enabled state if not specified
            update_fields.append("enabled = ?")
            params.append(current_enabled)

        # Handle other fields
        if 'name' in data:
            update_fields.append("name = ?")
            params.append(data['name'])

        if 'url' in data:
            update_fields.append("url = ?")
            params.append(data['url'])

        if 'genre' in data:
            update_fields.append("genre = ?")
            params.append(data['genre'])

        if 'market' in data:
            update_fields.append("market = ?")
            params.append(data['market'])

        if 'wait_time' in data:
            update_fields.append("wait_time = ?")
            params.append(data['wait_time'])

        if 'consecutive_failures' in data:
            update_fields.append("consecutive_failures = ?")
            params.append(data['consecutive_failures'])

        if update_fields:
            params.append(station_id)  # For WHERE clause
            query = f"""
                UPDATE stations
                SET {', '.join(update_fields)}
                WHERE id = ?
            """
            cursor.execute(query, params)
            conn.commit()
            logger.info(f"Updated station {station_id}: {update_fields}")

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating station {station_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@stations_bp.route('/api/stations/add', methods=['POST'])
@requires_auth
def api_add_station():
    """API endpoint to add a new station"""
    db = get_db()

    if not db:
        return jsonify({'success': False, 'error': 'Database not initialized'}), 500

    data = request.get_json()

    # Validate required fields
    required_fields = ['id', 'name', 'url', 'genre', 'market']
    missing_fields = [f for f in required_fields if f not in data or not data[f]]

    if missing_fields:
        return jsonify({
            'success': False,
            'message': f'Missing required fields: {", ".join(missing_fields)}'
        }), 400

    # Use a fresh connection for this request
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        # Check if station ID already exists
        cursor.execute("SELECT id FROM stations WHERE id = ?", (data['id'],))
        if cursor.fetchone():
            return jsonify({
                'success': False,
                'message': f'Station ID "{data["id"]}" already exists'
            }), 400

        # Insert new station
        cursor.execute("""
            INSERT INTO stations (id, name, url, genre, market, scraper_type, has_mbid, wait_time, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            data['id'],
            data['name'],
            data['url'],
            data['genre'],
            data['market'],
            data.get('scraper_type', 'iheart'),
            data.get('has_mbid', False),
            data.get('wait_time', 10)
        ))

        conn.commit()
        logger.info(f"Added new station: {data['id']} - {data['name']}")

        return jsonify({'success': True, 'message': 'Station added successfully'})
    except Exception as e:
        logger.error(f"Error adding station: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@stations_bp.route('/api/stations/<station_id>', methods=['DELETE'])
@requires_auth
def api_delete_station(station_id):
    """API endpoint to delete a station"""
    db = get_db()

    if not db:
        return jsonify({'success': False, 'error': 'Database not initialized'}), 500

    # Use a fresh connection for this request
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        # Check if station exists
        cursor.execute("SELECT id FROM stations WHERE id = ?", (station_id,))
        if not cursor.fetchone():
            return jsonify({
                'success': False,
                'message': f'Station not found: {station_id}'
            }), 404

        # Delete station (CASCADE will handle related records)
        cursor.execute("DELETE FROM stations WHERE id = ?", (station_id,))
        conn.commit()

        logger.info(f"Deleted station: {station_id}")

        return jsonify({'success': True, 'message': 'Station deleted successfully'})
    except Exception as e:
        logger.error(f"Error deleting station: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@stations_bp.route('/api/stations/<station_id>/test', methods=['POST'])
@requires_auth
def api_test_station(station_id):
    """Test scraper for a single station

    Returns JSON:
        {
            "success": true/false,
            "message": "Scrape complete",
            "songs_found": 10
        }
    """
    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        from radio_monitor.scrapers import scrape_single_station

        logger.info(f"Test scrape triggered for station: {station_id}")

        # Run single station scrape (returns list of songs)
        songs = scrape_single_station(db, station_id)

        logger.info(f"Test scrape complete for {station_id}: {len(songs)} songs found")

        return jsonify({
            'success': True,
            'message': f"Scrape complete - found {len(songs)} songs",
            'songs_found': len(songs)
        })

    except Exception as e:
        logger.error(f"Error during test scrape for {station_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
