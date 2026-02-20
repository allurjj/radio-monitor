"""
Log viewer routes for Radio Monitor 1.0

This blueprint provides routes for viewing and filtering application logs:
- Log viewer page with real-time updates
- Log filtering by level and search
- Log download functionality
- Clear logs functionality
"""

import os
import logging
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request, send_file, current_app
from radio_monitor.auth import requires_auth

logger = logging.getLogger(__name__)

# Create blueprint
logs_bp = Blueprint('logs', __name__, url_prefix='/logs')


def get_log_file_path():
    """Get the log file path from settings

    Returns:
        str: Path to log file or None if not configured
    """
    settings = current_app.config.get('settings')
    if settings:
        log_file = settings.get('logging', {}).get('file', 'radio_monitor.log')
        return log_file
    return 'radio_monitor.log'


def parse_log_level(line):
    """Parse log level from a log line

    Args:
        line: Log line string

    Returns:
        str: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) or None
    """
    line_upper = line.upper()
    if 'DEBUG' in line_upper:
        return 'DEBUG'
    elif 'INFO' in line_upper:
        return 'INFO'
    elif 'WARNING' in line_upper or 'WARN' in line_upper:
        return 'WARNING'
    elif 'ERROR' in line_upper:
        return 'ERROR'
    elif 'CRITICAL' in line_upper:
        return 'CRITICAL'
    return None


def parse_log_line(line, line_number):
    """Parse a log line into structured data

    Args:
        line: Log line string
        line_number: Line number in file

    Returns:
        dict: Parsed log data or None if not a valid log line
    """
    if not line.strip():
        return None

    level = parse_log_level(line)

    # Try to parse timestamp (format: YYYY-MM-DD HH:MM:SS)
    timestamp = None
    message = line
    try:
        # Look for timestamp at start of line
        parts = line.split(' - ', 2)
        if len(parts) >= 3:
            # Format: timestamp - level - message
            timestamp = parts[0]
            message = parts[2] if len(parts) > 2 else line
        elif len(parts) == 2:
            timestamp = parts[0]
            message = parts[1]
    except Exception:
        pass

    return {
        'line_number': line_number,
        'timestamp': timestamp,
        'level': level or 'INFO',
        'message': message.strip(),
        'raw': line.strip()
    }


def read_log_file(log_path, tail_lines=None, filter_level=None, search=None):
    """Read and parse log file

    Args:
        log_path: Path to log file
        tail_lines: Number of lines to read from end (None for all)
        filter_level: Filter by log level (DEBUG, INFO, WARNING, ERROR)
        search: Search string to filter by

    Returns:
        tuple: (log_entries, total_lines, file_size)
    """
    if not os.path.exists(log_path):
        return [], 0, 0

    file_size = os.path.getsize(log_path)
    log_entries = []

    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        total_lines = len(lines)

        # If tail_lines specified, only read last N lines
        if tail_lines:
            lines = lines[-tail_lines:]

        # Parse and filter lines
        for idx, line in enumerate(lines, start=(total_lines - len(lines) + 1)):
            entry = parse_log_line(line, idx)
            if entry:
                # Apply filters
                if filter_level and entry['level'] != filter_level:
                    continue
                if search and search.lower() not in line.lower():
                    continue

                log_entries.append(entry)

        return log_entries, total_lines, file_size

    except Exception as e:
        logger.error(f"Error reading log file: {e}")
        return [], 0, file_size


@logs_bp.route('/')
@requires_auth
def index():
    """Log viewer page"""
    return render_template('logs.html')


@logs_bp.route('/api/logs')
@requires_auth
def get_logs():
    """Get log entries with filtering

    Query params:
        tail: Number of lines to read from end (default: 1000)
        level: Filter by log level (DEBUG, INFO, WARNING, ERROR)
        search: Search string to filter by
    """
    try:
        tail = request.args.get('tail', type=int, default=1000)
        filter_level = request.args.get('level')
        search = request.args.get('search')

        # Limit tail to prevent performance issues
        if tail > 10000:
            tail = 10000

        log_path = get_log_file_path()
        log_entries, total_lines, file_size = read_log_file(
            log_path, tail_lines=tail, filter_level=filter_level, search=search
        )

        return jsonify({
            'success': True,
            'logs': log_entries,
            'total_lines': total_lines,
            'file_size': file_size,
            'file_size_human': f"{file_size / 1024:.2f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024 * 1024):.2f} MB"
        })

    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@logs_bp.route('/api/logs/download')
@requires_auth
def download_logs():
    """Download full log file"""
    try:
        log_path = get_log_file_path()

        if not os.path.exists(log_path):
            return jsonify({
                'success': False,
                'error': 'Log file not found'
            }), 404

        return send_file(
            log_path,
            as_attachment=True,
            download_name=f"radio_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )

    except Exception as e:
        logger.error(f"Error downloading logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@logs_bp.route('/api/logs', methods=['DELETE'])
@requires_auth
def clear_logs():
    """Clear log file (with confirmation)

    Note: This is a destructive action and should require confirmation
    """
    try:
        # Require confirmation parameter
        confirmation = request.json.get('confirm')

        if confirmation != 'CLEAR_LOGS':
            return jsonify({
                'success': False,
                'error': 'Invalid confirmation. Must send {"confirm": "CLEAR_LOGS"}'
            }), 400

        log_path = get_log_file_path()

        if not os.path.exists(log_path):
            return jsonify({
                'success': False,
                'error': 'Log file not found'
            }), 404

        # Backup log file before clearing
        backup_path = f"{log_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.rename(log_path, backup_path)

        # Create new empty log file
        with open(log_path, 'w') as f:
            f.write(f"# Log file cleared at {datetime.now().isoformat()}\n")

        logger.info(f"Log file cleared. Backup saved to {backup_path}")

        return jsonify({
            'success': True,
            'message': 'Log file cleared successfully',
            'backup_path': backup_path
        })

    except Exception as e:
        logger.error(f"Error clearing logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@logs_bp.route('/api/logs/stats')
@requires_auth
def get_log_stats():
    """Get log file statistics

    Returns:
        JSON with log file stats (size, line count, level distribution)
    """
    try:
        log_path = get_log_file_path()

        if not os.path.exists(log_path):
            return jsonify({
                'success': True,
                'exists': False,
                'stats': None
            })

        log_entries, total_lines, file_size = read_log_file(log_path)

        # Count by level
        level_counts = {}
        for entry in log_entries:
            level = entry['level']
            level_counts[level] = level_counts.get(level, 0) + 1

        return jsonify({
            'success': True,
            'exists': True,
            'stats': {
                'file_path': log_path,
                'file_size': file_size,
                'file_size_human': f"{file_size / 1024:.2f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024 * 1024):.2f} MB",
                'total_lines': total_lines,
                'level_counts': level_counts
            }
        })

    except Exception as e:
        logger.error(f"Error getting log stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
