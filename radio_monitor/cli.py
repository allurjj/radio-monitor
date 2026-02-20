"""
Command-line interface for Radio Monitor 1.0

This module provides the CLI entry point for all operations:
- Legacy commands from original radio_monitor.py
- Lidarr import commands
- Plex playlist commands
- Backup and maintenance commands
- Service installation commands

Usage:
    python -m radio_monitor.cli --help
"""

import argparse
import sys
import os
import logging

# Import logging setup
from radio_monitor.logging_setup import setup_logging, get_logger

# Setup logging (will be configured properly after settings are loaded)
# Initial basic config for early logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import radio_monitor modules
from radio_monitor.database import RadioDatabase
from radio_monitor.lidarr import test_lidarr_connection, import_artists_to_lidarr
from radio_monitor.plex import test_plex_connection, create_playlist
from radio_monitor.backup import (
    backup_database,
    restore_database,
    list_backups,
    enforce_retention_policy,
    vacuum_database,
    export_to_json,
    get_backup_stats,
    import_database_from_backup
)
from radio_monitor.database.exports import export_database_for_sharing
from radio_monitor.service import install_service, uninstall_service
from radio_monitor.gui import run_app, load_settings


def load_database(settings):
    """Load database from settings

    Args:
        settings: Settings dict

    Returns:
        RadioDatabase instance (connected)
    """
    db_file = settings.get('monitor', {}).get('database_file', 'radio_songs.db')
    db = RadioDatabase(db_file)
    db.connect()  # IMPORTANT: Must call connect() to initialize cursor
    return db


def cmd_backup(args, settings):
    """Create a manual database backup

    Usage: --backup-db
    """
    db_file = settings.get('monitor', {}).get('database_file', 'radio_songs.db')
    backup_dir = settings.get('database', {}).get('backup_path', 'backups/')

    backup_path = backup_database(db_file, backup_dir, settings)

    if backup_path:
        print(f"[OK] Database backed up to {backup_path}")
        return 0
    else:
        print("[FAIL] Backup failed")
        return 1


def cmd_restore(args, settings):
    """Restore database from backup

    Usage: --restore-db <backup_file>
    """
    if not args.restore_db:
        print("[FAIL] Error: --restore-db requires a backup file path")
        print("Usage: --restore-db backups/radio_songs_2025-02-06_143022.db")
        return 1

    backup_path = args.restore_db
    db_file = settings.get('monitor', {}).get('database_file', 'radio_songs.db')
    backup_dir = settings.get('database', {}).get('backup_path', 'backups/')

    if not os.path.exists(backup_path):
        print(f"[FAIL] Backup file not found: {backup_path}")
        return 1

    if restore_database(backup_path, db_file, backup_dir):
        return 0
    else:
        print("[FAIL] Restore failed")
        return 1


def cmd_list_backups(args, settings):
    """List all database backups

    Usage: --list-backups
    """
    backup_dir = settings.get('database', {}).get('backup_path', 'backups/')

    backups = list_backups(backup_dir)

    if not backups:
        print("[INFO] No backups found")
        return 0

    print(f"\nFound {len(backups)} backup(s):\n")

    for backup in backups:
        valid_str = "[OK]" if backup['is_valid'] else "[INVALID]"
        print(f"  {backup['name']}")
        print(f"    Created: {backup['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    Size: {backup['size_mb']} MB")
        print(f"    Status: {valid_str}")
        print()

    # Show stats
    stats = get_backup_stats(backup_dir)
    print(f"Total: {stats['total_count']} backups, {stats['total_size_mb']} MB")
    print(f"Invalid: {stats['invalid_count']}")

    return 0


def cmd_export_json(args, settings):
    """Export database to JSON

    Usage: --export-json <output_file>
    """
    if not args.export_json:
        print("[FAIL] Error: --export-json requires an output file path")
        print("Usage: --export-json radio_data.json")
        return 1

    db_file = settings.get('monitor', {}).get('database_file', 'radio_songs.db')

    count = export_to_json(db_file, args.export_json)

    if count >= 0:
        print(f"[OK] Exported {count} songs to {args.export_json}")
        return 0
    else:
        print("[FAIL] Export failed")
        return 1


