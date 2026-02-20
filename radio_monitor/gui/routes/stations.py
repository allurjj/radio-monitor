"""
Stations routes for Radio Monitor GUI

Provides list and detail views for radio stations with health tracking.
"""

import logging
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
    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    data = request.get_json()

    cursor = db.get_cursor()
    try:
        # Update station
        if 'enabled' in data:
            cursor.execute("""
                UPDATE stations
                SET enabled = ?
                WHERE id = ?
            """, (1 if data['enabled'] else 0, station_id))

        db.conn.commit()
    finally:
        cursor.close()

    return jsonify({'success': True})
