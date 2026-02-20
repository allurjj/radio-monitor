"""
MBID Overrides routes for Radio Monitor GUI

Provides API endpoints for managing manual MBID overrides:
- Check if artist has override
- Validate MBID before saving
- Create/update override
- Delete override

Note: The MBID editing UI is now integrated directly into the Artists page.
These API endpoints support that functionality.
"""

import logging
import re
from flask import Blueprint, request, jsonify, current_app
from radio_monitor.auth import requires_auth
from radio_monitor.database.crud import (
    add_manual_mbid_override,
    get_manual_mbid_override,
    delete_manual_mbid_override,
)
from radio_monitor.mbid import verify_mbid_exists

logger = logging.getLogger(__name__)

mbid_overrides_bp = Blueprint('mbid_overrides', __name__)


def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')


# ============================================================================
# CHECK OVERRIDE BY ARTIST NAME
# ============================================================================

@mbid_overrides_bp.route('/api/mbid-overrides/check')
@requires_auth
def check_override():
    """Check if an artist has a manual MBID override."""
    artist_name = request.args.get('artist_name', '').strip()

    if not artist_name:
        return jsonify({'error': 'artist_name required'}), 400

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()

    try:
        mbid = get_manual_mbid_override(cursor, artist_name)

        if mbid:
            return jsonify({
                'has_override': True,
                'mbid': mbid,
                'artist_name': artist_name
            })
        else:
            return jsonify({
                'has_override': False,
                'artist_name': artist_name
            })
    finally:
        cursor.close()


# ============================================================================
# VALIDATE MBID
# ============================================================================

@mbid_overrides_bp.route('/api/mbid-overrides/validate', methods=['POST'])
@requires_auth
def validate_mbid():
    """Validate an MBID before saving.

    Checks:
    1. UUID format
    2. Exists on MusicBrainz
    3. Artist name match
    4. Already in database
    """
    data = request.get_json()
    mbid = data.get('mbid', '').strip()
    artist_name = data.get('artist_name', '').strip()

    if not mbid or not artist_name:
        return jsonify({'error': 'mbid and artist_name required'}), 400

    issues = []
    warnings = []

    # Check 1: UUID format
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    if not re.match(uuid_pattern, mbid.lower()):
        issues.append({
            'type': 'format',
            'message': 'Invalid UUID format. Expected format: 8-4-4-4-12 hexadecimal characters'
        })

    # Check 2: Exists on MusicBrainz
    mbid_exists = False
    mbid_artist_name = None

    if len(issues) == 0:  # Only check if format is valid
        try:
            mbid_exists, mbid_artist_name = verify_mbid_exists(mbid)
        except Exception as e:
            logger.warning(f"MusicBrainz API error during validation: {e}")
            issues.append({
                'type': 'api_error',
                'message': f'Cannot verify MBID with MusicBrainz: {str(e)}'
            })

    if not mbid_exists and len(issues) == 0:
        warnings.append({
            'type': 'not_found',
            'message': 'This MBID was not found on MusicBrainz. It may be a private entry or a typo.'
        })

    # Check 3: Artist name match
    if mbid_artist_name:
        # Case-insensitive comparison
        if artist_name.lower() != mbid_artist_name.lower():
            warnings.append({
                'type': 'name_mismatch',
                'message': f'MusicBrainz reports this MBID is for "{mbid_artist_name}", but you are editing "{artist_name}"',
                'mbid_artist': mbid_artist_name
            })

    # Check 4: Already in database
    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()

    try:
        cursor.execute("SELECT name FROM artists WHERE mbid = ?", (mbid,))
        existing = cursor.fetchone()

        if existing:
            existing_name = existing[0]
            if existing_name.lower() != artist_name.lower():
                issues.append({
                    'type': 'duplicate',
                    'message': f'This MBID is already used by "{existing_name}" in your database',
                    'existing_artist': existing_name
                })
    finally:
        cursor.close()

    return jsonify({
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'mbid_exists_on_musicbrainz': mbid_exists,
        'mbid_artist_name': mbid_artist_name
    })


# ============================================================================
# CREATE/UPDATE OVERRIDE
# ============================================================================

@mbid_overrides_bp.route('/api/mbid-overrides', methods=['POST'])
@requires_auth
def save_override():
    """Create or update a manual MBID override."""
    data = request.get_json()
    artist_name = data.get('artist_name', '').strip()
    mbid = data.get('mbid', '').strip()
    notes = data.get('notes', '').strip() or None

    if not artist_name or not mbid:
        return jsonify({'error': 'artist_name and mbid required'}), 400

    # Check for PENDING prefix
    if mbid.upper().startswith('PENDING-'):
        return jsonify({
            'error': 'PENDING is reserved for system use. You cannot manually set MBIDs to PENDING-xxx'
        }), 400

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()

    try:
        override_id = add_manual_mbid_override(cursor, artist_name, mbid, notes)
        db.conn.commit()

        logger.info(f"Manual MBID override saved: '{artist_name}' → {mbid}")

        return jsonify({
            'success': True,
            'id': override_id,
            'artist_name': artist_name,
            'mbid': mbid,
            'message': f'MBID override saved for "{artist_name}"'
        })
    except Exception as e:
        db.conn.rollback()
        logger.error(f"Error saving MBID override: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


# ============================================================================
# DELETE OVERRIDE
# ============================================================================

@mbid_overrides_bp.route('/api/mbid-overrides', methods=['DELETE'])
@requires_auth
def remove_override():
    """Delete a manual MBID override."""
    data = request.get_json()
    artist_name = data.get('artist_name', '').strip()

    if not artist_name:
        return jsonify({'error': 'artist_name required'}), 400

    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()

    try:
        deleted = delete_manual_mbid_override(cursor, artist_name)

        if not deleted:
            return jsonify({'error': 'Override not found'}), 404

        db.conn.commit()

        logger.info(f"Manual MBID override deleted: '{artist_name}'")

        return jsonify({
            'success': True,
            'message': f'Override deleted for "{artist_name}"'
        })
    except Exception as e:
        db.conn.rollback()
        logger.error(f"Error deleting MBID override: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
