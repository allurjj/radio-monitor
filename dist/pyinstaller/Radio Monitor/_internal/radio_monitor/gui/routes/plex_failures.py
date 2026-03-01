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
    valid_columns = ['failure_date', 'song_title', 'artist_name', 'failure_reason', 'search_attempts']
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

    Actually attempts to find the song in Plex library.
    If found: Deletes failure record
    If not found: Updates last_attempt_at timestamp, increments search_attempts
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
        plex_url = settings.get('plex_url')
        plex_token = settings.get('plex_token')

        if not plex_url or not plex_token:
            return jsonify({'error': 'Plex not configured. Please configure Plex in Settings first.'}), 400

        # Connect to Plex
        try:
            from plexapi.server import PlexServer
            plex = PlexServer(plex_url, plex_token)
            music_library = plex.library.section(settings.get('music_library_name', 'Music'))
        except Exception as e:
            logger.error(f"Plex connection failed during retry: {e}")
            return jsonify({'error': f'Plex connection failed: {str(e)}'}), 500

        # Retry the match
        from radio_monitor.plex import find_song_in_library
        song_title = failure['song']['song_title']
        artist_name = failure['song']['artist_name']

        track = find_song_in_library(music_library, song_title, artist_name)

        if track:
            # SUCCESS: Song found in Plex - delete failure record
            cursor.execute("DELETE FROM plex_match_failures WHERE id = ?", (failure_id,))
            db.conn.commit()

            # Log activity
            from radio_monitor.database import activity
            activity.log_activity(
                cursor,
                event_type='plex_failure_retry_success',
                title='Plex Match Retry Successful',
                description=f'Found: {song_title} - {artist_name}',
                metadata={
                    'failure_id': failure_id,
                    'song_id': failure['song_id'],
                    'song_title': song_title,
                    'artist_name': artist_name
                },
                severity='success',
                source='user'
            )
            db.conn.commit()

            return jsonify({
                'success': True,
                'found': True,
                'message': f'Found: {song_title} - {artist_name}'
            })
        else:
            # FAILURE: Still not found - update timestamp and attempts
            # Use local time for failure_date timestamp
            now = datetime.now()
            cursor.execute("""
                UPDATE plex_match_failures
                SET search_attempts = search_attempts + 1,
                    failure_date = ?
                WHERE id = ?
            """, (now, failure_id,))
            db.conn.commit()

            return jsonify({
                'success': True,
                'found': False,
                'message': f'Still not found: {song_title} - {artist_name}. Retry after fixing metadata or adding music to Plex.'
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
