"""
Plex Failures routes for Radio Monitor 1.0 GUI

This module handles all Plex failure tracking GUI operations:
- List view with filtering and pagination
- Failure details
- Mark as resolved
- Export to CSV
- Failure statistics
"""

import logging
from flask import Blueprint, render_template, jsonify, request, send_file, current_app
from radio_monitor.auth import requires_auth
from io import StringIO
import csv
from datetime import datetime

logger = logging.getLogger(__name__)

# Create blueprint
plex_failures_bp = Blueprint('plex_failures', __name__, url_prefix='/plex-failures')


@plex_failures_bp.route('/')
@requires_auth
def list_failures():
    """Render Plex failures list page"""
    return render_template('plex_failures.html')


@plex_failures_bp.route('/api/failures')
@requires_auth
def api_get_failures():
    """Get Plex failures with filtering and pagination

    Query params:
        - resolved: Filter by resolved status (all, true, false)
        - reason: Filter by failure reason
        - limit: Items per page (default 50)
        - offset: Pagination offset
        - sort: Sort column (failure_date, song_title, artist_name, failure_reason, search_attempts)
        - direction: Sort direction (asc, desc)
    """
    db = current_app.config.get('db')
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    resolved_param = request.args.get('resolved', 'all')
    failure_reason = request.args.get('reason')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    sort = request.args.get('sort', 'failure_date')
    direction = request.args.get('direction', 'desc')

    # Validate direction
    if direction not in ['asc', 'desc']:
        direction = 'desc'

    # Validate sort column
    valid_columns = ['failure_date', 'song_title', 'artist_name', 'retry_match_succeeded']
    if sort not in valid_columns:
        sort = 'failure_date'

    # Convert resolved parameter
    resolved = None
    if resolved_param == 'true':
        resolved = True
    elif resolved_param == 'false':
        resolved = False

    cursor = db.get_cursor()
    try:
        from radio_monitor.database import plex_failures

        failures = plex_failures.get_failures(
            cursor,
            limit=limit,
            offset=offset,
            resolved=resolved,
            failure_reason=failure_reason,
            sort=sort,
            direction=direction
        )

        total = plex_failures.get_failure_count(
            cursor,
            resolved=resolved,
            failure_reason=failure_reason
        )

        return jsonify({
            'failures': failures,
            'total': total,
            'limit': limit,
            'offset': offset
        })
    finally:
        cursor.close()


@plex_failures_bp.route('/api/failures/<int:failure_id>')
@requires_auth
def api_get_failure(failure_id):
    """Get details of a specific failure"""
    db = current_app.config.get('db')
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()
    try:
        from radio_monitor.database import plex_failures

        failure = plex_failures.get_failure_by_id(cursor, failure_id)
        if not failure:
            return jsonify({'error': 'Failure not found'}), 404

        return jsonify(failure)
    finally:
        cursor.close()


@plex_failures_bp.route('/api/failures/<int:failure_id>/dismiss', methods=['POST'])
@requires_auth
def api_dismiss_failure(failure_id):
    """Delete a specific failure record (dismiss)"""
    db = current_app.config.get('db')
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()
    try:
        from radio_monitor.database import plex_failures

        # Delete the failure record
        cursor.execute("DELETE FROM plex_match_failures WHERE id = ?", (failure_id,))
        db.conn.commit()

        if cursor.rowcount > 0:
            # Log activity
            from radio_monitor.database import activity
            activity.log_activity(
                cursor,
                event_type='plex_failure_dismissed',
                title='Plex Failure Dismissed',
                description=f'Dismissed failure ID {failure_id}',
                metadata={'failure_id': failure_id},
                severity='info',
                source='user'
            )
            db.conn.commit()

            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failure not found'}), 404
    finally:
        cursor.close()


