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

                # Check if correct artist already exists
                cursor.execute("""
                    SELECT mbid FROM artists WHERE LOWER(name) = ?
                """, (correct_name.lower(),))
                correct_artist_row = cursor.fetchone()

                # Get the correct MBID to use (either from existing artist or from bad artist)
                correct_mbid = None
                if correct_artist_row:
                    correct_mbid = correct_artist_row[0]
                else:
                    # Get MBID from bad artist to carry over
                    cursor.execute("""
                        SELECT mbid FROM artists WHERE LOWER(name) = ?
                    """, (bad_name,))
                    bad_artist_row = cursor.fetchone()
                    if bad_artist_row:
                        correct_mbid = bad_artist_row[0]

                # Handle potential duplicate songs (same MBID + song_title)
                if correct_mbid and correct_artist_row:
                    # Find songs that would become duplicates
                    cursor.execute("""
                        SELECT s1.id as bad_id, s1.song_title, s1.play_count as bad_plays,
                               s2.id as good_id, s2.play_count as good_plays
                        FROM songs s1
                        JOIN songs s2 ON s1.song_title = s2.song_title
                        WHERE LOWER(s1.artist_name) = ? AND s2.artist_mbid = ?
                    """, (bad_name, correct_mbid))

                    duplicates = cursor.fetchall()

                    # For each duplicate, add play counts and delete the bad one
                    for dup in duplicates:
                        bad_id, song_title, bad_plays, good_id, good_plays = dup
                        logger.info(f"Found duplicate song: {song_title} (bad_id={bad_id}, good_id={good_id})")

                        # Add play counts from bad song to good song
                        new_plays = good_plays + bad_plays
                        cursor.execute("""
                            UPDATE songs SET play_count = ? WHERE id = ?
                        """, (new_plays, good_id))

                        # Delete the bad song (will be skipped in the main update)
                        cursor.execute("""
                            DELETE FROM songs WHERE id = ?
                        """, (bad_id,))

                        logger.info(f"Merged play counts: {good_plays} + {bad_plays} = {new_plays} for song {song_title}")

                # Update songs table FIRST (before touching artists table due to FK constraint)
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

                # Now handle artists table (after songs are updated)
                if correct_artist_row:
                    # Correct artist exists - delete the bad one (merge)
                    cursor.execute("""
                        DELETE FROM artists WHERE LOWER(name) = ?
                    """, (bad_name,))
                else:
                    # Correct artist doesn't exist - update the bad one
                    cursor.execute("""
                        UPDATE artists
                        SET name = ?
                        WHERE LOWER(name) = ?
                    """, (correct_name, bad_name))

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
            if song['artist_mbid'].startswith('PENDING-'):
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
                    mark_song_validated(db, song['id'], success=True)
                    logger.debug(f"Validated song {song['id']} ({song['artist_name']} - {song['song_title']}) using method: {method}")
                else:
                    mark_song_validated(db, song['id'], success=False, error_message='No match found')
                    logger.debug(f"No match found for song {song['id']} ({song['artist_name']} - {song['song_title']})")

                # Rate limiting: small delay between requests to avoid 503 errors
                time.sleep(0.2)

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


@data_quality_bp.route('/api/data-quality/messy-titles')
@requires_auth
def api_messy_titles():
    """Get list of songs with messy titles

    Query params:
        limit: Maximum results (default: 100)

    Returns JSON:
        {
            "success": true,
            "songs": [...]
        }
    """
    from radio_monitor.data_quality import get_messy_titles

    db = get_db()
    limit = request.args.get('limit', 100, type=int)

    try:
        messy_titles = get_messy_titles(db, limit=limit)
        return jsonify({
            'success': True,
            'songs': messy_titles
        })
    except Exception as e:
        logger.error(f"Error getting messy titles: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
