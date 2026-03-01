"""
Notifications database module for Radio Monitor 1.0

This module handles all database operations for:
- Notification configurations
- Notification history/tracking
- Trigger management

Supported notification types:
- discord: Discord webhook
- slack: Slack webhook
- email: SMTP email
- telegram: Telegram Bot API
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def create_notification(cursor, notification_type: str, name: str,
                       config: Dict[str, Any], triggers: List[str],
                       enabled: bool = True) -> int:
    """Create a new notification configuration

    Args:
        cursor: SQLite cursor object
        notification_type: Type of notification (discord, slack, email, telegram)
        name: Human-readable name
        config: Configuration dictionary (will be stored as JSON)
        triggers: List of trigger types
        enabled: Whether notification is enabled

    Returns:
        int: ID of the created notification
    """
    config_json = json.dumps(config)
    triggers_json = json.dumps(triggers)

    cursor.execute("""
        INSERT INTO notifications
        (notification_type, name, enabled, config, triggers)
        VALUES (?, ?, ?, ?, ?)
    """, (notification_type, name, enabled, config_json, triggers_json))

    notif_id = cursor.lastrowid
    logger.info(f"Created notification '{name}' (ID: {notif_id}, type: {notification_type})")
    return notif_id


def get_notification(cursor, notification_id: int) -> Optional[Dict[str, Any]]:
    """Get a notification configuration by ID

    Args:
        cursor: SQLite cursor object
        notification_id: Notification ID

    Returns:
        Dictionary with notification details or None
    """
    cursor.execute("""
        SELECT id, notification_type, name, enabled, config, triggers,
               created_at, last_triggered, failure_count
        FROM notifications
        WHERE id = ?
    """, (notification_id,))

    row = cursor.fetchone()
    if not row:
        return None

    (notif_id, notification_type, name, enabled, config_json,
     triggers_json, created_at, last_triggered, failure_count) = row

    return {
        'id': notif_id,
        'notification_type': notification_type,
        'name': name,
        'enabled': bool(enabled),
        'config': json.loads(config_json),
        'triggers': json.loads(triggers_json),
        'created_at': created_at,
        'last_triggered': last_triggered,
        'failure_count': failure_count
    }


def get_all_notifications(cursor, enabled_only: bool = False) -> List[Dict[str, Any]]:
    """Get all notification configurations

    Args:
        cursor: SQLite cursor object
        enabled_only: Only return enabled notifications

    Returns:
        List of notification configurations
    """
    query = """
        SELECT id, notification_type, name, enabled, config, triggers,
               created_at, last_triggered, failure_count
        FROM notifications
    """
    if enabled_only:
        query += " WHERE enabled = 1"
    query += " ORDER BY created_at DESC"

    cursor.execute(query)

    notifications = []
    for row in cursor.fetchall():
        (notif_id, notification_type, name, enabled, config_json,
         triggers_json, created_at, last_triggered, failure_count) = row

        notifications.append({
            'id': notif_id,
            'notification_type': notification_type,
            'name': name,
            'enabled': bool(enabled),
            'config': json.loads(config_json),
            'triggers': json.loads(triggers_json),
            'created_at': created_at,
            'last_triggered': last_triggered,
            'failure_count': failure_count
        })

    return notifications


def get_notifications_for_event(cursor, event_type: str) -> List[Dict[str, Any]]:
    """Get all enabled notifications that should trigger for an event

    Args:
        cursor: SQLite cursor object
        event_type: Event type (on_scrape_complete, on_import_error, etc.)

    Returns:
        List of matching notification configurations
    """
    cursor.execute("""
        SELECT id, notification_type, name, enabled, config, triggers,
               created_at, last_triggered, failure_count
        FROM notifications
        WHERE enabled = 1
        ORDER BY created_at DESC
    """)

    notifications = []
    for row in cursor.fetchall():
        (notif_id, notification_type, name, enabled, config_json,
         triggers_json, created_at, last_triggered, failure_count) = row

        triggers = json.loads(triggers_json)
        if event_type in triggers:
            notifications.append({
                'id': notif_id,
                'notification_type': notification_type,
                'name': name,
                'enabled': bool(enabled),
                'config': json.loads(config_json),
                'triggers': triggers,
                'created_at': created_at,
                'last_triggered': last_triggered,
                'failure_count': failure_count
            })

    return notifications


def update_notification(cursor, notification_id: int, **kwargs) -> bool:
    """Update notification configuration

    Args:
        cursor: SQLite cursor object
        notification_id: Notification ID
        **kwargs: Fields to update (name, enabled, config, triggers)

    Returns:
        bool: True if updated successfully
    """
    updates = []
    params = []

    for key, value in kwargs.items():
        if key in ['name', 'enabled']:
            updates.append(f"{key} = ?")
            params.append(value)
        elif key == 'config':
            updates.append("config = ?")
            params.append(json.dumps(value))
        elif key == 'triggers':
            updates.append("triggers = ?")
            params.append(json.dumps(value))

    if not updates:
        return False

    params.append(notification_id)
    query = f"UPDATE notifications SET {', '.join(updates)} WHERE id = ?"

    cursor.execute(query, params)
    return cursor.rowcount > 0


def delete_notification(cursor, notification_id: int) -> bool:
    """Delete a notification configuration

    Args:
        cursor: SQLite cursor object
        notification_id: Notification ID

    Returns:
        bool: True if deleted successfully
    """
    cursor.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
    deleted = cursor.rowcount > 0

    if deleted:
        # Also delete history
        cursor.execute("DELETE FROM notification_history WHERE notification_id = ?",
                      (notification_id,))
        logger.info(f"Deleted notification ID {notification_id} and its history")

    return deleted


def update_notification_triggered(cursor, notification_id: int) -> bool:
    """Update last_triggered timestamp for a notification

    Args:
        cursor: SQLite cursor object
        notification_id: Notification ID

    Returns:
        bool: True if updated successfully
    """
    # Use local time for last_triggered timestamp
    now = datetime.now()
    cursor.execute("""
        UPDATE notifications
        SET last_triggered = ?
        WHERE id = ?
    """, (now, notification_id,))

    return cursor.rowcount > 0


def increment_notification_failures(cursor, notification_id: int) -> bool:
    """Increment failure count for a notification

    Args:
        cursor: SQLite cursor object
        notification_id: Notification ID

    Returns:
        bool: True if updated successfully
    """
    cursor.execute("""
        UPDATE notifications
        SET failure_count = failure_count + 1
        WHERE id = ?
    """, (notification_id,))

    return cursor.rowcount > 0


def reset_notification_failures(cursor, notification_id: int) -> bool:
    """Reset failure count for a notification

    Args:
        cursor: SQLite cursor object
        notification_id: Notification ID

    Returns:
        bool: True if updated successfully
    """
    cursor.execute("""
        UPDATE notifications
        SET failure_count = 0
        WHERE id = ?
    """, (notification_id,))

    return cursor.rowcount > 0


def log_notification_send(cursor, notification_id: int, event_type: str,
                         severity: str, title: str, message: str,
                         success: bool, error_message: Optional[str] = None) -> int:
    """Log a notification send attempt to history

    Args:
        cursor: SQLite cursor object
        notification_id: Notification ID
        event_type: Event type
        severity: Severity level
        title: Notification title
        message: Notification message
        success: Whether send was successful
        error_message: Error message if failed

    Returns:
        int: ID of the history record
    """
    cursor.execute("""
        INSERT INTO notification_history
        (notification_id, event_type, event_severity, title, message, success, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (notification_id, event_type, severity, title, message, success, error_message))

    return cursor.lastrowid


