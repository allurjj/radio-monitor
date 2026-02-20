"""
Database cleanup module for Radio Monitor 1.0

This module provides scheduled cleanup jobs to maintain data quality by:
- Removing NULL mbid artists (corrupted data)
- Removing artists with obviously invalid names (commas, too long, etc.)
- Removing orphaned data
- Cleaning up old PENDING entries

Scheduled cleanup runs daily via APScheduler to maintain database health.
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def cleanup_corrupted_artists(cursor, conn, dry_run=False):
    """Remove artists with corrupted data that slipped through validation

    Looks for:
    - Artists with NULL mbid
    - Artists with suspicious names (multiple commas, excessive length)
    - Artists with no valid songs

    Args:
        cursor: Database cursor
        conn: Database connection
        dry_run: If True, report what would be deleted without deleting

    Returns:
        dict: Statistics about cleanup operation
    """
    stats = {
        'null_mbid_deleted': 0,
        'invalid_names_deleted': 0,
        'orphaned_artists_deleted': 0,
        'pending_no_songs_deleted': 0,
        'total_deleted': 0
    }

    # 1. Find artists with NULL mbid
    cursor.execute("SELECT mbid, name FROM artists WHERE mbid IS NULL")
    null_mbid_artists = cursor.fetchall()

    if null_mbid_artists:
        logger.info(f"Found {len(null_mbid_artists)} artists with NULL mbid")
        if not dry_run:
            # Delete songs first (CASCADE should handle this, but let's be explicit)
            for artist_mbid, artist_name in null_mbid_artists:
                cursor.execute("DELETE FROM songs WHERE artist_mbid IS NULL")
            cursor.execute("DELETE FROM artists WHERE mbid IS NULL")
            stats['null_mbid_deleted'] = cursor.rowcount
        else:
            stats['null_mbid_deleted'] = len(null_mbid_artists)

    # 2. Find artists with suspicious names (likely corrupted)
    #    - Names with 2+ commas (artist lists)
    #    - Names > 100 characters
    cursor.execute("""
        SELECT mbid, name FROM artists
        WHERE
            length(name) > 100
            OR (length(name) - length(replace(name, ',', ''))) >= 2
    """)
    invalid_names = cursor.fetchall()

    if invalid_names:
        logger.info(f"Found {len(invalid_names)} artists with invalid names")
        if not dry_run:
            for artist_mbid, artist_name in invalid_names:
                logger.debug(f"Deleting artist with invalid name: {artist_name[:50]}...")
                cursor.execute("DELETE FROM artists WHERE mbid = ?", (artist_mbid,))
            stats['invalid_names_deleted'] = len(invalid_names)
        else:
            stats['invalid_names_deleted'] = len(invalid_names)

    # 3. Find artists with no songs (orphaned artists)
    #    Exclude PENDING artists (they might not have songs yet)
    cursor.execute("""
        SELECT a.mbid, a.name
        FROM artists a
        LEFT JOIN songs s ON a.mbid = s.artist_mbid
        WHERE s.id IS NULL
        AND a.mbid NOT LIKE 'PENDING-%'
    """)
    orphaned_artists = cursor.fetchall()

    if orphaned_artists:
        logger.info(f"Found {len(orphaned_artists)} orphaned artists (no songs)")
        if not dry_run:
            for artist_mbid, artist_name in orphaned_artists:
                logger.debug(f"Deleting orphaned artist: {artist_name}")
                cursor.execute("DELETE FROM artists WHERE mbid = ?", (artist_mbid,))
            stats['orphaned_artists_deleted'] = len(orphaned_artists)
        else:
            stats['orphaned_artists_deleted'] = len(orphaned_artists)

    # 4. Find PENDING artists with no songs (these serve no purpose)
    #    These are likely failed scrapes or duplicates
    cursor.execute("""
        SELECT a.mbid, a.name
        FROM artists a
        LEFT JOIN songs s ON a.mbid = s.artist_mbid
        WHERE s.id IS NULL
        AND a.mbid LIKE 'PENDING-%'
    """)
    pending_no_songs = cursor.fetchall()

    if pending_no_songs:
        logger.info(f"Found {len(pending_no_songs)} PENDING artists with no songs")
        if not dry_run:
            for artist_mbid, artist_name in pending_no_songs:
                logger.debug(f"Deleting PENDING artist with no songs: {artist_name}")
                cursor.execute("DELETE FROM artists WHERE mbid = ?", (artist_mbid,))
            stats['pending_no_songs_deleted'] = len(pending_no_songs)
        else:
            stats['pending_no_songs_deleted'] = len(pending_no_songs)

    if not dry_run:
        conn.commit()
        stats['total_deleted'] = (stats['null_mbid_deleted'] +
                                   stats['invalid_names_deleted'] +
                                   stats['orphaned_artists_deleted'] +
                                   stats['pending_no_songs_deleted'])

    return stats


def cleanup_old_pending_artists(cursor, conn, days=30, dry_run=False):
    """Remove old PENDING artists that never got resolved

    Args:
        cursor: Database cursor
        conn: Database connection
        days: Delete PENDING artists older than this many days
        dry_run: If True, report what would be deleted without deleting

    Returns:
        int: Number of artists deleted
    """
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

    cursor.execute("""
        SELECT COUNT(*) FROM artists
        WHERE mbid LIKE 'PENDING-%'
        AND first_seen_at < ?
    """, (cutoff_date,))

    count = cursor.fetchone()[0]

    if count > 0:
        logger.info(f"Found {count} PENDING artists older than {days} days")
        if not dry_run:
            cursor.execute("""
                DELETE FROM artists
                WHERE mbid LIKE 'PENDING-%'
                AND first_seen_at < ?
            """, (cutoff_date,))
            conn.commit()
            return cursor.rowcount

    return 0


def run_daily_cleanup(cursor, conn, dry_run=False):
    """Run all daily cleanup jobs

    This should be scheduled to run once per day via APScheduler.

    Args:
        cursor: Database cursor
        conn: Database connection
        dry_run: If True, report what would be deleted without deleting

    Returns:
        dict: Combined statistics from all cleanup jobs
    """
    logger.info("=" * 60)
    logger.info("Starting daily database cleanup...")
    logger.info("=" * 60)

    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    # 1. Clean up corrupted artists
    corrupted_stats = cleanup_corrupted_artists(cursor, conn, dry_run=dry_run)
    logger.info(f"Corrupted artists cleanup: {corrupted_stats}")

    # 2. Clean up old PENDING artists
    pending_count = cleanup_old_pending_artists(cursor, conn, days=30, dry_run=dry_run)
    logger.info(f"Old PENDING artists deleted: {pending_count}")

    # 3. Vacuum database to reclaim space
    if not dry_run:
        logger.info("Vacuuming database to reclaim space...")
        cursor.execute("VACUUM")
        logger.info("Database vacuum complete")

    logger.info("=" * 60)
    logger.info("Daily database cleanup complete!")
    logger.info("=" * 60)

    return {
        'corrupted_artists': corrupted_stats,
        'pending_artists_deleted': pending_count,
        'total_deleted': corrupted_stats.get('total_deleted', 0) + pending_count
    }
