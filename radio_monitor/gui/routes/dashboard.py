"""
Dashboard Routes for Radio Monitor 1.0

Main dashboard with statistics and charts.
"""

import logging
from flask import Blueprint, render_template, jsonify, request, current_app
from radio_monitor.auth import requires_auth

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)

def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')

@dashboard_bp.route('/')
@requires_auth
def dashboard():
    """Main dashboard"""
    from radio_monitor.gui import is_first_run
    from flask import redirect, url_for

    if is_first_run():
        return redirect(url_for('wizard'))

    # Get stats from database
    stats = {}
    recent_plays = []

    db = get_db()
    if db:
        try:
            stats = db.get_stats()
            # Get recent plays (last 10)
            # TODO: Implement get_recent_plays() in database.py
            # recent_plays = db.get_recent_plays(limit=10)
        except Exception as e:
            logger.error(f"Error getting stats: {e}")

    return render_template('dashboard.html', stats=stats, recent_plays=recent_plays)

@dashboard_bp.route('/charts')
@requires_auth
def charts():
    """Charts and visualization page"""
    from radio_monitor.gui import is_first_run
    from flask import redirect, url_for

    if is_first_run():
        return redirect(url_for('wizard'))

    return render_template('charts.html')

@dashboard_bp.route('/api/stats')
@requires_auth
def api_stats():
    """Get current statistics

    Returns JSON:
        {
            "artists": 150,
            "songs": 350,
            "plays_today": 45
        }
    """
    db = get_db()
    if db:
        try:
            stats = db.get_stats()
            return jsonify(stats)
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Database not initialized'}), 500

@dashboard_bp.route('/api/plays/recent')
@requires_auth
def api_plays_recent():
    """Get recent plays for dashboard live feed

    Query params:
        limit: Number of plays (default: 10)
        station_id: Filter by specific station ID (default: None = all stations)

    Returns JSON:
        [
            {
                "timestamp": "2025-02-06 12:34:56",
                "artist_name": "Taylor Swift",
                "song_title": "Anti-Hero",
                "station_id": "station_name": ""
            },
            ...
        ]
    """
    db = get_db()
    if db:
        try:
            limit = request.args.get('limit', 10, type=int)
            station_id = request.args.get('station_id', None)
            # Convert empty string to None for "All Stations"
            if station_id == '':
                station_id = None
            plays = db.get_recent_plays(limit=limit, station_id=station_id)
            return jsonify(plays)
        except Exception as e:
            logger.error(f"Error getting recent plays: {e}")
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Database not initialized'}), 500