def get_notification_history(cursor, notification_id: Optional[int] = None,
                             limit: int = 100, offset: int = 0,
                             success_only: Optional[bool] = None) -> List[Dict[str, Any]]:
    """Get notification send history

    Args:
        cursor: SQLite cursor object
        notification_id: Filter by notification ID (None = all)
        limit: Maximum records to return
        offset: Number of records to skip
        success_only: Filter by success status (None = all)

    Returns:
        List of history records
    """
    query = """
        SELECT
            h.id, h.notification_id, h.sent_at, h.event_type, h.event_severity,
            h.title, h.message, h.success, h.error_message,
            n.name as notification_name, n.notification_type
        FROM notification_history h
        LEFT JOIN notifications n ON h.notification_id = n.id
        WHERE 1=1
    """
    params = []

    if notification_id:
        query += " AND h.notification_id = ?"
        params.append(notification_id)

    if success_only is not None:
        query += " AND h.success = ?"
        params.append(1 if success_only else 0)

    query += " ORDER BY h.sent_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)

    history = []
    for row in cursor.fetchall():
        (history_id, notification_id, sent_at, event_type, severity,
         title, message, success, error_message, notif_name, notif_type) = row

        history.append({
            'id': history_id,
            'notification_id': notification_id,
            'sent_at': sent_at,
            'event_type': event_type,
            'severity': severity,
            'title': title,
            'message': message,
            'success': bool(success),
            'error_message': error_message,
            'notification_name': notif_name,
            'notification_type': notif_type
        })

    return history


