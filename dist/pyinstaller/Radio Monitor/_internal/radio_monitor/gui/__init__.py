"""
Flask GUI Package for Radio Monitor 1.0

This package provides a web-based interface for Radio Monitor:
- Setup wizard for first-time configuration
- Dashboard with live stats
- Monitor controls (start/stop)
- Lidarr import interface
- Plex playlist generation
- Settings management

Key Principle: Single integrated app - Flask + APScheduler + Database in one process.
"""

import os
import sys
import json
import logging
from flask import Flask

logger = logging.getLogger(__name__)

# Get the project root directory
# Handle both normal Python execution and PyInstaller bundle
if getattr(sys, 'frozen', False):
    # Running in PyInstaller bundle
    # sys._MEIPASS is the temporary folder where PyInstaller extracts bundled files
    if hasattr(sys, '_MEIPASS'):
        # Files are extracted directly to _MEIPASS by PyInstaller
        BUNDLE_DIR = sys._MEIPASS
        TEMPLATE_DIR = os.path.join(BUNDLE_DIR, 'templates')
        STATIC_DIR = os.path.join(BUNDLE_DIR, 'static')
    else:
        # Fallback: look relative to executable
        BUNDLE_DIR = os.path.dirname(sys.executable)
        TEMPLATE_DIR = os.path.join(BUNDLE_DIR, '_internal', 'templates')
        STATIC_DIR = os.path.join(BUNDLE_DIR, '_internal', 'static')
else:
    # Normal Python execution
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    TEMPLATE_DIR = os.path.join(PROJECT_ROOT, 'templates')
    STATIC_DIR = os.path.join(PROJECT_ROOT, 'static')

# Create Flask app with explicit template and static folders
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = 'd475a0440c8aefa260c9c6e24d724dceb761b538bb0179fa6da68e482cf8240b'  # Generated 2026-02-12

# Import version info from radio_monitor package
# Use getter functions to prefer VERSION.py (build time) over package version (development)
try:
    from radio_monitor import get_version, get_github_url
    app.config['VERSION'] = get_version()
    app.config['GITHUB_URL'] = get_github_url()
except ImportError:
    # Fallback if import fails
    app.config['VERSION'] = '1.1.0'
    app.config['GITHUB_URL'] = 'https://github.com/allurjj/radio-monitor'

# Import and initialize authentication
from radio_monitor.auth import auth, requires_auth, is_auth_enabled

# Disable ALL caching for development
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True

logger.info(f"Flask app initialized with templates from: {TEMPLATE_DIR}")
logger.info(f"Static folder from: {STATIC_DIR}")
logger.info(f"Template folder exists: {os.path.exists(TEMPLATE_DIR)}")
logger.info(f"Static folder exists: {os.path.exists(STATIC_DIR)}")
logger.info(f"sys.frozen: {getattr(sys, 'frozen', False)}")
if hasattr(sys, '_MEIPASS'):
    logger.info(f"sys._MEIPASS: {sys._MEIPASS}")
logger.info(f"__file__: {__file__}")
logger.info(f"Current working directory: {os.getcwd()}")

# Global variables
db = None
settings = None
scheduler = None
mbid_retry_manager = None