@plex_failures_bp.route('/api/failures/<int:failure_id>/retry', methods=['POST'])
@requires_auth
def api_retry_failure(failure_id):
    """Retry matching a failed song in Plex

    Uses the full matching pipeline with multiple strategies.
    If found: Sets retry_match_succeeded=TRUE, marks resolved_at, KEEPS record for 7-day history
    If not found: Sets retry_match_succeeded=FALSE, increments search_attempts
    """
    db = current_app.config.get('db')
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()
    try:
        from radio_monitor.database import plex_failures

        failure = plex_failures.get_failure_by_id(cursor, failure_id)
        if not failure:
            return jsonify({'error': 'Failure not found'}), 404

        # Handle orphaned records (song deleted from database)
        if not failure.get('song'):
            return jsonify({'error': 'Song has been deleted from database. Dismiss this failure.'}), 400

        # Get Plex connection
        from radio_monitor.gui import load_settings
        settings = load_settings() or {}
        plex_url = settings.get('plex', {}).get('url')
        plex_token = settings.get('plex', {}).get('token')
        library_name = settings.get('plex', {}).get('music_library_name', 'Music')

        if not plex_url or not plex_token:
            return jsonify({'error': 'Plex not configured. Please configure Plex in Settings first.'}), 400

        # Connect to Plex
        try:
            from plexapi.server import PlexServer
            plex = PlexServer(plex_url, plex_token)
            music_library = plex.library.section(library_name)
        except Exception as e:
            logger.error(f"Plex connection failed during retry: {e}")
            return jsonify({'error': f'Plex connection failed: {str(e)}'}), 500

        # Retry the match using full pipeline
        from radio_monitor.plex import find_song_in_library
        song_title = failure['song']['song_title']
        artist_name = failure['song']['artist_name']

        # Call find_song_in_library with correct arguments
        plex_track = find_song_in_library(
            music_library=music_library,
            song_title=song_title,
            artist_name=artist_name,
            enable_various_artists_fallback=settings.get('plex', {}).get('enable_various_artists_fallback', False)
        )

        if plex_track:
            # SUCCESS: Mark retry as succeeded but KEEP record (for 7-day history)
            now = datetime.now()
            cursor.execute("""
                UPDATE plex_match_failures
                SET retry_match_succeeded = TRUE,
                    resolved = TRUE,
                    resolved_at = ?
                WHERE id = ?
            """, (now, failure_id))
            db.conn.commit()

            # Log activity
            from radio_monitor.database import activity
            activity.log_activity(
                cursor,
                event_type='plex_match_retry_success',
                title='Plex Match Retry Successful',
                description=f'Matched: {song_title} by {artist_name}',
                metadata={
                    'failure_id': failure_id,
                    'song_id': failure['song_id'],
                    'song_title': song_title,
                    'artist_name': artist_name,
                    'plex_track_key': plex_track.key,
                    'plex_track_title': plex_track.title,
                    'plex_artist_title': plex_track.artist().title if plex_track.artist() else None
                },
                severity='success',
                source='user'
            )
            db.conn.commit()

            return jsonify({
                'success': True,
                'found': True,
                'message': f'Matched: {song_title} - {artist_name}',
                'plex_track': {
                    'title': plex_track.title,
                    'artist': plex_track.artist().title if plex_track.artist() else None,
                    'album': plex_track.album().title if plex_track.album() else None,
                    'year': plex_track.year
                }
            })
        else:
            # FAILURE: Mark retry as failed but keep record for later attempts
            now = datetime.now()
            cursor.execute("""
                UPDATE plex_match_failures
                SET search_attempts = search_attempts + 1,
                    retry_match_succeeded = FALSE,
                    failure_date = ?
                WHERE id = ?
            """, (now, failure_id,))
            db.conn.commit()

            return jsonify({
                'success': True,
                'found': False,
                'message': f'Still not found: {song_title} - {artist_name}. Retry after fixing metadata or adding music to Plex.',
                'search_attempts': failure['search_attempts'] + 1,
                'can_retry': True  # User can try again later
            })

    except Exception as e:
        logger.error(f"Error retrying Plex failure: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


@plex_failures_bp.route('/api/failures/stats')
@requires_auth
def api_get_failure_stats():
    """Get failure statistics

    Query params:
        - days: Number of days to look back (default 30)
    """
    db = current_app.config.get('db')
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    days = int(request.args.get('days', 30))

    cursor = db.get_cursor()
    try:
        from radio_monitor.database import plex_failures

        stats = plex_failures.get_failure_stats(cursor, days=days)
        return jsonify(stats)
    finally:
        cursor.close()


@plex_failures_bp.route('/api/failures/export', methods=['POST'])
@requires_auth
def api_export_failures():
    """Export failures to CSV

    Query params:
        - resolved: Filter by resolved status (all, true, false)
        - days: Number of days to include (default 30)
    """
    db = current_app.config.get('db')
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    resolved_param = request.json.get('resolved', 'all')
    days = int(request.json.get('days', 30))

    # Convert resolved parameter
    resolved = None
    if resolved_param == 'true':
        resolved = True
    elif resolved_param == 'false':
        resolved = False

    cursor = db.get_cursor()
    try:
        from radio_monitor.database import plex_failures

        # Create CSV in memory
        output = StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'Failure ID', 'Artist', 'Song Title', 'Failure Date',
            'Failure Reason', 'Search Attempts', 'Search Terms',
            'Resolved', 'Resolved At', 'Playlist'
        ])

        # Get failures
        failures = plex_failures.get_failures(
            cursor,
            limit=10000,  # Large limit for export
            offset=0,
            resolved=resolved
        )

        # Write data
        for failure in failures:
            writer.writerow([
                failure['id'],
                failure['song']['artist_name'] if failure['song'] else '',
                failure['song']['song_title'] if failure['song'] else '',
                failure['failure_date'],
                failure['failure_reason'],
                failure['search_attempts'],
                str(failure['search_terms']) if failure['search_terms'] else '',
                'Yes' if failure['resolved'] else 'No',
                failure['resolved_at'] or '',
                failure['playlist']['name'] if failure.get('playlist') else ''
            ])

        # Log activity
        from radio_monitor.database import activity
        activity.log_activity(
            cursor,
            event_type='plex_failures_export',
            title='Plex Failures Exported',
            description=f'Exported {len(failures)} failures to CSV',
            metadata={'count': len(failures), 'resolved_filter': resolved_param},
            severity='info',
            source='user'
        )
        db.conn.commit()

        # Create file response
        output.seek(0)
        filename = f'plex_failures_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    finally:
        cursor.close()


