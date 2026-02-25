"""
Monitor Routes for Radio Monitor 1.0

Station monitoring and scraping controls.
"""

import logging
from flask import Blueprint, render_template, jsonify, request, current_app
from radio_monitor.auth import requires_auth

logger = logging.getLogger(__name__)

monitor_bp = Blueprint('monitor', __name__)

def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')

@monitor_bp.route('/monitor')
@requires_auth
def monitor():
    """Monitor controls page"""
    from radio_monitor.gui import is_first_run
    from flask import redirect, url_for

    if is_first_run():
        return redirect(url_for('wizard'))

    return render_template('monitor.html')

@monitor_bp.route('/api/monitor/start', methods=['POST'])
@requires_auth
def api_monitor_start():
    """Start monitoring

    Returns JSON:
        {
            "status": "started",
            "message": "Monitoring started"
        }
    """
    from radio_monitor.gui import scheduler

    if scheduler:
        try:
            if scheduler.start():
                return jsonify({
                    'status': 'started',
                    'message': 'Monitoring started'
                })
            else:
                return jsonify({
                    'status': 'already_running',
                    'message': 'Monitoring already running'
                })
        except Exception as e:
            logger.error(f"Error starting monitor: {e}")
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Scheduler not initialized'}), 500

@monitor_bp.route('/api/monitor/stop', methods=['POST'])
@requires_auth
def api_monitor_stop():
    """Stop monitoring

    Returns JSON:
        {
            "status": "stopped",
            "message": "Monitoring stopped"
        }
    """
    from radio_monitor.gui import scheduler

    if scheduler:
        try:
            if scheduler.stop():
                return jsonify({
                    'status': 'stopped',
                    'message': 'Monitoring stopped'
                })
            else:
                return jsonify({
                    'status': 'already_stopped',
                    'message': 'Monitoring already stopped'
                })
        except Exception as e:
            logger.error(f"Error stopping monitor: {e}")
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Scheduler not initialized'}), 500

@monitor_bp.route('/api/monitor/status')
@requires_auth
def api_monitor_status():
    """Get monitor status

    Returns JSON:
        {
            "running": true/false,
            "interval": 10,
            "next_run": "2025-02-06T15:30:00"
        }
    """
    from radio_monitor.gui import scheduler

    logger.info(f"[api_monitor_status] Checking status - scheduler exists: {scheduler is not None}")

    if scheduler:
        try:
            running = scheduler.is_running()
            interval = scheduler.scrape_interval

            # Get next run time
            next_run = None
            job = scheduler.scheduler.get_job('scrape_job')
            if job and job.next_run_time:
                next_run = job.next_run_time.isoformat()

            logger.info(f"[api_monitor_status] Returning: running={running}, interval={interval}, next_run={next_run}")
            return jsonify({
                'running': running,
                'interval': interval,
                'next_run': next_run
            })
        except Exception as e:
            logger.error(f"Error getting monitor status: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    logger.warning("[api_monitor_status] Scheduler not initialized")
    return jsonify({'error': 'Scheduler not initialized'}), 500

@monitor_bp.route('/api/monitor/scrape', methods=['POST'])
@requires_auth
def api_monitor_scrape():
    """Trigger immediate manual scrape

    Returns JSON:
        {
            "success": true/false,
            "message": "Scrape complete",
            "songs_scraped": 150,
            "stations_scraped": 8
        }
    """
    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        from radio_monitor.scrapers import scrape_all_stations

        logger.info("Manual scrape triggered via API")

        # Run scrape
        result = scrape_all_stations(db)

        logger.info(f"Manual scrape complete: {result}")

        return jsonify({
            'success': True,
            'message': 'Scrape complete',
            'songs_scraped': result.get('total_songs_scraped', 0),
            'stations_scraped': result.get('stations_scraped', 0)
        })

    except Exception as e:
        logger.error(f"Error during manual scrape: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e),
            'error': str(e)
        }), 500

