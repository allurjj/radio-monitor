"""
Data Quality Management Blueprint

Provides web interface for:
- Viewing data quality issues
- Running health checks
- Applying fixes
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

                # Update artists table
                cursor.execute("""
                    UPDATE artists
                    SET name = ?
                    WHERE LOWER(name) = ?
                """, (correct_name, bad_name))

                # Update songs table
                cursor.execute("""
                    UPDATE songs
                    SET artist_name = ?
                    WHERE LOWER(artist_name) = ?
                """, (correct_name, bad_name))

                fixes_applied.append({
                    'from': bad_name,
                    'to': correct_name,
                    'count': count
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
