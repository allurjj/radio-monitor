"""
Data Quality Health Check Module

This module provides local-only health checks for the Radio Monitor database.
All checks are performed without API calls to MusicBrainz.

Key Functions:
- run_health_check(): Comprehensive health check
- get_pending_mbid_songs(): Get songs with PENDING MBIDs
- get_known_bad_artists(): Find artists needing correction
- get_messy_titles(): Find songs with messy titles
- detect_potential_duplicates(): Find possible duplicate songs
- get_validated_count(): Count validated songs

Usage:
    from radio_monitor.data_quality import run_health_check

    issues = run_health_check(db)
    print(f"Found {len(issues)} data quality issues")
"""

import logging
import re
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def run_health_check(db) -> Dict[str, Any]:
    """Run comprehensive health check on database

    Args:
        db: RadioDatabase instance

    Returns:
        Dict with health check results
    """
    issues = {
        'critical': [],
        'warning': [],
        'info': [],
        'summary': {}
    }

    # Check 1: PENDING MBIDs - with song details
    pending_songs = get_pending_mbid_songs(db, limit=100)
    if pending_songs:
        issues['warning'].append({
            'type': 'pending_mbid',
            'count': len(pending_songs),
            'songs': pending_songs,
            'message': f'{len(pending_songs)} songs with PENDING MBIDs'
        })

    # Check 2: Known bad artist names
    bad_artists = get_known_bad_artists(db)
    if bad_artists:
        issues['critical'].append({
            'type': 'artist_names',
            'count': len(bad_artists),
            'artists': bad_artists,
            'message': f'{len(bad_artists)} songs with known artist name issues'
        })

    # Check 3: Messy song titles - with details
    messy = get_messy_titles(db, limit=100)
    if messy:
        issues['info'].append({
            'type': 'song_titles',
            'count': len(messy),
            'titles': messy,
            'message': f'{len(messy)} songs with messy titles (parentheticals, etc.)'
        })

    # Check 4: Potential duplicates - with details
    dupes = detect_potential_duplicates(db, limit=100)
    if dupes:
        issues['warning'].append({
            'type': 'duplicates',
            'count': len(dupes),
            'duplicates': dupes,
            'message': f'{len(dupes)} potential duplicate song pairs'
        })

    # Get validation stats
    validated_count = get_validated_count(db)
    invalid_count = get_invalid_count(db)

    # Summary
    stats = db.get_stats()
    total_songs = stats.get('total_songs', 0)
    issues['summary'] = {
        'total_songs': total_songs,
        'total_issues': sum(len(issues[k]) for k in ['critical', 'warning', 'info']),
        'health_score': calculate_health_score(total_songs, issues),
        'validated_count': validated_count,
        'invalid_count': invalid_count
    }

    return issues


def get_validated_count(db) -> int:
    """Count songs that have been validated with MusicBrainz recording checks

    Args:
        db: RadioDatabase instance

    Returns:
        Number of validated songs
    """
    cursor = db.get_cursor()
    try:
        # Check if validation_status column exists
        cursor.execute("PRAGMA table_info(songs)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'validation_status' in columns:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM songs
                WHERE validation_status = 'valid'
            """)
            result = cursor.fetchone()
            count = result[0] if result else 0
            logger.debug(f"Validated count: {count}")
            return count
        else:
            # Column doesn't exist yet (schema not migrated)
            logger.warning("validation_status column doesn't exist, returning 0")
            return 0
    except Exception as e:
        logger.error(f"Error getting validated count: {e}")
        return 0
    finally:
        cursor.close()


def get_invalid_count(db) -> int:
    """Count songs that failed validation with MusicBrainz

    Args:
        db: RadioDatabase instance

    Returns:
        Number of invalid songs
    """
    cursor = db.get_cursor()
    try:
        # Check if validation_status column exists
        cursor.execute("PRAGMA table_info(songs)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'validation_status' in columns:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM songs
                WHERE validation_status = 'invalid'
            """)
            result = cursor.fetchone()
            count = result[0] if result else 0
            logger.debug(f"Invalid count: {count}")
            return count
        else:
            # Column doesn't exist yet (schema not migrated)
            logger.warning("validation_status column doesn't exist, returning 0")
            return 0
    except Exception as e:
        logger.error(f"Error getting invalid count: {e}")
        return 0
    finally:
        cursor.close()


def get_pending_mbid_songs(db, limit: int = 100) -> List[Dict]:
    """Get songs with PENDING MBIDs with details

    Args:
        db: RadioDatabase instance
        limit: Maximum number of results (default: 100)

    Returns:
        List of dicts with song info
    """
    pending_songs = []
    cursor = db.get_cursor()

    try:
        cursor.execute("""
            SELECT id, artist_name, song_title, artist_mbid, play_count
            FROM songs
            WHERE artist_mbid LIKE 'PENDING-%'
            ORDER BY play_count DESC
            LIMIT ?
        """, (limit,))

        results = cursor.fetchall()
        for row in results:
            pending_songs.append({
                'song_id': row[0],
                'artist_name': row[1],
                'song_title': row[2],
                'artist_mbid': row[3],
                'play_count': row[4]
            })
    finally:
        cursor.close()

    return pending_songs


