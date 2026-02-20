"""
Logging configuration for Radio Monitor

This module sets up logging based on settings from radio_monitor_settings.json:
- Console logging (colored, for development)
- File logging (rotating, for production debugging)
- Configurable log levels for console and file
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
import re


class ColorStripFormatter(logging.Formatter):
    """Custom formatter that strips ANSI color codes from log messages"""

    def format(self, record):
        # Strip ANSI escape sequences
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        record.msg = ansi_escape.sub('', str(record.msg))
        return super().format(record)


def setup_logging(settings=None):
    """Setup logging based on settings

    Args:
        settings: Settings dict from radio_monitor_settings.json
                 If None, uses defaults

    Returns:
        None
    """
    # Check if running as frozen EXE (Windows)
    is_frozen = getattr(sys, 'frozen', False)

    # Extract logging settings with defaults
    logging_config = settings.get('logging', {}) if settings else {}

    log_file = logging_config.get('file', 'radio_monitor.log')
    max_bytes = logging_config.get('max_bytes', 10485760)  # 10MB default
    backup_count = logging_config.get('backup_count', 5)
    console_level_name = logging_config.get('console_level', 'INFO')
    file_level_name = logging_config.get('file_level', 'ERROR')

    # Convert level names to logging constants
    console_level = getattr(logging, console_level_name.upper(), logging.INFO)
    file_level = getattr(logging, file_level_name.upper(), logging.ERROR)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all levels, handlers filter

    # Remove any existing handlers
    root_logger.handlers.clear()

    # Create console handler (ONLY if not frozen EXE)
    if not is_frozen:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # Create file handler with rotation
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(file_level)
        file_formatter = ColorStripFormatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        # If file logging fails, at least we have console logging
        print(f"Warning: Could not setup file logging: {e}")

    # Reduce Flask/Werkzeug request logging noise
    # In frozen EXE, completely suppress werkzeug logging
    if is_frozen:
        logging.getLogger('werkzeug').setLevel(logging.CRITICAL)
        logging.getLogger('flask').setLevel(logging.WARNING)
    else:
        logging.getLogger('werkzeug').setLevel(logging.ERROR)

    # Log the configuration
    logger = logging.getLogger(__name__)
    if is_frozen:
        logger.info(f"Logging configured: file={file_level_name}, file={log_file} (no console - frozen EXE)")
    else:
        logger.info(f"Logging configured: console={console_level_name}, file={file_level_name}, file={log_file}")
    logger.debug(f"Max file size: {max_bytes} bytes, Backup count: {backup_count}")


def get_logger(name):
    """Get a logger instance

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
