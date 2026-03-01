"""
System Routes for Radio Monitor 1.0

System status, health monitoring, and service connectivity checks.
"""

import logging
import os
from datetime import datetime
from flask import Blueprint, render_template, jsonify, current_app
from radio_monitor.auth import requires_auth

logger = logging.getLogger(__name__)

system_bp = Blueprint('system', __name__)


def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')


@system_bp.route('/api/system/status')
@requires_auth
def api_system_status():
    """Get comprehensive system status

    Returns JSON:
        {
            "database": {"status": "ok", "size_mb": 1.2, "version": 4},
            "scheduler": {"status": "running", "jobs": 3},
            "lidarr": {"status": "connected", "url": "..."},
            "plex": {"status": "connected", "url": "..."},
            "scrapers": {"status": "idle", "active_stations": 8},
            "uptime": "2 days, 4 hours"
        }
    """
    db = get_db()
    status = {
        'database': {},
        'scheduler': {},
        'lidarr': {},
        'plex': {},
        'scrapers': {},
        'uptime': 'Unknown'
    }

    # Database status
    if db:
        try:
            # Get database file size
            db_path = current_app.config.get('database_path', '')
            if db_path and os.path.exists(db_path):
                size_mb = os.path.getsize(db_path) / (1024 * 1024)
                status['database'] = {
                    'status': 'ok',
                    'size_mb': round(size_mb, 2),
                    'version': db.SCHEMA_VERSION,
                    'path': db_path
                }
            else:
                status['database'] = {'status': 'error', 'message': 'Database file not found'}
        except Exception as e:
            logger.error(f"Error getting database status: {e}")
            status['database'] = {'status': 'error', 'message': str(e)}
    else:
        status['database'] = {'status': 'error', 'message': 'Not initialized'}

    # Scheduler status
    try:
        scheduler = current_app.config.get('scheduler')
        if scheduler and hasattr(scheduler, 'scheduler'):
            # Check if the APScheduler is actually running
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.schedulers.base import STATE_RUNNING

            if hasattr(scheduler.scheduler, 'state') and scheduler.scheduler.state == STATE_RUNNING:
                jobs = scheduler.scheduler.get_jobs()
                status['scheduler'] = {
                    'status': 'running',
                    'jobs': len(jobs),
                    'next_run': jobs[0].next_run_time.isoformat() if jobs else None
                }
            else:
                status['scheduler'] = {'status': 'stopped', 'jobs': 0}
        else:
            status['scheduler'] = {'status': 'stopped', 'jobs': 0}
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        status['scheduler'] = {'status': 'error', 'message': str(e)}

    # Lidarr status
    try:
        lidarr_url = current_app.config.get('lidarr_url')
        if lidarr_url:  # Check if URL is configured
            # Try to connect to Lidarr
            import requests
            try:
                headers = {}
                lidarr_api_key = current_app.config.get('lidarr_api_key')
                if lidarr_api_key:
                    headers['X-Api-Key'] = lidarr_api_key

                response = requests.get(f"{lidarr_url}/api/v1/system/status", headers=headers, timeout=3)
                if response.status_code == 200:
                    status['lidarr'] = {
                        'status': 'connected',
                        'url': lidarr_url,
                        'version': response.json().get('version', 'unknown')
                    }
                elif response.status_code == 401:
                    status['lidarr'] = {'status': 'error', 'message': 'Invalid API key'}
                elif response.status_code == 404:
                    status['lidarr'] = {'status': 'error', 'message': 'Lidarr not found (wrong URL?)'}
                else:
                    status['lidarr'] = {'status': 'error', 'message': f'HTTP {response.status_code}'}
            except requests.exceptions.Timeout:
                status['lidarr'] = {'status': 'timeout', 'message': 'Connection timeout'}
            except Exception as e:
                status['lidarr'] = {'status': 'disconnected', 'message': str(e)}
        else:
            status['lidarr'] = {'status': 'not_configured', 'message': 'Lidarr URL not set'}
    except Exception as e:
        logger.error(f"Error checking Lidarr: {e}")
        status['lidarr'] = {'status': 'error', 'message': str(e)}

    # Plex status
    try:
        plex_url = current_app.config.get('plex_url')
        if plex_url:  # Check if URL is configured
            status['plex'] = {
                'status': 'configured',
                'url': plex_url
            }
        else:
            status['plex'] = {'status': 'not_configured', 'message': 'Plex URL not set'}
    except Exception as e:
        logger.error(f"Error checking Plex: {e}")
        status['plex'] = {'status': 'error', 'message': str(e)}

    # Scraper status
    try:
        if db:
            stations = db.get_all_stations_with_health()
            enabled_stations = [s for s in stations if s.get('enabled', False)]

            # Check if scheduler is actually running
            scheduler_running = False
            scheduler = current_app.config.get('scheduler')
            if scheduler and hasattr(scheduler, 'scheduler'):
                from apscheduler.schedulers.base import STATE_RUNNING
                if hasattr(scheduler.scheduler, 'state') and scheduler.scheduler.state == STATE_RUNNING:
                    scheduler_running = True

            status['scrapers'] = {
                'status': 'running' if scheduler_running else 'idle',
                'active_stations': len(enabled_stations),
                'total_stations': len(stations)
            }
        else:
            status['scrapers'] = {'status': 'error', 'message': 'Database not initialized'}
    except Exception as e:
        logger.error(f"Error getting scraper status: {e}")
        status['scrapers'] = {'status': 'error', 'message': str(e)}

    # App uptime
    try:
        start_time = current_app.config.get('start_time')
        if start_time:
            uptime = datetime.now() - start_time
            days = uptime.days
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            status['uptime'] = f'{days} days, {hours} hours, {minutes} minutes'
    except Exception as e:
        logger.error(f"Error calculating uptime: {e}")

    return jsonify(status)


@system_bp.route('/api/system/health')
@requires_auth
def api_system_health():
    """Get simplified health check (for monitoring tools)

    Returns JSON:
        {
            "status": "healthy",
            "checks": {
                "database": "ok",
                "scheduler": "ok",
                "lidarr": "ok"
            }
        }
    """
    # Call the full status endpoint
    status_response = api_system_status()
    status_data = status_response.get_json()

    # Determine overall health
    checks = {}
    overall_status = 'healthy'

    for component in ['database', 'scheduler', 'scrapers']:
        comp_data = status_data.get(component, {})
        comp_status = comp_data.get('status', 'unknown')
        checks[component] = comp_status
        if comp_status in ['error', 'disconnected']:
            overall_status = 'unhealthy'

    # Optional components (don't affect overall health)
    for component in ['lidarr', 'plex']:
        comp_data = status_data.get(component, {})
        checks[component] = comp_data.get('status', 'not_configured')

    return jsonify({
        'status': overall_status,
        'checks': checks
    })