def get_known_bad_artists(db) -> List[Dict]:
    """Find songs with known bad artist names

    Args:
        db: RadioDatabase instance

    Returns:
        List of dicts with song info
    """
    from radio_monitor.normalization import ARTIST_NAME_CORRECTIONS

    bad_songs = []
    cursor = db.get_cursor()

    try:
        # Check for each known bad artist
        for bad_name, correct_name in ARTIST_NAME_CORRECTIONS.items():
            cursor.execute("""
                SELECT id, artist_name, song_title, play_count
                FROM songs
                WHERE LOWER(artist_name) = ?
            """, (bad_name,))

            results = cursor.fetchall()
            for row in results:
                bad_songs.append({
                    'song_id': row[0],
                    'current_artist': row[1],
                    'correct_artist': correct_name,
                    'song_title': row[2],
                    'play_count': row[3]
                })
    finally:
        cursor.close()

    return bad_songs


def get_messy_titles(db, limit: int = 100) -> List[Dict]:
    """Find songs with messy titles (parentheticals, features, etc.)

    Args:
        db: RadioDatabase instance
        limit: Maximum number of results (default: 100)

    Returns:
        List of dicts with song info
    """
    from radio_monitor.normalization import clean_song_title_for_query

    messy_songs = []
    cursor = db.get_cursor()

    try:
        # Find titles with parentheticals, brackets, etc.
        cursor.execute("""
            SELECT id, artist_name, song_title, play_count
            FROM songs
            WHERE song_title LIKE '%(%'
               OR song_title LIKE '%[%'
               OR song_title LIKE '%feat%'
               OR song_title LIKE '%ft.%'
               OR song_title LIKE '%featuring%'
            ORDER BY play_count DESC
            LIMIT ?
        """, (limit,))

        results = cursor.fetchall()
        for row in results:
            original = row[2]  # song_title
            cleaned = clean_song_title_for_query(original)

            messy_songs.append({
                'song_id': row[0],
                'artist_name': row[1],
                'original_title': original,
                'cleaned_title': cleaned,
                'play_count': row[3]
            })
    finally:
        cursor.close()

    return messy_songs


def detect_potential_duplicates(db, limit: int = 100) -> List[Dict]:
    """Detect potential duplicate songs

    Args:
        db: RadioDatabase instance
        limit: Maximum number of results (default: 100)

    Returns:
        List of potential duplicate groups
    """
    duplicates = []
    cursor = db.get_cursor()

    try:
        # Find songs with same artist but very similar titles
        cursor.execute("""
            SELECT s1.id as id1, s1.song_title as title1,
                   s2.id as id2, s2.song_title as title2,
                   s1.artist_name
            FROM songs s1
            JOIN songs s2 ON s1.artist_name = s2.artist_name AND s1.id < s2.id
            WHERE s1.artist_name = s2.artist_name
              AND LENGTH(s1.song_title) > 3
              AND LENGTH(s2.song_title) > 3
            LIMIT ?
        """, (limit,))

        results = cursor.fetchall()
        for row in results:
            # Calculate similarity (indices: id1=0, title1=1, id2=2, title2=3, artist=4)
            title1 = row[1].lower()
            title2 = row[3].lower()

            # Simple similarity check
            if title1 in title2 or title2 in title1 or title1.startswith(title2[:5]):
                duplicates.append({
                    'song_id1': row[0],
                    'song_id2': row[2],
                    'title1': row[1],
                    'title2': row[3],
                    'artist': row[4]
                })
    finally:
        cursor.close()

    return duplicates


def calculate_health_score(total_songs: int, issues: Dict) -> float:
    """Calculate overall health score (0-100)

    Args:
        total_songs: Total number of songs
        issues: Health check issues dict

    Returns:
        Health score (0-100)
    """
    if total_songs == 0:
        return 100.0

    # Count total issues from issue dicts with 'count' field
    critical_count = sum(issue.get('count', 0) for issue in issues.get('critical', []))
    warning_count = sum(issue.get('count', 0) for issue in issues.get('warning', []))
    info_count = sum(issue.get('count', 0) for issue in issues.get('info', []))

    # Calculate weighted score
    total_issues = (critical_count * 10) + (warning_count * 3) + (info_count * 1)

    # Calculate score
    # Start at 100, subtract points for issues
    # But don't go below 0
    score = max(0, 100 - (total_issues / total_songs * 100))

    return round(score, 1)


