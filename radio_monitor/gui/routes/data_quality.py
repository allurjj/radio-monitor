"""
Data Quality Management Blueprint

Provides web interface for:
- Viewing data quality issues
- Running health checks
- Applying fixes
- Batch recording validation
"""

import logging
import shutil
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, current_app
from radio_monitor.auth import requires_auth
from radio_monitor.normalization import ARTIST_NAME_CORRECTIONS

logger = logging.getLogger(__name__)

data_quality_bp = Blueprint('data_quality', __name__)


def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')


@data_quality_bp.route('/data-quality')
@requires_auth
def data_quality_page():
    """Data quality management page"""
    db = get_db()

    from radio_monitor.data_quality import run_health_check
    issues = run_health_check(db)

    return render_template('data_quality.html', issues=issues)


@data_quality_bp.route('/api/data-quality/health')
@requires_auth
def api_health_check():
    """API endpoint for health check

    Returns JSON with health check results
    """
    db = get_db()

    from radio_monitor.data_quality import run_health_check
    issues = run_health_check(db)

    return jsonify({
        'success': True,
        'issues': issues
    })


@data_quality_bp.route('/api/data-quality/fix-artist-names', methods=['POST'])
@requires_auth
def api_fix_artist_names():
    """API endpoint to fix artist names

    Handles artist name corrections with merge logic:
    - If correct artist already exists, merge the bad one into it
    - If correct artist doesn't exist, update the bad one

    Expects JSON body:
        {
            "backup": true  // Whether to create backup before fixing
        }

    Returns JSON:
        {
            "success": true,
            "fixes_applied": [...],
            "backup": "backup_path"
        }
    """
    db = get_db()
    settings = current_app.config.get('settings', {})

    # Get request data
    data = request.get_json() or {}
    create_backup = data.get('backup', False)

    # Create backup if requested
    backup_path = None
    if create_backup:
        db_file = settings.get('monitor', {}).get('database_file', 'radio_songs.db')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f'{db_file}.backup_{timestamp}'
        try:
            shutil.copy2(db_file, backup_path)
            logger.info(f"Backup created: {backup_path}")
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return jsonify({
                'success': False,
                'error': f'Failed to create backup: {str(e)}'
            }), 500

    # Apply fixes
    cursor = db.get_cursor()
    fixes_applied = []

    try:
        for bad_name, correct_name in ARTIST_NAME_CORRECTIONS.items():
            # Find affected songs
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM songs
                WHERE LOWER(artist_name) = ?
            """, (bad_name,))

            result = cursor.fetchone()
            if result and result[0] > 0:
                count = result[0]
                logger.info(f"Processing: '{bad_name}' -> '{correct_name}' ({count} songs)")

                # Check if correct artist already exists
                cursor.execute("""
                    SELECT mbid FROM artists WHERE LOWER(name) = ?
                """, (correct_name.lower(),))
                correct_artist_row = cursor.fetchone()

                # Get the bad artist's MBID
                cursor.execute("""
                    SELECT mbid FROM artists WHERE LOWER(name) = ?
                """, (bad_name,))
                bad_artist_row = cursor.fetchone()
                bad_artist_mbid = bad_artist_row[0] if bad_artist_row else None

                # Determine which MBID to use
                if correct_artist_row:
                    correct_mbid = correct_artist_row[0]
                    logger.info(f"Using existing artist MBID: {correct_mbid}")
                elif bad_artist_mbid:
                    correct_mbid = bad_artist_mbid
                    logger.info(f"Carrying over bad artist MBID: {correct_mbid}")
                else:
                    correct_mbid = None
                    logger.warning(f"No MBID found for either artist")

                # Step 1: Handle duplicate songs (if merging with existing artist)
                if correct_mbid and correct_artist_row:
                    # Find songs that would become duplicates (same song title, different artist MBIDs)
                    cursor.execute("""
                        SELECT s1.id as bad_id, s1.song_title, s1.play_count as bad_plays,
                               s2.id as good_id, s2.play_count as good_plays
                        FROM songs s1
                        JOIN songs s2 ON s1.song_title = s2.song_title AND s1.id != s2.id
                        WHERE LOWER(s1.artist_name) = ? AND s2.artist_mbid = ?
                    """, (bad_name, correct_mbid))

                    duplicates = cursor.fetchall()
                    logger.info(f"Found {len(duplicates)} duplicate songs to merge")

                    for dup in duplicates:
                        bad_id, song_title, bad_plays, good_id, good_plays = dup
                        logger.info(f"Merging duplicate: {song_title} (id {bad_id} -> {good_id})")

                        # Add play counts from bad song to good song
                        new_plays = good_plays + bad_plays
                        cursor.execute("UPDATE songs SET play_count = ? WHERE id = ?", (new_plays, good_id))

                        # Delete song_plays_daily entries for the bad song (must do this first due to FK constraint)
                        cursor.execute("DELETE FROM song_plays_daily WHERE song_id = ?", (bad_id,))
                        logger.info(f"Deleted {cursor.rowcount} play records for song {bad_id}")

                        # Delete the bad song
                        cursor.execute("DELETE FROM songs WHERE id = ?", (bad_id,))
                        logger.info(f"Deleted duplicate song {bad_id}")

                # Step 2: Update remaining songs to use correct artist name and MBID
                if correct_mbid:
                    cursor.execute("""
                        UPDATE songs
                        SET artist_name = ?, artist_mbid = ?
                        WHERE LOWER(artist_name) = ?
                    """, (correct_name, correct_mbid, bad_name))
                else:
                    cursor.execute("""
                        UPDATE songs
                        SET artist_name = ?
                        WHERE LOWER(artist_name) = ?
                    """, (correct_name, bad_name))

                logger.info(f"Updated {cursor.rowcount} songs")

                # Step 3: Handle blocklist entries
                if correct_mbid:
                    cursor.execute("""
                        UPDATE blocklist
                        SET artist_mbid = ?
                        WHERE LOWER(entity_id) = ? AND entity_type = 'artist'
                    """, (correct_mbid, bad_name.lower()))

                    cursor.execute("""
                        DELETE FROM blocklist WHERE LOWER(entity_id) = ? AND entity_type = 'artist'
                    """, (bad_name.lower(),))

                # Step 4: Handle artists table - ALWAYS update, never delete to avoid FK issues
                # If correct artist exists, just delete the bad one (only if safe)
                # If correct artist doesn't exist, rename the bad one
                if correct_artist_row and bad_artist_mbid:
                    # Try to delete bad artist - if it fails due to FK, we'll just leave it
                    # It should be safe now since we updated all songs
                    try:
                        cursor.execute("DELETE FROM artists WHERE LOWER(name) = ?", (bad_name,))
                        logger.info(f"Deleted bad artist '{bad_name}'")
                    except Exception as e:
                        logger.warning(f"Could not delete bad artist: {e}")
                        # Fallback: just rename it to avoid conflicts
                        cursor.execute("""
                            UPDATE artists
                            SET name = ?
                            WHERE LOWER(name) = ?
                        """, (f"{bad_name} (duplicate)", bad_name,))
                elif not correct_artist_row:
                    # Correct artist doesn't exist - rename the bad one
                    cursor.execute("""
                        UPDATE artists
                        SET name = ?
                        WHERE LOWER(name) = ?
                    """, (correct_name, bad_name))
                    logger.info(f"Renamed artist '{bad_name}' to '{correct_name}'")

                fixes_applied.append({
                    'from': bad_name,
                    'to': correct_name,
                    'count': count,
                    'action': 'merged' if correct_artist_row else 'updated'
                })

        db.conn.commit()

        return jsonify({
            'success': True,
            'fixes_applied': fixes_applied,
            'backup': backup_path
        })
    except Exception as e:
        db.conn.rollback()
        logger.error(f"Error fixing artist names: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        cursor.close()


@data_quality_bp.route('/api/data-quality/validate-batch', methods=['POST'])
@requires_auth
def api_validate_batch():
    """API endpoint to validate a batch of songs

    Expects JSON body:
        {
            "count": 50  // Number of songs to validate
        }

    Returns JSON:
        {
            "success": true,
            "processed": 50,
            "updated": 45,
            "errors": 2,
            "skipped": 3,
            "message": "..."
        }
    """
    import time
    db = get_db()

    data = request.get_json() or {}
    count = data.get('count', 50)

    from radio_monitor.data_quality import get_songs_to_validate, mark_song_validated
    from radio_monitor.recording_validation import validate_recording_with_fallback

    try:
        songs_to_validate = get_songs_to_validate(db, count=count)

        if not songs_to_validate:
            return jsonify({
                'success': True,
                'processed': 0,
                'updated': 0,
                'errors': 0,
                'skipped': 0,
                'message': 'No songs to validate - all songs may already be validated'
            })

        processed = 0
        updated = 0
        errors = 0
        skipped = 0
        last_log_time = time.time()

        for song in songs_to_validate:
            processed += 1

            # Log progress every 5 seconds
            current_time = time.time()
            if current_time - last_log_time >= 5:
                logger.info(f"Validation progress: {processed}/{len(songs_to_validate)} songs processed")
                last_log_time = current_time

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
                    # Successfully validated
                    updated += 1
                    mark_song_validated(db, song['id'], success=True, method=method)
                    logger.debug(f"Validated song {song['id']} ({song['artist_name']} - {song['song_title']}) using method: {method}")
                else:
                    mark_song_validated(db, song['id'], success=False, error_message='No match found', method=method)
                    logger.debug(f"No match found for song {song['id']} ({song['artist_name']} - {song['song_title']})")

                # Rate limiting: delay between requests to avoid MusicBrainz blocking
                # MusicBrainz recommends 1 request per second
                time.sleep(1)

            except Exception as e:
                logger.error(f"Error validating song {song['id']}: {e}")
                mark_song_validated(db, song['id'], success=False, error_message=str(e))
                errors += 1

        logger.info(f"Batch validation complete: {processed} processed, {updated} found, {errors} errors, {skipped} skipped")

        return jsonify({
            'success': True,
            'processed': processed,
            'updated': updated,
            'errors': errors,
            'skipped': skipped,
            'message': f'Validated {processed} songs: {updated} found, {errors} errors, {skipped} skipped'
        })

    except Exception as e:
        logger.error(f"Error in validate_batch: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@data_quality_bp.route('/api/data-quality/bad-artists')
@requires_auth
def api_bad_artists():
    """Get list of songs with bad artist names

    Returns JSON:
        {
            "success": true,
            "artists": [...]
        }
    """
    from radio_monitor.data_quality import get_known_bad_artists

    db = get_db()

    try:
        bad_artists = get_known_bad_artists(db)
        return jsonify({
            'success': True,
            'artists': bad_artists
        })
    except Exception as e:
        logger.error(f"Error getting bad artists: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@data_quality_bp.route('/api/data-quality/unvalidated-songs')
@requires_auth
def api_unvalidated_songs():
    """Get list of songs that are not validated or failed validation

    Query params:
        limit: Maximum results (default: None for all)
        sort_by: Column to sort by (play_count, song_title, artist_name, validation_status)
        sort_dir: Sort direction (ASC or DESC, default: DESC)

    Returns JSON:
        {
            "success": true,
            "songs": [
                {
                    "id": 123,
                    "song_title": "Song Name",
                    "artist_name": "Artist Name",
                    "artist_mbid": "uuid",
                    "validation_status": "unvalidated",
                    "play_count": 15
                },
                ...
            ]
        }
    """
    from radio_monitor.data_quality import get_unvalidated_songs

    db = get_db()
    limit = request.args.get('limit', type=int)
    sort_by = request.args.get('sort_by', 'play_count')
    sort_dir = request.args.get('sort_dir', 'DESC')

    try:
        songs = get_unvalidated_songs(db, limit=limit, sort_by=sort_by, sort_dir=sort_dir)
        return jsonify({
            'success': True,
            'songs': songs
        })
    except Exception as e:
        logger.error(f"Error getting unvalidated songs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@data_quality_bp.route('/api/data-quality/revalidate-invalid', methods=['POST'])
@requires_auth
def api_revalidate_invalid():
    """API endpoint to reset and re-validate invalid songs

    Resets validation_status of invalid songs to unvalidated,
    then re-validates them with the fixed code.

    Returns JSON:
        {
            "success": true,
            "reset_count": 68,
            "validation_results": {...}
        }
    """
    import time
    db = get_db()

    from radio_monitor.data_quality import get_songs_to_validate, mark_song_validated
    from radio_monitor.recording_validation import validate_recording_with_fallback

    cursor = db.get_cursor()

    try:
        # Step 1: Reset invalid songs to unvalidated
        cursor.execute("""
            UPDATE songs
            SET validation_status = 'unvalidated',
                validated_at = NULL,
                validation_method = NULL
            WHERE validation_status = 'invalid'
        """)
        reset_count = cursor.rowcount
        db.conn.commit()
        logger.info(f"Reset {reset_count} invalid songs to unvalidated")

        if reset_count == 0:
            return jsonify({
                'success': True,
                'reset_count': 0,
                'message': 'No invalid songs found to re-validate'
            })

        # Step 2: Get the songs we just reset (they're now unvalidated)
        cursor.execute("""
            SELECT id, artist_name, song_title, artist_mbid
            FROM songs
            WHERE validation_status = 'unvalidated' OR validation_status IS NULL
            ORDER BY id DESC
            LIMIT ?
        """, (reset_count,))

        songs_to_validate = []
        for row in cursor.fetchall():
            songs_to_validate.append({
                'id': row[0],
                'artist_name': row[1],
                'song_title': row[2],
                'artist_mbid': row[3]
            })
        cursor.close()

        processed = 0
        updated = 0
        errors = 0
        skipped = 0

        logger.info(f"Starting re-validation of {len(songs_to_validate)} songs")

        for song in songs_to_validate:
            processed += 1

            # Skip if PENDING MBID
            if song['artist_mbid'] and song['artist_mbid'].startswith('PENDING-'):
                mark_song_validated(db, song['id'], success=False, error_message='PENDING MBID', method='pending')
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
                    logger.info(f"[{processed}/{len(songs_to_validate)}] ✓ Validated: {song['artist_name']} - {song['song_title']} (method: {method})")
                else:
                    mark_song_validated(db, song['id'], success=False, error_message='No match found', method=method)
                    logger.warning(f"[{processed}/{len(songs_to_validate)}] ✗ No match: {song['artist_name']} - {song['song_title']}")

                # Rate limiting: delay between requests to avoid MusicBrainz blocking
                # MusicBrainz recommends 1 request per second
                time.sleep(1)

            except Exception as e:
                logger.error(f"Error validating song {song['id']}: {e}")
                mark_song_validated(db, song['id'], success=False, error_message=str(e), method='error')
                errors += 1

        result = {
            'success': True,
            'reset_count': reset_count,
            'processed': processed,
            'updated': updated,
            'errors': errors,
            'skipped': skipped,
            'message': f'Re-validated {processed} songs: {updated} found (were invalid), {errors} errors, {skipped} skipped'
        }

        logger.info(f"Re-validation complete: {result['message']}")
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in revalidate_invalid: {e}")
        db.conn.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@data_quality_bp.route('/api/data-quality/validate-selected', methods=['POST'])
@requires_auth
def api_validate_selected():
    """API endpoint to validate specific selected songs

    Expects JSON body:
        {
            "song_ids": [1, 2, 3, ...]
        }

    Returns JSON:
        {
            "success": true,
            "processed": 3,
            "updated": 2,
            "errors": 0,
            "skipped": 1,
            "message": "..."
        }
    """
    import time
    db = get_db()

    from radio_monitor.data_quality import mark_song_validated
    from radio_monitor.recording_validation import validate_recording_with_fallback

    data = request.get_json() or {}
    song_ids = data.get('song_ids', [])

    if not song_ids:
        return jsonify({
            'success': False,
            'error': 'No song IDs provided'
        }), 400

    cursor = db.get_cursor()

    try:
        # Get the songs to validate
        placeholders = ','.join('?' * len(song_ids))
        cursor.execute(f"""
            SELECT id, artist_name, song_title, artist_mbid
            FROM songs
            WHERE id IN ({placeholders})
        """, song_ids)

        songs_to_validate = []
        for row in cursor.fetchall():
            songs_to_validate.append({
                'id': row[0],
                'artist_name': row[1],
                'song_title': row[2],
                'artist_mbid': row[3]
            })
        cursor.close()

        processed = 0
        updated = 0
        errors = 0
        skipped = 0

        logger.info(f"Starting validation of {len(songs_to_validate)} selected songs")

        for song in songs_to_validate:
            processed += 1

            # Skip if PENDING MBID
            if song['artist_mbid'] and song['artist_mbid'].startswith('PENDING-'):
                mark_song_validated(db, song['id'], success=False, error_message='PENDING MBID', method='pending')
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
                    logger.info(f"[{processed}/{len(songs_to_validate)}] ✓ Validated: {song['artist_name']} - {song['song_title']} (method: {method})")
                else:
                    mark_song_validated(db, song['id'], success=False, error_message='No match found', method=method)
                    logger.warning(f"[{processed}/{len(songs_to_validate)}] ✗ No match: {song['artist_name']} - {song['song_title']}")

                # Rate limiting: delay between requests to avoid MusicBrainz blocking
                time.sleep(1)

            except Exception as e:
                logger.error(f"Error validating song {song['id']}: {e}")
                mark_song_validated(db, song['id'], success=False, error_message=str(e), method='error')
                errors += 1

        result = {
            'success': True,
            'processed': processed,
            'updated': updated,
            'errors': errors,
            'skipped': skipped,
            'message': f'Validated {processed} selected songs: {updated} found, {errors} errors, {skipped} skipped'
        }

        logger.info(f"Selected validation complete: {result['message']}")
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in validate_selected: {e}")
        db.conn.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
