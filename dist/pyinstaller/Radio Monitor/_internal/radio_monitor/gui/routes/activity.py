"""
Activity Routes for Radio Monitor 1.0

Activity timeline, event history, and system events tracking.
"""

import logging
from flask import Blueprint, render_template, jsonify, request, current_app
from radio_monitor.auth import requires_auth

logger = logging.getLogger(__name__)

activity_bp = Blueprint('activity', __name__)


def get_db():
    """Get database instance from Flask app config"""
    return current_app.config.get('db')


@activity_bp.route('/activity')
@requires_auth
def activity_page():
    """Activity timeline and event history page"""
    return render_template('activity.html')


@activity_bp.route('/api/activity/recent')
@requires_auth
def api_activity_recent():
    """Get recent activity entries (for dashboard feed)

    Query params:
        limit: Number of entries (default: 20)

    Returns JSON:
        [
            {
                "id": 1,
                "timestamp": "2025-02-09 12:34:56",
                "event_type": "scrape",
                "severity": "success",
                "title": "Scrape completed",
                "description": "Processed 15 songs from 3 stations",
                "metadata": {"songs": 15, "stations": 3},
                "source": "system"
            },
            ...
        ]
    """
    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        from radio_monitor.database.activity import get_recent_activity

        limit = request.args.get('limit', 20, type=int)
        limit = min(limit, 100)  # Cap at 100

        cursor = db.get_cursor()
        try:
            activities = get_recent_activity(cursor, limit=limit)
            return jsonify(activities)
        finally:
            cursor.close()

    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        return jsonify({'error': str(e)}), 500


@activity_bp.route('/api/activity')
@requires_auth
def api_activity():
    """Get activity log with pagination and filtering

    Query params:
        page: Page number (default: 1)
        limit: Items per page (default: 50)
        event_type: Filter by event type (optional)
        severity: Filter by severity (optional)
        days: Only show entries from last N days (optional)

    Returns JSON:
        {
            "activities": [...],
            "page": 1,
            "limit": 50,
            "total": 150,
            "filters": {...}
        }
    """
    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        from radio_monitor.database.activity import get_activity_paginated

        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        event_type = request.args.get('event_type')
        severity = request.args.get('severity')
        days = request.args.get('days', type=int)

        # Validate and cap limit
        limit = min(max(1, limit), 200)

        cursor = db.get_cursor()
        try:
            activities = get_activity_paginated(
                cursor,
                page=page,
                limit=limit,
                event_type=event_type,
                severity=severity,
                days=days
            )

            # Get total count (simplified - for accurate total, need separate query)
            # For now, return activities with pagination info
            return jsonify({
                'activities': activities,
                'page': page,
                'limit': limit,
                'total': len(activities),  # Simplified
                'filters': {
                    'event_type': event_type,
                    'severity': severity,
                    'days': days
                }
            })
        finally:
            cursor.close()

    except Exception as e:
        logger.error(f"Error getting activity log: {e}")
        return jsonify({'error': str(e)}), 500


@activity_bp.route('/api/activity/stats')
@requires_auth
def api_activity_stats():
    """Get activity statistics

    Query params:
        days: Number of days to look back (default: 7)

    Returns JSON:
        {
            "total_events": 150,
            "by_type": {"scrape": 50, "import": 20, ...},
            "by_severity": {"info": 100, "warning": 30, "error": 5, "success": 15},
            "error_count": 5,
            "days": 7
        }
    """
    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    try:
        from radio_monitor.database.activity import get_activity_stats

        days = request.args.get('days', 7, type=int)

        cursor = db.get_cursor()
        try:
            stats = get_activity_stats(cursor, days=days)
            return jsonify(stats)
        finally:
            cursor.close()

    except Exception as e:
        logger.error(f"Error getting activity stats: {e}")
        return jsonify({'error': str(e)}), 500
