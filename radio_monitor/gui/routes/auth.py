"""
Authentication routes for Radio Monitor GUI

Provides:
- GET /api/auth/status - Check if auth enabled
- GET /auth/setup - Show setup page (first time)
- POST /api/auth/setup - Create initial credentials
- POST /api/auth/change-password - Change password
- POST /api/auth/disable - Disable authentication
"""

import logging
from flask import Blueprint, request, jsonify, render_template, redirect, url_for

from radio_monitor.gui import is_first_run
from radio_monitor.gui import load_settings, save_settings_to_file
from radio_monitor.auth import (
    is_auth_enabled,
    load_auth_config,
    save_auth_config,
    hash_password,
    verify_password,
    verify_auth,
    requires_auth,
    AUTH_FILE
)

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/auth/setup')
def setup_page():
    """Authentication setup page

    Only accessible if auth file doesn't exist
    """
    # Redirect to wizard if first run
    if is_first_run():
        return redirect(url_for('wizard.index'))

    # If auth already enabled, redirect to dashboard
    if is_auth_enabled():
        return redirect(url_for('dashboard.index'))

    return render_template('auth_setup.html')


@auth_bp.route('/api/auth/status')
def api_auth_status():
    """Check authentication status

    Returns JSON:
        {
            "enabled": true/false,
            "username": "admin" (if enabled)
        }
    """
    try:
        if not is_auth_enabled():
            return jsonify({
                'enabled': False,
                'username': None
            })

        config = load_auth_config()
        if not config:
            return jsonify({
                'enabled': False,
                'username': None
            })

        return jsonify({
            'enabled': True,
            'username': config.get('username')
        })

    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return jsonify({
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/setup', methods=['POST'])
def api_auth_setup():
    """Create initial authentication credentials

    Expects JSON:
        {
            "username": "admin",
            "password": "secure_password"
        }

    Returns JSON:
        {
            "success": true,
            "message": "Authentication enabled"
        }
    """
    try:
        # Validate auth not already enabled
        if is_auth_enabled():
            return jsonify({
                'success': False,
                'message': 'Authentication already enabled. Use change-password endpoint instead.'
            }), 400

        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        # Validate
        if not username:
            return jsonify({
                'success': False,
                'message': 'Username is required'
            }), 400

        if len(username) < 3:
            return jsonify({
                'success': False,
                'message': 'Username must be at least 3 characters'
            }), 400

        if not password:
            return jsonify({
                'success': False,
                'message': 'Password is required'
            }), 400

        if len(password) < 8:
            return jsonify({
                'success': False,
                'message': 'Password must be at least 8 characters'
            }), 400

        # Hash password and save
        password_hash = hash_password(password)

        if save_auth_config(username, password_hash):
            logger.info(f"Authentication enabled for user: {username}")
            return jsonify({
                'success': True,
                'message': 'Authentication enabled successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Error saving authentication configuration'
            }), 500

    except Exception as e:
        logger.error(f"Error setting up authentication: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@auth_bp.route('/api/auth/change-password', methods=['POST'])
@requires_auth
def api_auth_change_password():
    """Change password (requires authentication)

    Expects JSON:
        {
            "current_password": "old_password",
            "new_password": "new_secure_password"
        }

    Returns JSON:
        {
            "success": true,
            "message": "Password changed successfully"
        }
    """
    try:
        # Validate auth is enabled
        if not is_auth_enabled():
            return jsonify({
                'success': False,
                'message': 'Authentication not enabled'
            }), 400

        data = request.json
        current_password = data.get('current_password', '').strip()
        new_password = data.get('new_password', '').strip()

        # Validate
        if not current_password or not new_password:
            return jsonify({
                'success': False,
                'message': 'Current and new passwords are required'
            }), 400

        if len(new_password) < 8:
            return jsonify({
                'success': False,
                'message': 'New password must be at least 8 characters'
            }), 400

        # Load current config
        config = load_auth_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error loading authentication configuration'
            }), 500

        # Verify current password
        stored_hash = config.get('password_hash')
        if not verify_password(current_password, stored_hash):
            return jsonify({
                'success': False,
                'message': 'Current password is incorrect'
            }), 401

        # Update password
        new_password_hash = hash_password(new_password)
        username = config.get('username')

        if save_auth_config(username, new_password_hash):
            logger.info(f"Password changed for user: {username}")
            return jsonify({
                'success': True,
                'message': 'Password changed successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Error saving new password'
            }), 500

    except Exception as e:
        logger.error(f"Error changing password: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@auth_bp.route('/api/auth/disable', methods=['POST'])
@requires_auth
def api_auth_disable():
    """Disable authentication (requires authentication)

    Deletes auth file and returns to unauthenticated mode

    Returns JSON:
        {
            "success": true,
            "message": "Authentication disabled"
        }
    """
    try:
        import os

        if not is_auth_enabled():
            return jsonify({
                'success': False,
                'message': 'Authentication not enabled'
            }), 400

        # Delete auth file
        try:
            os.remove(AUTH_FILE)
            logger.info("Authentication disabled (auth file deleted)")
            return jsonify({
                'success': True,
                'message': 'Authentication disabled successfully'
            })
        except FileNotFoundError:
            return jsonify({
                'success': False,
                'message': 'Authentication file not found'
            }), 404

    except Exception as e:
        logger.error(f"Error disabling authentication: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