@plex_failures_bp.route('/api/failures/clear-all', methods=['POST'])
@requires_auth
def api_clear_all_failures():
    """Delete ALL failure records

    Requires confirmation in the request body.
    """
    db = current_app.config.get('db')
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    data = request.get_json()
    confirmed = data.get('confirmed', False)

    if not confirmed:
        return jsonify({'error': 'Confirmation required'}), 400

    cursor = db.get_cursor()
    try:
        # Get count before deleting
        cursor.execute("SELECT COUNT(*) FROM plex_match_failures")
        count = cursor.fetchone()[0]

        # Delete all
        cursor.execute("DELETE FROM plex_match_failures")
        db.conn.commit()

        # Log activity
        from radio_monitor.database import activity
        activity.log_activity(
            cursor,
            event_type='plex_failures_cleared',
            title='All Plex Failures Cleared',
            description=f'Deleted {count} failure records',
            metadata={'count': count},
            severity='warning',
            source='user'
        )
        db.conn.commit()

        return jsonify({
            'success': True,
            'deleted': count
        })
    except Exception as e:
        logger.error(f"Error clearing failures: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


# ==============================================================================
# SpotiFLAC Integration Endpoints
# ==============================================================================

@plex_failures_bp.route('/api/spotiflac/search-spotify', methods=['GET'])
@requires_auth
def api_search_spotify():
    """
    Search Spotify for tracks matching song_title and artist_name

    Query params:
        - song_title: Song title to search for
        - artist_name: Artist name to search for

    Returns:
        List of Spotify tracks with URLs
    """
    song_title = request.args.get('song_title')
    artist_name = request.args.get('artist_name')

    if not song_title or not artist_name:
        return jsonify({'error': 'song_title and artist_name are required'}), 400

    try:
        from radio_monitor.integrations.spotiflac_service import SpotiFLACService
        from radio_monitor.gui import load_settings

        settings = load_settings() or {}
        service = SpotiFLACService(settings)

        results = service.search_spotify(song_title, artist_name)

        return jsonify({
            'results': results,
            'count': len(results)
        })
    except Exception as e:
        logger.error(f"Error searching Spotify: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@plex_failures_bp.route('/api/spotiflac/download', methods=['POST'])
@requires_auth
def api_start_spotiflac_download():
    """
    Start a SpotiFLAC download job

    JSON body:
        - plex_failure_id: ID of the Plex failure record
        - spotify_url: Spotify track/album URL
        - services: List of services to try (optional)

    Returns:
        Job information with status
    """
    data = request.json
    plex_failure_id = data.get('plex_failure_id')
    spotify_url = data.get('spotify_url')
    services = data.get('services', ['tidal', 'qobuz', 'amazon'])

    if not plex_failure_id or not spotify_url:
        return jsonify({'error': 'plex_failure_id and spotify_url are required'}), 400

    db = current_app.config.get('db')
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()
    try:
        from radio_monitor.database import plex_failures
        from radio_monitor.integrations.spotiflac_service import SpotiFLACService
        from radio_monitor.gui import load_settings

        # Get failure details
        failure = plex_failures.get_failure_by_id(cursor, plex_failure_id)
        if not failure:
            return jsonify({'error': 'Failure not found'}), 404

        # Get song details
        song = failure.get('song')
        if not song:
            return jsonify({'error': 'Song not found'}), 404

        # Initialize service
        settings = load_settings() or {}
        spotiflac_service = SpotiFLACService(settings)

        # Determine URL type
        url_type = spotiflac_service.get_download_url_type(spotify_url)

        # Perform download
        if url_type == 'track':
            result = spotiflac_service.download_track(
                spotify_url=spotify_url,
                song_title=song['song_title'],
                artist_name=song['artist_name'],
                services=services
            )

            if result['success']:
                # Log SpotiFLAC download to database
                from radio_monitor.database import spotiflac, activity

                download_id = spotiflac.log_download(
                    cursor,
                    plex_match_failure_id=plex_failure_id,
                    song_id=song['id'],
                    song_title=song['song_title'],
                    artist_name=song['artist_name'],
                    album_name=song.get('album_name'),
                    spotify_url=spotify_url,
                    download_status='completed',
                    service_used=result.get('service_used'),
                    file_path=result.get('file_path'),
                    file_size_mb=result.get('file_size_mb'),
                    completed_at=datetime.now()
                )

                # Log activity
                activity.log_activity(
                    cursor,
                    event_type='spotiflac_download_success',
                    title='SpotiFLAC Download Complete',
                    description=f'Downloaded: {song["song_title"]} - {song["artist_name"]}',
                    metadata={
                        'failure_id': plex_failure_id,
                        'song_id': song['id'],
                        'download_id': download_id,
                        'file_path': result['file_path'],
                        'service_used': result['service_used']
                    },
                    severity='success',
                    source='user'
                )
                db.conn.commit()

                return jsonify({
                    'success': True,
                    'job_id': plex_failure_id,
                    'file_path': result['file_path'],
                    'service_used': result['service_used'],
                    'url_type': 'track'
                })
            else:
                # Log failed download to database
                from radio_monitor.database import spotiflac

                spotiflac.log_download(
                    cursor,
                    plex_match_failure_id=plex_failure_id,
                    song_id=song['id'],
                    song_title=song['song_title'],
                    artist_name=song['artist_name'],
                    album_name=song.get('album_name'),
                    spotify_url=spotify_url,
                    download_status='failed',
                    error_message=result.get('error', 'Download failed'),
                    completed_at=datetime.now()
                )
                db.conn.commit()

                return jsonify({
                    'success': False,
                    'error': result.get('error', 'Download failed')
                }), 500

        elif url_type == 'album':
            result = spotiflac_service.download_album(
                spotify_url=spotify_url,
                artist_name=song['artist_name'],
                album_name=song.get('album_name', 'Unknown Album'),
                services=services
            )

            if result['success']:
                # Log activity
                from radio_monitor.database import activity
                activity.log_activity(
                    cursor,
                    event_type='spotiflac_album_download_success',
                    title='SpotiFLAC Album Download Complete',
                    description=f'Downloaded album: {song["artist_name"]}',
                    metadata={
                        'failure_id': plex_failure_id,
                        'song_id': song['id'],
                        'files_count': len(result['files_downloaded']),
                        'service_used': result['service_used']
                    },
                    severity='success',
                    source='user'
                )
                db.conn.commit()

                return jsonify({
                    'success': True,
                    'job_id': plex_failure_id,
                    'files_downloaded': result['files_downloaded'],
                    'service_used': result['service_used'],
                    'url_type': 'album'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': result.get('errors', ['Download failed'])[0]
                }), 500

        else:
            return jsonify({'error': f'Unsupported URL type: {url_type}'}), 400

    except Exception as e:
        logger.error(f"Error starting SpotiFLAC download: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


@plex_failures_bp.route('/api/spotiflac/auto-move', methods=['POST'])
@requires_auth
def api_auto_move_to_lidarr():
    """
    Automatically move downloaded file to Lidarr artist folder

    JSON body:
        - source_file: Path to downloaded file
        - artist_name: Artist name
        - lidarr_path: Lidarr root folder path
        - url_type: 'track' or 'album' (optional)

    Returns:
        Success/failure with destination path
    """
    data = request.json
    source_file = data.get('source_file')
    artist_name = data.get('artist_name')
    lidarr_path = data.get('lidarr_path')
    url_type = data.get('url_type', 'track')

    if not source_file or not artist_name or not lidarr_path:
        return jsonify({'error': 'source_file, artist_name, and lidarr_path are required'}), 400

    try:
        from radio_monitor.integrations.spotiflac_service import SpotiFLACService
        from radio_monitor.gui import load_settings

        settings = load_settings() or {}
        service = SpotiFLACService(settings)

        # Auto-move with configured filename format
        final_path = service.auto_move_to_lidarr_folder(
            source_file=source_file,
            artist_name=artist_name,
            lidarr_path=lidarr_path,
            url_type=url_type
        )

        # Log activity
        db = current_app.config.get('db')
        if db:
            cursor = db.get_cursor()
            try:
                from radio_monitor.database import activity
                activity.log_activity(
                    cursor,
                    event_type='spotiflac_auto_moved',
                    title='SpotiFLAC File Auto-Moved',
                    description=f'Auto-moved downloaded file for {artist_name} to {final_path}',
                    metadata={
                        'source_file': source_file,
                        'destination_path': final_path,
                        'artist_name': artist_name
                    },
                    severity='success',
                    source='system'
                )
                db.conn.commit()
            finally:
                cursor.close()

        return jsonify({
            'success': True,
            'destination_path': final_path,
            'message': f'File moved to {final_path}'
        })
    except Exception as e:
        logger.error(f"Error auto-moving file: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@plex_failures_bp.route('/api/lidarr/artist-path', methods=['GET'])
@requires_auth
def api_get_lidarr_artist_path():
    """
    Get the Lidarr folder path for an artist

    Query params:
        - artist_name: Artist name
        - url_type: 'track' or 'album' (default: 'track')

    Returns:
        Path information with existence check and naming convention
    """
    artist_name = request.args.get('artist_name')
    url_type = request.args.get('url_type', 'track')

    if not artist_name:
        return jsonify({'error': 'artist_name is required'}), 400

    try:
        from radio_monitor.integrations.spotiflac_service import SpotiFLACService
        from radio_monitor.gui import load_settings

        settings = load_settings() or {}
        service = SpotiFLACService(settings)

        result = service.get_lidarr_artist_path(artist_name)

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting Lidarr artist path: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