def load_settings():
    """Load settings from radio_monitor_settings.json

    Returns:
        Settings dict or None if file doesn't exist
    """
    settings_file = 'radio_monitor_settings.json'

    if not os.path.exists(settings_file):
        return None

    try:
        with open(settings_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return None


def save_settings_to_file(settings_dict):
    """Save settings to radio_monitor_settings.json

    Args:
        settings_dict: Settings to save

    Returns:
        True if saved successfully, False otherwise
    """
    settings_file = 'radio_monitor_settings.json'

    try:
        with open(settings_file, 'w') as f:
            json.dump(settings_dict, f, indent=2)
        logger.info(f"Settings saved to {settings_file}")
        return True
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return False


def is_first_run():
    """Check if this is the first run (no settings file)

    Returns:
        True if first run, False otherwise
    """
    return load_settings() is None


def init_gui(database=None, background_scheduler=None):
    """Initialize GUI with database and scheduler

    Args:
        database: RadioDatabase instance
        background_scheduler: RadioScheduler instance
    """
    global db, scheduler, settings, mbid_retry_manager

    logger.info(f"[init_gui] Received database: {database}, type: {type(database)}")
    if database:
        logger.info(f"[init_gui] database.conn: {database.conn}, database.cursor: {database.cursor}")

    db = database
    scheduler = background_scheduler
    settings = load_settings()

    # Setup logging with settings
    from radio_monitor.logging_setup import setup_logging
    setup_logging(settings)

    # Store in Flask app config for access across requests
    app.config['db'] = database
    app.config['scheduler'] = background_scheduler
    app.config['settings'] = settings

    # IMPORTANT: Connect to database to initialize cursor
    database.connect()
    logger.info(f"Database connected: {database.db_path}")

    # Store database path for system status page
    if database and database.db_path:
        app.config['database_path'] = database.db_path

    # Store app start time for uptime calculation
    from datetime import datetime
    app.config['start_time'] = datetime.now()

    # Load service URLs from settings for system status page
    if settings:
        app.config['lidarr_url'] = settings.get('lidarr', {}).get('url')
        app.config['plex_url'] = settings.get('plex', {}).get('url')
        app.config['plex_token'] = settings.get('plex', {}).get('token')
        app.config['lidarr_api_key'] = settings.get('lidarr', {}).get('api_key')

        logger.info(f"Loaded service URLs - Lidarr: {app.config['lidarr_url']}, Plex: {app.config['plex_url']}")

    logger.info(f"[init_gui] After assignment - db: {db}, db.conn: {db.conn if db else None}, db.cursor: {db.cursor if db else None}")
    logger.info(f"[init_gui] Stored in app.config - db: {app.config['db']}, settings: {app.config['settings']}")

    # Add backup job if enabled
    if settings and settings.get('database', {}).get('backup_enabled', False):
        from radio_monitor.backup import backup_database
        db_file = settings.get('monitor', {}).get('database_file', 'radio_songs.db')
        backup_dir = settings.get('database', {}).get('backup_path', 'backups/')

        def backup_job_func():
            try:
                logger.info("Starting scheduled backup")
                backup_database(db_file, backup_dir, settings)
                logger.info("Scheduled backup complete")
            except Exception as e:
                logger.error(f"Error during scheduled backup: {e}")

        scheduler.add_backup_job(backup_job_func)
        logger.info("Backup job added to scheduler (daily at 3 AM)")

    # Add cleanup jobs
    if scheduler and scheduler.scheduler and settings:
        from radio_monitor import cleanup

        def activity_cleanup_job_func():
            try:
                logger.info("Starting scheduled activity log cleanup")
                deleted = cleanup.cleanup_activity_logs(database)
                logger.info(f"Scheduled activity cleanup complete: {deleted} entries deleted")
            except Exception as e:
                logger.error(f"Error during scheduled activity cleanup: {e}")

        def log_cleanup_job_func():
            try:
                logger.info("Starting scheduled log file cleanup")
                deleted = cleanup.cleanup_log_files()
                logger.info(f"Scheduled log cleanup complete: {deleted} files deleted")
            except Exception as e:
                logger.error(f"Error during scheduled log cleanup: {e}")

        def plex_cleanup_job_func():
            try:
                logger.info("Starting scheduled Plex failure cleanup")
                from radio_monitor.database import plex_failures
                deleted = plex_failures.cleanup_old_failures(database, days=7)
                if deleted > 0:
                    logger.info(f"Scheduled Plex failure cleanup complete: {deleted} entries deleted")
                elif deleted == 0:
                    logger.info("Scheduled Plex failure cleanup complete: no old entries to delete")
            except Exception as e:
                logger.error(f"Error during scheduled Plex failure cleanup: {e}")

        def database_cleanup_job_func():
            try:
                logger.info("Starting scheduled database cleanup (corrupted data)")
                from radio_monitor.database.cleanup import run_daily_cleanup
                cursor = database.get_cursor()
                stats = run_daily_cleanup(cursor, database.conn, dry_run=False)
                cursor.close()
                logger.info(f"Scheduled database cleanup complete: {stats['total_deleted']} entries deleted")
            except Exception as e:
                logger.error(f"Error during scheduled database cleanup: {e}")

        scheduler.add_cleanup_jobs(activity_cleanup_job_func, log_cleanup_job_func, plex_cleanup_job_func, database_cleanup_job_func)
        logger.info("Cleanup jobs added to scheduler (daily at 4 AM, Plex cleanup at 4:10 AM, DB cleanup at 4:20 AM)")

    # Initialize MBID retry manager (Phase 5 enhancement)
    if scheduler and scheduler.scheduler:
        from radio_monitor.mbid_retry import MBIDRetryManager
        mbid_retry_manager = MBIDRetryManager(database)
        mbid_retry_manager.initialize(scheduler.scheduler)
        logger.info("MBID retry manager initialized (daily retry every 24 hours)")

    # Initialize auto playlist manager (loads and schedules all auto playlists)
    if scheduler and scheduler.scheduler and settings:
        from radio_monitor.auto_playlists import AutoPlaylistManager
        plex_config = settings.get('plex', {})

        # Auto playlists should run as long as the scheduler exists (even if scraping is paused)
        # They don't depend on scraping - they just query the database
        def scheduler_alive():
            # Just check if scheduler exists and is initialized, not if scraping is running
            return scheduler.scheduler is not None if scheduler and scheduler.scheduler else False

        auto_playlist_manager = AutoPlaylistManager(
            db=database,
            plex_config=plex_config,
            monitor_running_callback=scheduler_alive
        )
        auto_playlist_manager.initialize(scheduler.scheduler)
        logger.info("Auto playlist manager initialized (scheduled all enabled auto playlists)")

    logger.info(f"GUI initialized - db: {db is not None}, scheduler: {scheduler is not None}, settings: {settings is not None}")


def run_app(host='0.0.0.0', port=5000, debug=False):
    """Run Flask application

    Args:
        host: Host to bind to (default: 0.0.0.0)
        port: Port to bind to (default: 5000)
        debug: Enable debug mode (default: False)
    """
    logger.info(f"Starting Flask GUI on {host}:{port}")

    try:
        app.run(host=host, port=port, debug=debug, use_reloader=False)
    finally:
        # Cleanup on exit
        logger.info("Flask app shutting down...")
        cleanup()


def cleanup():
    """Cleanup resources before shutdown"""
    global scheduler, db

    try:
        # Shutdown scheduler
        if scheduler and scheduler.scheduler:
            logger.info("Shutting down scheduler...")
            scheduler.shutdown(wait=True)
            logger.info("Scheduler shut down")
    except Exception as e:
        logger.error(f"Error shutting down scheduler: {e}")

    try:
        # Close database
        if db:
            logger.info("Closing database...")
            db.close()
            logger.info("Database closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}")


# Import wizard routes first (has before_request handler)
from radio_monitor.gui.routes import wizard

# Import and register blueprints
from radio_monitor.gui.routes import dashboard, monitor, lidarr, plex, playlists, settings as settings_routes, backup
from radio_monitor.gui.routes import system, activity, search, artists, songs, stations, logs
from radio_monitor.gui.routes import notifications, plex_failures, mbid_overrides, ai_playlists, playlist_builder

app.register_blueprint(dashboard.dashboard_bp)
app.register_blueprint(monitor.monitor_bp)
app.register_blueprint(lidarr.lidarr_bp)
app.register_blueprint(plex.plex_bp)
app.register_blueprint(playlists.playlists_bp)
app.register_blueprint(settings_routes.settings_bp)
app.register_blueprint(backup.backup_bp)
app.register_blueprint(system.system_bp)
app.register_blueprint(activity.activity_bp)
app.register_blueprint(search.search_bp)
app.register_blueprint(artists.artists_bp)
app.register_blueprint(songs.songs_bp)
app.register_blueprint(stations.stations_bp)
app.register_blueprint(logs.logs_bp)
app.register_blueprint(notifications.notifications_bp)
app.register_blueprint(plex_failures.plex_failures_bp)
app.register_blueprint(mbid_overrides.mbid_overrides_bp)
app.register_blueprint(ai_playlists.ai_playlists_bp)
app.register_blueprint(playlist_builder.playlist_builder_bp)

# Import and register auth blueprint
from radio_monitor.gui.routes import auth as auth_routes
app.register_blueprint(auth_routes.auth_bp)

logger.info("All GUI blueprints registered successfully")
logger.info("Authentication module initialized")