@dashboard_bp.route('/api/charts/plays-over-time')
@requires_auth
def api_charts_plays_over_time():
    """Get plays over time data for line chart

    Query params:
        days: Number of days to look back (default: 30)
        station_id: Filter by station (optional)

    Returns JSON:
        {
            "dates": ["2025-01-01", "2025-01-02", ...],
            "plays": [450, 520, 480, ...]
        }
    """
    try:
        db = get_db()
        if not db:
            return jsonify({'error': 'Database not initialized'}), 500

        days = request.args.get('days', 30, type=int)
        station_id = request.args.get('station_id')  # String, not int!

        logger.info(f"Plays over time request: days={days}, station_id={station_id}")

        # Get plays over time, optionally filtered by station
        data = db.get_plays_over_time(days=days, station_id=station_id)

        dates = [row['date'] for row in data]
        plays = [row['total_plays'] for row in data]

        return jsonify({
            'dates': dates,
            'plays': plays
        })
    except Exception as e:
        logger.error(f"Error getting plays over time: {e}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/charts/top-songs')
@requires_auth
def api_charts_top_songs():
    """Get top songs data for bar chart

    Query params:
        limit: Maximum number of songs (default: 20)
        days: Number of days to look back (default: 30)
        station_id: Filter by station (optional)

    Returns JSON:
        {
            "songs": [
                {"artist": "Taylor Swift", "title": "Anti-Hero", "plays": 125},
                ...
            ]
        }
    """
    try:
        db = get_db()
        if not db:
            return jsonify({'error': 'Database not initialized'}), 500

        limit = request.args.get('limit', 20, type=int)
        days = request.args.get('days', 30, type=int)
        station_id = request.args.get('station_id')  # String, not int!

        logger.info(f"Top songs request: limit={limit}, days={days}, station_id={station_id}")

        # Get top songs (returns tuples: song_id, song_title, artist_name, play_count)
        songs = db.get_top_songs(days=days, station_id=station_id, limit=limit)

        logger.info(f"Top songs returned: {len(songs)} songs")

        # Format for chart (convert tuples to dicts)
        song_data = []
        for song in songs:
            song_data.append({
                'artist': song[2],  # artist_name
                'title': song[1],   # song_title
                'plays': song[3]    # play_count
            })

        return jsonify({
            'songs': song_data
        })
    except Exception as e:
        logger.error(f"Error getting top songs: {e}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/charts/top-artists')
@requires_auth
def api_charts_top_artists():
    """Get top artists data for bar chart

    Query params:
        limit: Maximum number of artists (default: 20)
        days: Only include plays from last N days (optional)
        station_id: Filter by station (optional)

    Returns JSON:
        {
            "artists": [
                {"name": "Artist Name", "plays": 123},
                ...
            ]
        }
    """
    try:
        db = get_db()
        if not db:
            return jsonify({'error': 'Database not initialized'}), 500

        # Get query parameters
        limit = request.args.get('limit', 20, type=int)
        days = request.args.get('days', type=int)
        station_id = request.args.get('station_id')  # String, not int!

        logger.info(f"Top artists request: limit={limit}, days={days}, station_id={station_id}")

        # Build station_ids list for filtering
        station_ids = [station_id] if station_id else None

        data = db.get_top_artists(days=days, station_ids=station_ids, limit=limit)

        artists = []
        for row in data:
            artists.append({
                'name': row[0],
                'plays': row[1]
            })

        return jsonify({
            'artists': artists
        })
    except Exception as e:
        logger.error(f"Error getting top artists: {e}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/charts/station-distribution')
@requires_auth
def api_charts_station_distribution():
    """Get station distribution data for pie chart

    Query params:
        days: Number of days to look back (default: None = all time)

    Returns JSON:
        {
            "stations": [
                {"name": "B96", "plays": 1234},
                {"name": "US99", "plays": 987},
                ...
            ]
        }
    """
    try:
        db = get_db()
        if not db:
            return jsonify({'error': 'Database not initialized'}), 500

        days = request.args.get('days', type=int)

        logger.info(f"Station distribution request: days={days}")

        data = db.get_station_distribution(days=days)

        stations = []
        for row in data:
            stations.append({
                'name': row['station_name'],
                'plays': row['play_count']
            })

        return jsonify({
            'stations': stations
        })
    except Exception as e:
        logger.error(f"Error getting station distribution: {e}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/stations/dropdown')
@requires_auth
def api_stations_dropdown():
    """Get all stations for dropdown filters (simple format)

    Returns JSON:
        {
            "stations": [
                {"id": "name": ""},
                ...
            ]
        }
    """
    try:
        db = get_db()
        if not db:
            return jsonify({'error': 'Database not initialized'}), 500

        cursor = db.get_cursor()
        try:
            from radio_monitor.database.queries import get_all_stations
            stations_tuples = get_all_stations(cursor)

            # Convert tuples to dicts with proper field names
            stations = []
            for station in stations_tuples:
                stations.append({
                    'id': station[0],      # id
                    'name': station[1]     # name
                })

            return jsonify({
                'stations': stations
            })
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Error getting stations: {e}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/mbid-retry/stats')
@requires_auth
def api_mbid_retry_stats():
    """Get MBID retry statistics

    Returns JSON:
        {
            "pending_count": 0,
            "last_retry_time": "2026-02-08 10:30:00",
            "total_retried": 150,
            "resolved": 145,
            "failed": 5,
            "deleted_old": 10
        }
    """
    try:
        from radio_monitor.gui import mbid_retry_manager

        if not mbid_retry_manager:
            return jsonify({
                'pending_count': 0,
                'last_retry_time': None,
                'total_retried': 0,
                'resolved': 0,
                'failed': 0,
                'deleted_old': 0,
                'message': 'MBID retry manager not initialized'
            })

        stats = mbid_retry_manager.get_stats()

        # Format last_retry_time
        if stats.get('last_retry_time'):
            stats['last_retry_time'] = stats['last_retry_time'].strftime('%Y-%m-%d %H:%M:%S')
        else:
            stats['last_retry_time'] = None

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error getting MBID retry stats: {e}")
        return jsonify({'error': str(e)}), 500