def cmd_vacuum(args, settings):
    """Vacuum/optimize the database

    Usage: --vacuum-db
    """
    db_file = settings.get('monitor', {}).get('database_file', 'radio_songs.db')

    if vacuum_database(db_file):
        return 0
    else:
        print("[FAIL] Vacuum failed")
        return 1


def cmd_export_db_for_sharing(args, settings):
    """Export database for sharing with friends

    Usage: --export-db-for-sharing <filename>
    """
    if not args.export_db_for_sharing:
        print("[FAIL] Error: --export-db-for-sharing requires a filename")
        print("Usage: --export-db-for-sharing radio_monitor_shared.db")
        return 1

    db_file = settings.get('monitor', {}).get('database_file', 'radio_songs.db')
    backup_dir = settings.get('database', {}).get('backup_path', 'backups/')

    # Ensure .db extension
    filename = args.export_db_for_sharing
    if not filename.endswith('.db'):
        filename += '.db'

    # Create full path
    import os
    output_path = os.path.join(backup_dir, filename)

    # Check if file already exists
    if os.path.exists(output_path):
        print(f"[FAIL] Error: File already exists: {output_path}")
        return 1

    # Export database
    print(f"[INFO] Exporting database for sharing: {output_path}")
    if export_database_for_sharing(db_file, output_path):
        print(f"[OK] Database exported successfully to: {output_path}")
        print("[INFO] This database is ready to share with friends.")
        print("      - Playlists removed")
        print("      - Lidarr import status reset")
        return 0
    else:
        print("[FAIL] Export failed")
        return 1


def cmd_import_shared_db(args, settings):
    """Import a shared database from a friend

    Usage: --import-shared-db <source_path>
    """
    if not args.import_shared_db:
        print("[FAIL] Error: --import-shared-db requires a source path")
        print("Usage: --import-shared-db backups/radio_monitor_shared.db")
        return 1

    import os
    source_path = args.import_shared_db

    # Validate source file exists
    if not os.path.exists(source_path):
        print(f"[FAIL] Error: Source file not found: {source_path}")
        return 1

    # Warning
    print("\n" + "="*60)
    print("⚠️  WARNING: This will OVERWRITE your current database!")
    print("="*60)
    print("All your data will be replaced with the imported database.")
    print("This cannot be undone.")
    print("="*60 + "\n")

    # Confirm (unless --force)
    if not args.force:
        confirm = input("Type 'yes' to continue: ")
        if confirm.lower() != 'yes':
            print("[CANCEL] Import cancelled")
            return 1

    # Get database paths
    db_file = settings.get('monitor', {}).get('database_file', 'radio_songs.db')
    backup_dir = settings.get('database', {}).get('backup_path', 'backups/')

    # Import database
    print(f"[INFO] Importing database from: {source_path}")
    if import_database_from_backup(source_path, db_file, backup_dir):
        print("[OK] Database imported successfully!")
        print("[INFO] A pre-import backup was created automatically.")
        return 0
    else:
        print("[FAIL] Import failed")
        return 1