@monitor_bp.route('/api/stations/<station_id>', methods=['PUT'])
@requires_auth
def api_stations_update(station_id):
    """Update station

    Expects JSON:
        {
            "enabled": true,
            "consecutive_failures": 0
        }

    Returns JSON:
        {
            "success": true
        }
    """
    db = get_db()
    if db:
        try:
            data = request.json

            # Update station in database
            db.cursor.execute("""
                UPDATE stations
                SET enabled = ?,
                    consecutive_failures = ?
                WHERE id = ?
            """, (data.get('enabled', False), data.get('consecutive_failures', 0), station_id))

            db.conn.commit()

            return jsonify({'success': True})

        except Exception as e:
            logger.error(f"Error updating station: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    return jsonify({'error': 'Database not initialized'}), 500

@monitor_bp.route('/api/stations/<station_id>', methods=['DELETE'])
@requires_auth
def api_stations_delete(station_id):
    """Delete station

    Returns JSON:
        {
            "success": true,
            "message": "Station deleted successfully"
        }
    """
    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        success = db.delete_station(station_id)

        if success:
            return jsonify({
                'success': True,
                'message': f'Station {station_id} deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Station {station_id} not found'
            }), 404

    except Exception as e:
        logger.error(f"Error deleting station: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@monitor_bp.route('/api/stations/add', methods=['POST'])
@requires_auth
def api_stations_add():
    """Add a new station

    Expects JSON:
        {
            "id": "station_id",
            "name": "Station Name",
            "url": "https://...",
            "genre": "Genre",
            "market": "Market",
            "has_mbid": false,
            "scraper_type": "iheart",
            "wait_time": 10
        }

    Returns JSON:
        {
            "success": true,
            "message": "Station added successfully"
        }
    """
    db = get_db()

    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['id', 'name', 'url', 'genre', 'market']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'message': f'{field} is required'
                }), 400

        station_id = data['id'].strip().lower()
        name = data['name'].strip()
        url = data['url'].strip()
        genre = data['genre'].strip()
        market = data['market'].strip()
        has_mbid = data.get('has_mbid', False)
        scraper_type = data.get('scraper_type', 'iheart')
        wait_time = data.get('wait_time', 10)

        # Validate scraper_type (only iheart supported)
        if scraper_type != 'iheart':
            return jsonify({
                'success': False,
                'message': f"Unsupported scraper_type: '{scraper_type}'. "
                           f"Only 'iheart' is supported."
            }), 400

        # Add station
        success = db.add_station(station_id, name, url, genre, market, has_mbid, scraper_type, wait_time)

        if success:
            return jsonify({
                'success': True,
                'message': f'Station {station_id} added successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Station {station_id} already exists'
            }), 409  # Conflict

    except KeyError as e:
        logger.error(f"KeyError adding station: {e}")
        return jsonify({
            'success': False,
            'message': f'Missing required field: {str(e)}'
        }), 400
    except Exception as e:
        logger.error(f"Error adding station: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@monitor_bp.route('/api/status/lidarr')
@requires_auth
def api_status_lidarr():
    """Get Lidarr connection status

    Returns JSON:
        {
            "success": true/false,
            "message": "Connected (Lidarr v3.1.0.4875)" or error message
        }
    """
    from radio_monitor.gui import load_settings
    from radio_monitor.lidarr import test_lidarr_connection

    settings = load_settings()
    if not settings:
        return jsonify({
            'success': False,
            'message': 'Not configured'
        })

    try:
        success, message = test_lidarr_connection(settings)
        return jsonify({
            'success': success,
            'message': message
        })
    except Exception as e:
        logger.error(f"Error checking Lidarr status: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        })

@monitor_bp.route('/api/status/plex')
@requires_auth
def api_status_plex():
    """Get Plex connection status

    Returns JSON:
        {
            "success": true/false,
            "message": "Connected to ServerName (Plex 1.32.0)" or error message
        }
    """
    from radio_monitor.gui import load_settings
    from radio_monitor.plex import test_plex_connection

    settings = load_settings()
    if not settings:
        return jsonify({
            'success': False,
            'message': 'Not configured'
        })

    try:
        success, message = test_plex_connection(settings)
        return jsonify({
            'success': success,
            'message': message
        })
    except Exception as e:
        logger.error(f"Error checking Plex status: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        })
