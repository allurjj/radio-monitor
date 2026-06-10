"""
Notifications routes for Radio Monitor 1.0 GUI

This module handles all notification management GUI operations:
- List, create, update, delete notifications
- Test notifications
- View notification history
- Notification statistics
"""

import json
import logging
from flask import Blueprint, render_template, jsonify, request, current_app
from radio_monitor.auth import requires_auth

logger = logging.getLogger(__name__)

# Create blueprint
notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')


@notifications_bp.route('/')
@requires_auth
def list_notifications():
    """Render notifications management page"""
    return render_template('notifications.html')


@notifications_bp.route('/api/notifications')
@requires_auth
def api_get_notifications():
    """Get all notification configurations

    Query params:
        - enabled_only: Only return enabled notifications
    """
    db = current_app.config.get('db')
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'

    cursor = db.get_cursor()
    try:
        from radio_monitor.database import notifications as notif_db

        notifications = notif_db.get_all_notifications(cursor, enabled_only=enabled_only)
        return jsonify({'notifications': notifications})
    finally:
        cursor.close()


@notifications_bp.route('/api/notifications/<int:notification_id>')
@requires_auth
def api_get_notification(notification_id):
    """Get a specific notification configuration"""
    db = current_app.config.get('db')
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()
    try:
        from radio_monitor.database import notifications as notif_db

        notification = notif_db.get_notification(cursor, notification_id)
        if not notification:
            return jsonify({'error': 'Notification not found'}), 404

        return jsonify(notification)
    finally:
        cursor.close()


@notifications_bp.route('/api/notifications', methods=['POST'])
@requires_auth
def api_create_notification():
    """Create a new notification configuration

    Request body:
        - notification_type: Type (discord, slack, email, telegram)
        - name: Human-readable name
        - config: Configuration dictionary
        - triggers: List of trigger types
        - enabled: Whether enabled (default true)
    """
    db = current_app.config.get('db')
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    data = request.get_json()

    # Validate required fields
    required_fields = ['notification_type', 'name', 'config', 'triggers']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # Validate notification type (all 17 supported providers)
    valid_types = [
        'discord', 'slack', 'email', 'telegram',
        'gotify', 'ntfy', 'mattermost', 'rocketchat',
        'matrix', 'pushover', 'pushbullet', 'prowl',
        'boxcar', 'mqtt'
    ]
    if data['notification_type'] not in valid_types:
        return jsonify({'error': f'Invalid notification type: {data["notification_type"]}'}), 400

    cursor = db.get_cursor()
    try:
        from radio_monitor.database import notifications as notif_db

        notif_id = notif_db.create_notification(
            cursor,
            data['notification_type'],
            data['name'],
            data['config'],
            data['triggers'],
            data.get('enabled', True)
        )
        db.conn.commit()

        # Log activity
        from radio_monitor.database import activity
        activity.log_activity(
            cursor,
            'notification_created',
            'Notification Created',
            f'Created notification "{data["name"]}" ({data["notification_type"]})',
            {'notification_id': notif_id, 'type': data['notification_type']},
            'success',
            'user'
        )
        db.conn.commit()

        return jsonify({
            'success': True,
            'notification_id': notif_id
        }), 201
    finally:
        cursor.close()


@notifications_bp.route('/api/notifications/<int:notification_id>', methods=['PUT'])
@requires_auth
def api_update_notification(notification_id):
    """Update a notification configuration

    Request body:
        - name: New name
        - enabled: Enable/disable
        - config: New configuration
        - triggers: New triggers list
    """
    db = current_app.config.get('db')
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    data = request.get_json()

    cursor = db.get_cursor()
    try:
        from radio_monitor.database import notifications as notif_db

        success = notif_db.update_notification(cursor, notification_id, **data)
        if not success:
            return jsonify({'error': 'Notification not found'}), 404

        db.conn.commit()

        # Log activity
        from radio_monitor.database import activity
        activity.log_activity(
            cursor,
            'notification_updated',
            'Notification Updated',
            f'Updated notification ID {notification_id}',
            {'notification_id': notification_id, 'changes': list(data.keys())},
            'success',
            'user'
        )
        db.conn.commit()

        return jsonify({'success': True})
    finally:
        cursor.close()