def get_songs_to_validate(db, count: int = 50) -> List[Dict]:
    """Get songs that need recording validation

    Args:
        db: RadioDatabase instance
        count: Number of songs to return (default: 50)

    Returns:
        List of song dicts to validate
    """
    cursor = db.get_cursor()

    try:
        # Check if validation_status column exists
        cursor.execute("PRAGMA table_info(songs)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'validation_status' in columns:
            # Get songs that haven't been validated yet, prioritized by play count
            cursor.execute("""
                SELECT id, artist_name, song_title, artist_mbid, play_count
                FROM songs
                WHERE validation_status = 'unvalidated' OR validation_status IS NULL
                ORDER BY play_count DESC
                LIMIT ?
            """, (count,))
        else:
            # Column doesn't exist, get all songs by play count
            cursor.execute("""
                SELECT id, artist_name, song_title, artist_mbid, play_count
                FROM songs
                WHERE artist_mbid NOT LIKE 'PENDING-%'
                ORDER BY play_count DESC
                LIMIT ?
            """, (count,))

        results = cursor.fetchall()
        songs = []
        for row in results:
            songs.append({
                'id': row[0],
                'artist_name': row[1],
                'song_title': row[2],
                'artist_mbid': row[3],
                'play_count': row[4]
            })
        return songs
    finally:
        cursor.close()


def mark_song_validated(db, song_id: int, success: bool = True, error_message: str = None, method: str = 'unknown'):
    """Mark a song as validated

    Args:
        db: RadioDatabase instance
        song_id: Song ID to mark
        success: Whether validation was successful
        error_message: Error message if validation failed
        method: Validation method used (mbid, text_fallback, etc.)
    """
    cursor = db.get_cursor()

    try:
        # Check if validation_status column exists
        cursor.execute("PRAGMA table_info(songs)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'validation_status' not in columns:
            # Column doesn't exist - try to add it (defensive)
            logger.warning("validation_status column doesn't exist, attempting to add it...")
            try:
                cursor.execute("ALTER TABLE songs ADD COLUMN validation_status TEXT DEFAULT 'unvalidated'")
                cursor.execute("ALTER TABLE songs ADD COLUMN validated_at TIMESTAMP")
                cursor.execute("ALTER TABLE songs ADD COLUMN validation_method TEXT")
                db.conn.commit()
                logger.info("Added validation columns to songs table")
            except Exception as e:
                logger.error(f"Could not add validation columns: {e}")
                return  # Can't proceed without columns

        now = datetime.now().isoformat()
        status = 'valid' if success else 'invalid'

        cursor.execute("""
            UPDATE songs
            SET validation_status = ?,
                validated_at = ?,
                validation_method = ?
            WHERE id = ?
        """, (status, now, method, song_id))
        db.conn.commit()
        logger.debug(f"Marked song {song_id} as {status} (method: {method})")
    except Exception as e:
        logger.error(f"Error marking song validated: {e}")
        db.conn.rollback()
    finally:
        cursor.close()


def validate_batch_scheduled(db, batch_size: int = 50) -> Dict[str, Any]:
    """Validate a batch of songs for scheduled background validation

    This function is designed to be called by the scheduler for automated validation.
    It validates unvalidated songs against MusicBrainz recording database.

    Args:
        db: RadioDatabase instance
        batch_size: Number of songs to validate (default: 50)

    Returns:
        Dict with validation results
    """
    import time
    from radio_monitor.recording_validation import validate_recording_with_fallback

    try:
        songs_to_validate = get_songs_to_validate(db, count=batch_size)

        if not songs_to_validate:
            logger.info("Scheduled validation: No songs to validate")
            return {
                'success': True,
                'processed': 0,
                'updated': 0,
                'errors': 0,
                'skipped': 0,
                'message': 'No songs to validate'
            }

        processed = 0
        updated = 0
        errors = 0
        skipped = 0

        logger.info(f"Scheduled validation: Starting batch of {len(songs_to_validate)} songs")

        for song in songs_to_validate:
            processed += 1

            # Skip if PENDING MBID
            if song['artist_mbid'] and song['artist_mbid'].startswith('PENDING-'):
                mark_song_validated(db, song['id'], success=False, error_message='PENDING MBID')
                skipped += 1
                continue

            try:
                # Validate recording - returns tuple (found: bool, method: str)
                found, method = validate_recording_with_fallback(
                    artist_name=song['artist_name'],
                    song_title=song['song_title'],
                    artist_mbid=song['artist_mbid']
                )

                if found:
                    updated += 1
                    mark_song_validated(db, song['id'], success=True, method=method)
                    logger.debug(f"Validated song {song['id']} ({song['artist_name']} - {song['song_title']}) using method: {method}")
                else:
                    mark_song_validated(db, song['id'], success=False, error_message='No match found', method=method)
                    logger.debug(f"No match found for song {song['id']} ({song['artist_name']} - {song['song_title']})")

                # Rate limiting: small delay between requests to avoid 503 errors
                time.sleep(0.2)

            except Exception as e:
                logger.error(f"Error validating song {song['id']}: {e}")
                mark_song_validated(db, song['id'], success=False, error_message=str(e))
                errors += 1

        result = {
            'success': True,
            'processed': processed,
            'updated': updated,
            'errors': errors,
            'skipped': skipped,
            'message': f'Validated {processed} songs: {updated} found, {errors} errors, {skipped} skipped'
        }

        logger.info(f"Scheduled validation complete: {result['message']}")
        return result

    except Exception as e:
        logger.error(f"Error in scheduled validation: {e}")
        return {
            'success': False,
            'error': str(e)
        }
