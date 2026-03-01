"""
Authentication module for Radio Monitor GUI

Provides:
- HTTP Basic Authentication for all web routes
- Password hashing and verification with bcrypt
- User-friendly password reset (delete auth file)
- Login attempt tracking (brute force protection)
"""

import os
import json
import logging
import hashlib
from datetime import datetime, timedelta
from functools import wraps

import bcrypt
from flask import request, Response
from flask_httpauth import HTTPBasicAuth

logger = logging.getLogger(__name__)

# Constants
AUTH_FILE = 'radio_monitor_auth.json'
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 5

# Global variables
auth = HTTPBasicAuth()
failed_attempts = {}  # IP address -> {'attempts': int, 'locked_until': datetime}


def is_auth_enabled():
    """Check if authentication is enabled

    Returns:
        True if auth file exists, False otherwise
    """
    return os.path.exists(AUTH_FILE)


def load_auth_config():
    """Load authentication configuration from JSON file

    Returns:
        dict with 'username' and 'password_hash' keys, or None if file doesn't exist
    """
    if not os.path.exists(AUTH_FILE):
        return None

    try:
        with open(AUTH_FILE, 'r') as f:
            config = json.load(f)
            logger.info(f"Auth config loaded from {AUTH_FILE}")
            return config
    except Exception as e:
        logger.error(f"Error loading auth config: {e}")
        return None


def save_auth_config(username, password_hash):
    """Save authentication configuration to JSON file

    Args:
        username: Username (plain text)
        password_hash: Bcrypt hash of password

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        # Import version dynamically using getter (prefers VERSION.py)
        try:
            from radio_monitor import get_version
            version = get_version()
        except ImportError:
            version = '1.1.0'

        config = {
            'username': username,
            'password_hash': password_hash,
            'created_at': datetime.now().isoformat(),
            'version': version
        }

        with open(AUTH_FILE, 'w') as f:
            json.dump(config, f, indent=2)

        logger.info(f"Auth config saved to {AUTH_FILE}")
        return True
    except Exception as e:
        logger.error(f"Error saving auth config: {e}")
        return False


def hash_password(password):
    """Hash a password using bcrypt

    Args:
        password: Plain text password

    Returns:
        Bcrypt hash string
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password, hashed):
    """Verify a password against a bcrypt hash

    Args:
        password: Plain text password to verify
        hashed: Bcrypt hash to verify against

    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False


def is_ip_locked(ip_address):
    """Check if IP address is locked due to too many failed attempts

    Args:
        ip_address: Client IP address

    Returns:
        True if locked, False otherwise
    """
    if ip_address not in failed_attempts:
        return False

    attempt_data = failed_attempts[ip_address]

    # Check if lockout has expired
    if attempt_data.get('locked_until'):
        locked_until = attempt_data['locked_until']
        if datetime.now() < locked_until:
            return True  # Still locked
        else:
            # Lockout expired, clear attempts
            del failed_attempts[ip_address]
            return False

    return False


def record_failed_attempt(ip_address):
    """Record a failed login attempt and lock out if necessary

    Args:
        ip_address: Client IP address

    Returns:
        True if IP is now locked, False otherwise
    """
    now = datetime.now()

    if ip_address not in failed_attempts:
        failed_attempts[ip_address] = {'attempts': 0}

    attempt_data = failed_attempts[ip_address]
    attempt_data['attempts'] = attempt_data.get('attempts', 0) + 1
    attempt_data['last_attempt'] = now.isoformat()

    # Check if should lock out
    if attempt_data['attempts'] >= MAX_LOGIN_ATTEMPTS:
        # Lock out for specified duration
        locked_until = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        attempt_data['locked_until'] = locked_until.isoformat()
        failed_attempts[ip_address] = attempt_data

        logger.warning(f"IP {ip_address} locked out until {locked_until} "
                     f"({attempt_data['attempts']} failed attempts)")
        return True

    logger.warning(f"Failed login attempt from {ip_address} "
                  f"({attempt_data['attempts']}/{MAX_LOGIN_ATTEMPTS})")
    return False


def clear_failed_attempts(ip_address):
    """Clear failed login attempts for IP address (successful login)

    Args:
        ip_address: Client IP address
    """
    if ip_address in failed_attempts:
        del failed_attempts[ip_address]


@auth.verify_password
def verify_auth(username, password):
    """Flask-HTTPAuth password verifier

    Called automatically on every authenticated request

    Returns:
        True if credentials valid, False otherwise
    """
    # Check if auth is enabled
    if not is_auth_enabled():
        # No auth file, no authentication required
        return True

    # Check IP lockout
    ip_address = request.remote_addr
    if is_ip_locked(ip_address):
        logger.warning(f"Locked out IP attempted login: {ip_address}")
        return False

    # Load auth config
    config = load_auth_config()
    if not config:
        return True  # No config = no auth

    # Verify credentials
    stored_username = config.get('username')
    stored_hash = config.get('password_hash')

    if username == stored_username and verify_password(password, stored_hash):
        # Success - clear failed attempts
        clear_failed_attempts(ip_address)
        logger.info(f"Successful login for {username} from {ip_address}")
        return True
    else:
        # Failure - record attempt
        record_failed_attempt(ip_address)
        return False


@auth.error_handler
def auth_error():
    """Handle authentication errors

    Returns:
        Flask response with 401 Unauthorized
    """
    ip_address = request.remote_addr

    # Check if IP is locked
    if is_ip_locked(ip_address):
        locked_until = failed_attempts[ip_address]['locked_until']
        return Response(
            f'Too many failed login attempts. Account locked until {locked_until}. '
            f'Delete {AUTH_FILE} to reset.',
            401,
            {'WWW-Authenticate': 'Basic realm="Locked Out"'}
        )

    # Standard auth required
    return Response(
        'Authentication required. Delete ' + AUTH_FILE + ' to reset password.',
        401,
        {'WWW-Authenticate': 'Basic realm="Radio Monitor"'}
    )


def requires_auth(f):
    """Decorator to require authentication for a route

    Only enforces auth if auth file exists

    Usage:
        @app.route('/api/example')
        @requires_auth
        def example():
            return jsonify({'data': 'protected'})

    Args:
        f: Flask route function

    Returns:
        Decorated function
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # If auth enabled, use HTTPBasicAuth
        if is_auth_enabled():
            return auth.login_required(lambda *a, **kw: f(*a, **kw))(*args, **kwargs)
        else:
            # Auth not enabled, proceed normally
            return f(*args, **kwargs)

    return decorated