@notifications_bp.route('/api/notifications/<int:notification_id>', methods=['DELETE'])
@requires_auth
def api_delete_notification(notification_id):
    """Delete a notification configuration"""
    db = current_app.config.get('db')
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()
    try:
        from radio_monitor.database import notifications as notif_db

        # Get notification details for logging
        notification = notif_db.get_notification(cursor, notification_id)
        if not notification:
            return jsonify({'error': 'Notification not found'}), 404

        success = notif_db.delete_notification(cursor, notification_id)
        if not success:
            return jsonify({'error': 'Failed to delete notification'}), 500

        db.conn.commit()

        # Log activity
        from radio_monitor.database import activity
        activity.log_activity(
            cursor,
            'notification_deleted',
            'Notification Deleted',
            f'Deleted notification "{notification["name"]}"',
            {'notification_id': notification_id, 'type': notification['notification_type']},
            'success',
            'user'
        )
        db.conn.commit()

        return jsonify({'success': True})
    finally:
        cursor.close()


@notifications_bp.route('/api/notifications/<int:notification_id>/test', methods=['POST'])
@requires_auth
def api_test_notification(notification_id):
    """Send a test notification

    Request body optional:
        - title: Custom title
        - message: Custom message
    """
    db = current_app.config.get('db')
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    data = request.get_json() or {}
    title = data.get('title', 'Test Notification')
    message = data.get('message', 'This is a test notification from Radio Monitor 1.0')

    cursor = db.get_cursor()
    try:
        from radio_monitor.database import notifications as notif_db
        from radio_monitor.notifications import send_notification

        notification = notif_db.get_notification(cursor, notification_id)
        if not notification:
            return jsonify({'error': 'Notification not found'}), 404

        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"=" * 60)
        logger.info(f"TEST NOTIFICATION API CALLED")
        logger.info(f"Notification ID: {notification_id}")
        logger.info(f"Name: {notification['name']}")
        logger.info(f"Type: {notification['notification_type']}")
        logger.info(f"Config: {notification['config']}")
        logger.info(f"Enabled: {notification['enabled']}")
        logger.info(f"Title: {title}")
        logger.info(f"Message: {message}")
        logger.info(f"=" * 60)

        # Send test notification
        logger.info(f"Calling send_notification()...")
        try:
            success = send_notification(
                notification['notification_type'],
                notification['config'],
                title,
                message,
                'info'
            )
            logger.info(f"send_notification() returned: {success} without exception")
        except Exception as e:
            logger.error(f"Exception during send_notification(): {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            success = False
            error_message = f"Exception: {str(e)}"

        logger.info(f"Final success value: {success}")
        logger.info(f"=" * 60)

        # Determine error message
        error_message = None
        if not success:
            logger.error(f"Test notification FAILED for {notification['name']}")
            # Check config
            if not notification['config'].get('server_url') or not notification['config'].get('app_token'):
                error_message = "Gotify server URL or app token not configured"
                logger.error("Config incomplete")
            else:
                error_message = f"Failed to send to {notification['config'].get('server_url')} - check server is running"
                logger.error(f"Config looks complete, send failed for server: {notification['config'].get('server_url')}")
        else:
            logger.info(f"Test notification SUCCEEDED for {notification['name']}")

        # Log to history
        notif_db.log_notification_send(
            cursor,
            notification_id,
            'test',
            'info',
            title,
            message,
            success,
            error_message
        )

        # Update notification stats
        if success:
            notif_db.update_notification_triggered(cursor, notification_id)
        else:
            notif_db.increment_notification_failures(cursor, notification_id)

        db.conn.commit()

        if success:
            return jsonify({'success': True, 'message': 'Test notification sent successfully'})
        else:
            return jsonify({
                'success': False,
                'message': f'Failed to send test notification: {error_message}'
            }), 500
    finally:
        cursor.close()


@notifications_bp.route('/api/notifications/<int:notification_id>/history')
@requires_auth
def api_get_notification_history(notification_id):
    """Get notification send history

    Query params:
        - limit: Items per page (default 50)
        - offset: Pagination offset
        - success_only: Filter by success (true/false)
    """
    db = current_app.config.get('db')
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    success_only_param = request.args.get('success_only')

    success_only = None
    if success_only_param == 'true':
        success_only = True
    elif success_only_param == 'false':
        success_only = False

    cursor = db.get_cursor()
    try:
        from radio_monitor.database import notifications as notif_db

        history = notif_db.get_notification_history(
            cursor,
            notification_id=notification_id,
            limit=limit,
            offset=offset,
            success_only=success_only
        )

        # Get total count
        cursor.execute("""
            SELECT COUNT(*) FROM notification_history
            WHERE notification_id = ?
        """, (notification_id,))
        total = cursor.fetchone()[0]

        return jsonify({
            'history': history,
            'total': total,
            'limit': limit,
            'offset': offset
        })
    finally:
        cursor.close()


@notifications_bp.route('/api/notifications/<int:notification_id>/stats')
@requires_auth
def api_get_notification_stats(notification_id):
    """Get statistics for a specific notification"""
    db = current_app.config.get('db')
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    cursor = db.get_cursor()
    try:
        from radio_monitor.database import notifications as notif_db

        stats = notif_db.get_notification_stats(cursor, notification_id)
        return jsonify(stats)
    finally:
        cursor.close()


@notifications_bp.route('/api/triggers')
@requires_auth
def api_get_triggers():
    """Get available notification triggers"""
    from radio_monitor.notifications import NOTIFICATION_TRIGGERS

    triggers = [
        {'key': key, 'label': label}
        for key, label in NOTIFICATION_TRIGGERS.items()
    ]

    return jsonify({'triggers': triggers})


@notifications_bp.route('/api/history')
@requires_auth
def api_get_all_history():
    """Get all notification history across all notifications

    Query params:
        - limit: Items per page (default 50)
        - offset: Pagination offset
        - success_only: Filter by success (true/false)
    """
    db = current_app.config.get('db')
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    success_only_param = request.args.get('success_only')

    success_only = None
    if success_only_param == 'true':
        success_only = True
    elif success_only_param == 'false':
        success_only = False

    cursor = db.get_cursor()
    try:
        from radio_monitor.database import notifications as notif_db

        history = notif_db.get_notification_history(
            cursor,
            notification_id=None,
            limit=limit,
            offset=offset,
            success_only=success_only
        )

        # Get total count
        query = "SELECT COUNT(*) FROM notification_history WHERE 1=1"
        params = []
        if success_only is not None:
            query += " AND success = ?"
            params.append(1 if success_only else 0)

        cursor.execute(query, params)
        total = cursor.fetchone()[0]

        return jsonify({
            'history': history,
            'total': total,
            'limit': limit,
            'offset': offset
        })
    finally:
        cursor.close()


@notifications_bp.route('/api/types')
@requires_auth
def api_get_notification_types():
    """Get available notification types with their config schemas"""
    types = {
        'discord': {
            'name': 'Discord',
            'description': 'Send notifications to Discord via webhook',
            'config_fields': [
                {'name': 'webhook_url', 'type': 'url', 'required': True, 'label': 'Webhook URL'}
            ]
        },
        'slack': {
            'name': 'Slack',
            'description': 'Send notifications to Slack via webhook',
            'config_fields': [
                {'name': 'webhook_url', 'type': 'url', 'required': True, 'label': 'Webhook URL'}
            ]
        },
        'email': {
            'name': 'Email',
            'description': 'Send notifications via email (SMTP)',
            'config_fields': [
                {'name': 'smtp_server', 'type': 'text', 'required': True, 'label': 'SMTP Server'},
                {'name': 'smtp_port', 'type': 'number', 'required': True, 'label': 'SMTP Port', 'default': 587},
                {'name': 'username', 'type': 'text', 'required': True, 'label': 'Username'},
                {'name': 'password', 'type': 'password', 'required': True, 'label': 'Password'},
                {'name': 'from_addr', 'type': 'email', 'required': False, 'label': 'From Address'},
                {'name': 'to_addr', 'type': 'email', 'required': True, 'label': 'To Address'}
            ]
        },
        'telegram': {
            'name': 'Telegram',
            'description': 'Send notifications via Telegram Bot API',
            'config_fields': [
                {'name': 'bot_token', 'type': 'text', 'required': True, 'label': 'Bot Token'},
                {'name': 'chat_id', 'type': 'text', 'required': True, 'label': 'Chat ID'}
            ]
        },
        'gotify': {
            'name': 'Gotify',
            'description': 'Self-hosted push notification server',
            'config_fields': [
                {'name': 'server_url', 'type': 'url', 'required': True, 'label': 'Server URL'},
                {'name': 'app_token', 'type': 'text', 'required': True, 'label': 'App Token'},
                {'name': 'priority', 'type': 'number', 'required': False, 'label': 'Priority (1-10)', 'default': 5}
            ]
        },
        'ntfy': {
            'name': 'Ntfy.sh',
            'description': 'Simple HTTP pub/sub notification service',
            'config_fields': [
                {'name': 'topic', 'type': 'text', 'required': True, 'label': 'Topic'},
                {'name': 'server_url', 'type': 'url', 'required': False, 'label': 'Server URL', 'default': 'https://ntfy.sh'},
                {'name': 'auth_token', 'type': 'password', 'required': False, 'label': 'Auth Token (optional)'},
                {'name': 'priority', 'type': 'number', 'required': False, 'label': 'Priority (1-5)', 'default': 3}
            ]
        },
        'mattermost': {
            'name': 'Mattermost',
            'description': 'Send notifications to Mattermost via webhook',
            'config_fields': [
                {'name': 'webhook_url', 'type': 'url', 'required': True, 'label': 'Webhook URL'},
                {'name': 'channel', 'type': 'text', 'required': False, 'label': 'Channel (optional)'},
                {'name': 'username', 'type': 'text', 'required': False, 'label': 'Username', 'default': 'Radio Monitor'}
            ]
        },
        'rocketchat': {
            'name': 'Rocket.Chat',
            'description': 'Send notifications to Rocket.Chat via webhook',
            'config_fields': [
                {'name': 'webhook_url', 'type': 'url', 'required': True, 'label': 'Webhook URL'},
                {'name': 'username', 'type': 'text', 'required': False, 'label': 'Username', 'default': 'Radio Monitor'},
                {'name': 'emoji', 'type': 'text', 'required': False, 'label': 'Emoji', 'default': ':robot_face:'}
            ]
        },
        'matrix': {
            'name': 'Matrix',
            'description': 'Decentralized messaging protocol',
            'config_fields': [
                {'name': 'homeserver', 'type': 'url', 'required': True, 'label': 'Homeserver URL'},
                {'name': 'access_token', 'type': 'text', 'required': True, 'label': 'Access Token'},
                {'name': 'room_id', 'type': 'text', 'required': True, 'label': 'Room ID'}
            ]
        },
        'pushover': {
            'name': 'Pushover',
            'description': 'Simple mobile push notifications',
            'config_fields': [
                {'name': 'api_token', 'type': 'text', 'required': True, 'label': 'API Token'},
                {'name': 'user_key', 'type': 'text', 'required': True, 'label': 'User Key'},
                {'name': 'device', 'type': 'text', 'required': False, 'label': 'Device (optional)'},
                {'name': 'priority', 'type': 'number', 'required': False, 'label': 'Priority (-2 to 2)', 'default': 0}
            ]
        },
        'pushbullet': {
            'name': 'Pushbullet',
            'description': 'Cross-platform push notifications',
            'config_fields': [
                {'name': 'api_key', 'type': 'text', 'required': True, 'label': 'API Key'},
                {'name': 'device_iden', 'type': 'text', 'required': False, 'label': 'Device ID (optional)'}
            ]
        },
        'prowl': {
            'name': 'Prowl',
            'description': 'iOS push notifications',
            'config_fields': [
                {'name': 'api_key', 'type': 'text', 'required': True, 'label': 'API Key'},
                {'name': 'provider_key', 'type': 'text', 'required': False, 'label': 'Provider Key (optional)'},
                {'name': 'application', 'type': 'text', 'required': False, 'label': 'Application Name', 'default': 'Radio Monitor'},
                {'name': 'priority', 'type': 'number', 'required': False, 'label': 'Priority (-2 to 2)', 'default': 0}
            ]
        },
        'boxcar': {
            'name': 'Boxcar',
            'description': 'Multi-platform push notifications',
            'config_fields': [
                {'name': 'access_token', 'type': 'text', 'required': True, 'label': 'Access Token'}
            ]
        },
        'mqtt': {
            'name': 'MQTT',
            'description': 'IoT/home automation messaging (requires paho-mqtt)',
            'config_fields': [
                {'name': 'broker', 'type': 'text', 'required': True, 'label': 'Broker Address'},
                {'name': 'port', 'type': 'number', 'required': False, 'label': 'Port', 'default': 1883},
                {'name': 'topic', 'type': 'text', 'required': False, 'label': 'Topic', 'default': 'radio-monitor/notifications'},
                {'name': 'username', 'type': 'text', 'required': False, 'label': 'Username (optional)'},
                {'name': 'password', 'type': 'password', 'required': False, 'label': 'Password (optional)'},
                {'name': 'qos', 'type': 'number', 'required': False, 'label': 'QoS (0-2)', 'default': 1},
                {'name': 'retain', 'type': 'checkbox', 'required': False, 'label': 'Retain Message', 'default': False}
            ]
        }
    }

    return jsonify({'types': types})