def get_notification_stats(cursor, notification_id: int) -> Dict[str, Any]:
    """Get statistics for a specific notification

    Args:
        cursor: SQLite cursor object
        notification_id: Notification ID

    Returns:
        Dictionary with statistics
    """
    # Total sends
    cursor.execute("""
        SELECT COUNT(*) FROM notification_history
        WHERE notification_id = ?
    """, (notification_id,))
    total_sends = cursor.fetchone()[0]

    # Successful sends
    cursor.execute("""
        SELECT COUNT(*) FROM notification_history
        WHERE notification_id = ? AND success = 1
    """, (notification_id,))
    successful_sends = cursor.fetchone()[0]

    # Failed sends
    cursor.execute("""
        SELECT COUNT(*) FROM notification_history
        WHERE notification_id = ? AND success = 0
    """, (notification_id,))
    failed_sends = cursor.fetchone()[0]

    # Last sent
    cursor.execute("""
        SELECT sent_at FROM notification_history
        WHERE notification_id = ?
        ORDER BY sent_at DESC LIMIT 1
    """, (notification_id,))
    last_sent_result = cursor.fetchone()
    last_sent = last_sent_result[0] if last_sent_result else None

    # Sends by event type
    cursor.execute("""
        SELECT event_type, COUNT(*) as count
        FROM notification_history
        WHERE notification_id = ?
        GROUP BY event_type
        ORDER BY count DESC
    """, (notification_id,))
    by_event_type = {row[0]: row[1] for row in cursor.fetchall()}

    return {
        'total_sends': total_sends,
        'successful_sends': successful_sends,
        'failed_sends': failed_sends,
        'success_rate': round(successful_sends / total_sends * 100, 1) if total_sends > 0 else 0,
        'last_sent': last_sent,
        'by_event_type': by_event_type
    }


def cleanup_old_history(cursor, days: int = 30) -> int:
    """Delete notification history older than specified days

    Args:
        cursor: SQLite cursor object
        days: Days to retain (default 30)

    Returns:
        int: Number of records deleted
    """
    from datetime import timedelta

    cutoff_date = datetime.now() - timedelta(days=days)

    cursor.execute("""
        DELETE FROM notification_history
        WHERE sent_at < ?
    """, (cutoff_date,))

    deleted = cursor.rowcount
    logger.info(f"Deleted {deleted} old notification history records (older than {days} days)")
    return deleted
