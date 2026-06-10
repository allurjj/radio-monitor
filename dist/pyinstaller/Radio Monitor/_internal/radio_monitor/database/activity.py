"""
Activity logging module for Radio Monitor 1.0

This module provides functions to log and retrieve system activity events.
Activity logs create a timeline/audit trail of all system events.

Event Types:
- scrape: Radio scraping operations
- import: Lidarr import operations
- playlist_update: Plex playlist updates
- playlist_error: Playlist creation failures
- error: System errors
- station_health: Station health changes
- system: System events (startup, shutdown, etc)
- user: User-initiated actions

Severity Levels:
- info: Informational events
- warning: Warning events (non-critical issues)
- error: Error events (failures that need attention)
- success: Successful operations
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


def log_activity(
    cursor,
    event_type: str,
    title: str,
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    severity: str = 'info',
    source: str = 'system'
) -> int:
    """Log an activity event

    Args:
        cursor: SQLite cursor object
        event_type: Type of event (scrape, import, error, etc.)
        title: Brief title of the event
        description: Detailed description (optional)
        metadata: Additional metadata as dict (will be JSON serialized)
        severity: Event severity (info, warning, error, success)
        source: Event source (system, user, scheduler)

    Returns:
        int: ID of the inserted activity log entry
    """
    try:
        metadata_json = json.dumps(metadata) if metadata else None

        cursor.execute("""
            INSERT INTO activity_log (
                event_type, event_severity, title, description, metadata, source
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (event_type, severity, title, description, metadata_json, source))

        log_id = cursor.lastrowid
        logger.debug(f"Logged activity {log_id}: {event_type} - {title}")
        return log_id

    except Exception as e:
        logger.error(f"Failed to log activity: {e}")
        return 0


def get_activity_paginated(
    cursor,
    page: int = 1,
    limit: int = 50,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    days: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Get activity log entries with pagination and filtering

    Args:
        cursor: SQLite cursor object
        page: Page number (1-indexed)
        limit: Items per page
        event_type: Filter by event type (optional)
        severity: Filter by severity (optional)
        days: Only show entries from last N days (optional)

    Returns:
        List of activity log entries as dictionaries
    """
    try:
        offset = (page - 1) * limit

        # Build query with filters
        where_clauses = []
        params = []

        if event_type:
            where_clauses.append("event_type = ?")
            params.append(event_type)

        if severity:
            where_clauses.append("event_severity = ?")
            params.append(severity)

        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            where_clauses.append("timestamp >= ?")
            params.append(cutoff_date.isoformat())

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        query = f"""
            SELECT id, timestamp, event_type, event_severity, title,
                   description, metadata, source
            FROM activity_log
            WHERE {where_sql}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """

        params.extend([limit, offset])
        cursor.execute(query, params)

        rows = cursor.fetchall()

        # Convert to list of dicts
        activities = []
        for row in rows:
            activity = {
                'id': row[0],
                'timestamp': row[1],
                'event_type': row[2],
                'severity': row[3],
                'title': row[4],
                'description': row[5],
                'metadata': json.loads(row[6]) if row[6] else None,
                'source': row[7]
            }
            activities.append(activity)

        return activities

    except Exception as e:
        logger.error(f"Failed to get activity log: {e}")
        return []


def get_activity_stats(
    cursor,
    days: int = 7
) -> Dict[str, Any]:
    """Get activity statistics for the last N days

    Args:
        cursor: SQLite cursor object
        days: Number of days to look back

    Returns:
        Dictionary with activity statistics
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=days)

        # Total events
        cursor.execute("""
            SELECT COUNT(*) FROM activity_log
            WHERE timestamp >= ?
        """, (cutoff_date.isoformat(),))
        total_events = cursor.fetchone()[0]

        # Events by type
        cursor.execute("""
            SELECT event_type, COUNT(*) as count
            FROM activity_log
            WHERE timestamp >= ?
            GROUP BY event_type
            ORDER BY count DESC
        """, (cutoff_date.isoformat(),))
        by_type = {row[0]: row[1] for row in cursor.fetchall()}

        # Events by severity
        cursor.execute("""
            SELECT event_severity, COUNT(*) as count
            FROM activity_log
            WHERE timestamp >= ?
            GROUP BY event_severity
        """, (cutoff_date.isoformat(),))
        by_severity = {row[0]: row[1] for row in cursor.fetchall()}

        # Recent errors
        cursor.execute("""
            SELECT COUNT(*) FROM activity_log
            WHERE timestamp >= ? AND event_severity = 'error'
        """, (cutoff_date.isoformat(),))
        error_count = cursor.fetchone()[0]

        return {
            'total_events': total_events,
            'by_type': by_type,
            'by_severity': by_severity,
            'error_count': error_count,
            'days': days
        }

    except Exception as e:
        logger.error(f"Failed to get activity stats: {e}")
        return {
            'total_events': 0,
            'by_type': {},
            'by_severity': {},
            'error_count': 0,
            'days': days
        }


def get_recent_activity(
    cursor,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Get recent activity entries (for dashboard feed)

    Args:
        cursor: SQLite cursor object
        limit: Maximum number of entries to return

    Returns:
        List of recent activity entries as dictionaries
    """
    return get_activity_paginated(cursor, page=1, limit=limit)


def cleanup_old_activity(
    cursor,
    days: int = 90
) -> int:
    """Delete activity log entries older than N days

    Args:
        cursor: SQLite cursor object
        days: Retention period in days (default: 90)

    Returns:
        Number of entries deleted
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=days)

        cursor.execute("""
            DELETE FROM activity_log
            WHERE timestamp < ?
        """, (cutoff_date.isoformat(),))

        deleted = cursor.rowcount
        logger.info(f"Cleaned up {deleted} old activity log entries (older than {days} days)")
        return deleted

    except Exception as e:
        logger.error(f"Failed to cleanup old activity: {e}")
        return 0