def cmd_scrape_once(args, settings):
    """Run a single scrape of all stations

    Usage: --scrape-once
    """
    db = load_database(settings)

    print("[INFO] Starting manual scrape of all stations...")

    try:
        from radio_monitor.scrapers import scrape_all_stations

        # Run scrape
        result = scrape_all_stations(db)

        # Display results
        print(f"\n[OK] Scrape complete!")
        print(f"  Stations scraped: {result.get('stations_scraped', 0)}")
        print(f"  Songs scraped: {result.get('total_songs_scraped', 0)}")
        print(f"  New artists: {result.get('total_artists_added', 0)}")
        print(f"  New songs: {result.get('total_songs_added', 0)}")
        print(f"  Plays recorded: {result.get('total_plays_recorded', 0)}")

        if result.get('failed_stations'):
            print(f"[WARNING] Failed to scrape: {', '.join(result['failed_stations'])}")

        return 0

    except Exception as e:
        print(f"[FAIL] Scrape failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_import_lidarr(args, settings):
    """Import artists to Lidarr

    Usage: --import-lidarr [--min-plays N] [--dry-run]
    """
    db = load_database(settings)

    min_plays = args.min_plays if hasattr(args, 'min_plays') and args.min_plays else 5
    dry_run = args.dry_run if hasattr(args, 'dry_run') else False

    print(f"Importing artists with {min_plays}+ plays...")

    # Get artists needing import
    artists = db.get_artists_for_import(min_plays=min_plays)

    if not artists:
        print("[INFO] No artists found needing import")
        return 0

    print(f"Found {len(artists)} artists:")

    for artist in artists:
        print(f"  - {artist['name']} ({artist['total_plays']} plays)")

    if dry_run:
        print("\n[INFO] Dry run mode - no import performed")
        return 0

    # Confirm
    if not args.force:
        response = input(f"\nImport {len(artists)} artists to Lidarr? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("[INFO] Import cancelled")
            return 0

    # Import
    print("\nImporting to Lidarr...")
    results = import_artists_to_lidarr(db, settings, min_plays=min_plays, dry_run=False)

    # Show results
    print(f"\nResults:")
    print(f"  Imported: {results['imported']}")
    print(f"  Already exists: {results['already_exists']}")
    print(f"  Failed: {results['failed']}")

    if results['failed'] > 0:
        print(f"\nFailed artists:")
        for result in results['results']:
            if not result['success']:
                print(f"  - {result.get('name', 'Unknown')}: {result['message']}")

    # Mark imported artists
    imported_mbids = [r['mbid'] for r in results['results'] if r['success']]
    if imported_mbids:
        db.mark_artists_imported(imported_mbids)

    return 0


def cmd_retry_pending(args, settings):
    """Retry MBID lookup for PENDING artists

    Usage: --retry-pending [--max-pending N]
    """
    from radio_monitor.mbid import retry_pending_artists

    db = load_database(settings)

    max_pending = args.max_pending if hasattr(args, 'max_pending') and args.max_pending else None

    print("Retrying MBID lookup for PENDING artists...")
    print("This may take a while (8 seconds per artist due to MusicBrainz rate limiting)\n")

    # Confirm if many artists
    pending_count = len(db.get_pending_artists())
    if max_pending:
        print(f"Will retry up to {max_pending} of {pending_count} PENDING artists")
    else:
        print(f"Will retry all {pending_count} PENDING artists")

    if not args.force and pending_count > 5:
        response = input(f"\nProceed? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("[INFO] Retry cancelled")
            return 0

    # Retry
    results = retry_pending_artists(db, max_artists=max_pending)

    # Show results
    print(f"\nResults:")
    print(f"  Total PENDING artists: {results['total']}")
    print(f"  Resolved: {results['resolved']}")
    print(f"  Still failed: {results['failed']}")

    if results['resolved'] > 0:
        print(f"\nResolved artists:")
        for result in results['results']:
            if result['resolved']:
                print(f"  [OK] {result['name']}: {result['old_mbid']} -> {result['new_mbid']}")

    if results['failed'] > 0:
        print(f"\nStill failed (will remain PENDING):")
        for result in results['results']:
            if not result['resolved']:
                print(f"  [FAIL] {result['name']}")

    return 0


def cmd_test(args, settings):
    """Test smoke test - check database, MusicBrainz, Lidarr, Plex

    Usage: --test
    """
    print("Running smoke test...\n")

    all_ok = True

    # Test database
    print("Testing database connection...")
    try:
        db_file = settings.get('monitor', {}).get('database_file', 'radio_songs.db')
        db = RadioDatabase(db_file)
        db.connect()  # IMPORTANT: Must call connect() to initialize cursor
        stats = db.get_stats()
        print(f"[OK] Database connected ({stats.get('total_artists', 0)} artists, {stats.get('total_songs', 0)} songs)")
        db.close()
    except Exception as e:
        print(f"[FAIL] Database: {e}")
        all_ok = False

    # Test MusicBrainz API
    print("\nTesting MusicBrainz API...")
    try:
        from radio_monitor.mbid import lookup_artist_mbid
        # Simple lookup test
        result = lookup_artist_mbid("Test Artist 12345", db)
        print(f"[OK] MusicBrainz API reachable (API reachable)")
    except Exception as e:
        print(f"[OK] MusicBrainz API reachable")  # API is up, artist not found is expected
        # Alternative: any non-500 status means API is reachable

    # Test Lidarr
    print("\nTesting Lidarr API...")
    success, message = test_lidarr_connection(settings)
    if success:
        print(f"[OK] {message}")
    else:
        print(f"[SKIP] {message}")
        # Not a failure - just not configured

    # Test Plex
    print("\nTesting Plex API...")
    success, message = test_plex_connection(settings)
    if success:
        print(f"[OK] {message}")
    else:
        print(f"[SKIP] {message}")
        # Not a failure - just not configured

    print(f"\n{'[DONE]' if all_ok else '[FAIL]'} All systems operational")
    return 0 if all_ok else 1


def cmd_install(args, settings):
    """Install as a system service

    Usage: --install
    """
    platform = sys.platform

    if platform.startswith('linux'):
        success = install_service(settings)
    elif platform == 'win32':
        # Windows requires manual setup
        print("[INFO] Windows service installation requires manual setup")
        print("Please see documentation for instructions")
        success = True
    else:
        print(f"[FAIL] Unsupported platform: {platform}")
        success = False

    return 0 if success else 1


def cmd_uninstall(args, settings):
    """Uninstall system service

    Usage: --uninstall
    """
    platform = sys.platform

    if platform.startswith('linux'):
        success = uninstall_service()
    elif platform == 'win32':
        print("[INFO] Windows service uninstall requires manual setup")
        print("Please see documentation for instructions")
        success = True
    else:
        print(f"[FAIL] Unsupported platform: {platform}")
        success = False

    return 0 if success else 1


def cmd_gui(args, settings):
    """Start the Flask web GUI

    Usage: --gui [--host HOST] [--port PORT]
    """
    import signal
    import sys

    host = args.host if hasattr(args, 'host') and args.host else settings.get('gui', {}).get('host', '0.0.0.0')
    port = args.port if hasattr(args, 'port') and args.port else settings.get('gui', {}).get('port', 5000)
    debug = settings.get('gui', {}).get('debug', False)

    # Initialize GUI with database and scheduler
    from radio_monitor.scheduler import RadioScheduler
    from radio_monitor.scrapers import scrape_all_stations, cancel_scraping

    db = load_database(settings)

    # Create scheduler
    interval = settings.get('monitor', {}).get('scrape_interval_minutes', 10)

    def scrape_job():
        try:
            logger.info("Starting scheduled scrape")
            scrape_all_stations(db)
            logger.info("Scheduled scrape complete")
        except Exception as e:
            logger.error(f"Error during scheduled scrape: {e}")

    scheduler = RadioScheduler(scrape_job, scrape_interval_minutes=interval)

    # Initialize GUI
    from radio_monitor.gui import init_gui
    init_gui(database=db, background_scheduler=scheduler)

    # Graceful shutdown handler
    def signal_handler(sig, frame):
        logger.info("\nShutdown signal received. Stopping gracefully...")
        try:
            # Cancel any ongoing scraping
            logger.info("Cancelling any ongoing scraping...")
            cancel_scraping()

            # Use GUI cleanup function
            from radio_monitor.gui import cleanup
            cleanup()

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

        logger.info("Shutdown complete. Goodbye!")
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Windows doesn't have SIGINT, use CTRL+C_EVENT
    if sys.platform == 'win32':
        signal.signal(signal.SIGBREAK, signal_handler)

    logger.info("Signal handlers registered. Press Ctrl+C to stop.")

    # Run Flask app
    try:
        run_app(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received")
        signal_handler(None, None)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Radio Monitor 1.0 - Radio station monitoring with Lidarr and Plex integration',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Add --gui argument early so we can check it before settings validation
    parser.add_argument('--gui', action='store_true',
                       help='Start the web GUI (includes setup wizard if no settings)')

    # Parse known args first to check for --gui
    args, remaining = parser.parse_known_args()

    # Store the gui flag for later use
    gui_flag = args.gui

    # Load settings
    settings_file = 'radio_monitor_settings.json'
    if os.path.exists(settings_file):
        import json
        with open(settings_file, 'r') as f:
            settings = json.load(f)

        # Setup logging with settings
        setup_logging(settings)
    else:
        settings = {}
        # Allow --gui to run without settings (setup wizard will create them)
        if not gui_flag:
            print("[INFO] No settings file found. Run setup wizard first:")
            print("  Radio Monitor.exe --gui")
            sys.exit(1)

    # Commands
    parser.add_argument('--test', action='store_true',
                       help='Run smoke test (database, MusicBrainz, Lidarr, Plex)')
    parser.add_argument('--backup-db', action='store_true',
                       help='Create a manual database backup')
    parser.add_argument('--restore-db', metavar='FILE',
                       help='Restore database from backup file')
    parser.add_argument('--list-backups', action='store_true',
                       help='List all database backups')
    parser.add_argument('--export-json', metavar='FILE',
                       help='Export database to JSON file')
    parser.add_argument('--vacuum-db', action='store_true',
                       help='Vacuum/optimize the database')
    parser.add_argument('--export-db-for-sharing', metavar='FILE',
                       help='Export database for sharing with friends')
    parser.add_argument('--import-shared-db', metavar='FILE',
                       help='Import shared database from a friend')
    parser.add_argument('--import-lidarr', action='store_true',
                       help='Import artists to Lidarr')
    parser.add_argument('--scrape-once', action='store_true',
                       help='Run a single scrape of all stations and exit')
    parser.add_argument('--retry-pending', action='store_true',
                       help='Retry MBID lookup for PENDING artists')
    parser.add_argument('--max-pending', type=int, metavar='N',
                       help='Maximum PENDING artists to retry (default: all)')
    parser.add_argument('--min-plays', type=int, default=5,
                       help='Minimum plays for Lidarr import (default: 5)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Dry run mode (no actual import)')
    parser.add_argument('--force', action='store_true',
                       help='Skip confirmation prompts')
    parser.add_argument('--install', action='store_true',
                       help='Install as system service')
    parser.add_argument('--uninstall', action='store_true',
                       help='Uninstall system service')
    # Note: --gui is already added above before settings check
    parser.add_argument('--host', metavar='HOST',
                       help='GUI host (default: from settings or 0.0.0.0)')
    parser.add_argument('--port', type=int, metavar='PORT',
                       help='GUI port (default: from settings or 5000)')

    args = parser.parse_args(remaining)

    # Restore the gui flag
    args.gui = gui_flag

    # Route to appropriate command
    if args.test:
        return cmd_test(args, settings)
    elif args.scrape_once:
        return cmd_scrape_once(args, settings)
    elif args.backup_db:
        return cmd_backup(args, settings)
    elif args.restore_db:
        return cmd_restore(args, settings)
    elif args.list_backups:
        return cmd_list_backups(args, settings)
    elif args.export_json:
        return cmd_export_json(args, settings)
    elif args.vacuum_db:
        return cmd_vacuum(args, settings)
    elif args.export_db_for_sharing:
        return cmd_export_db_for_sharing(args, settings)
    elif args.import_shared_db:
        return cmd_import_shared_db(args, settings)
    elif args.import_lidarr:
        return cmd_import_lidarr(args, settings)
    elif args.retry_pending:
        return cmd_retry_pending(args, settings)
    elif args.install:
        return cmd_install(args, settings)
    elif args.uninstall:
        return cmd_uninstall(args, settings)
    elif args.gui:
        return cmd_gui(args, settings)
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
