"""
Centralized logging configuration for the Behavior-Based Authentication system.

This module provides a configurable logging setup that can be adjusted via
environment variables and uses rotating file handlers for production use.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler


def setup_logging(app=None, log_level=None, log_file=None):
    """
    Configure logging for the application.

    Args:
        app: Flask application instance (optional)
        log_level: Logging level (optional, defaults to LOG_LEVEL env var or INFO)
        log_file: Log file path (optional, defaults to LOG_FILE env var or 'behavioral_auth.log')

    Returns:
        logging.Logger: Configured logger instance
    """
    # Get configuration from environment or parameters
    level_str = log_level or os.getenv("LOG_LEVEL", "INFO").upper()
    log_file_path = log_file or os.getenv("LOG_FILE", "behavioral_auth.log")
    log_max_bytes = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10MB default
    log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    log_format = os.getenv(
        "LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Map string level to logging constant
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    log_level_value = level_map.get(level_str, logging.INFO)

    # Create logger
    logger = logging.getLogger("behavior_auth")
    logger.setLevel(log_level_value)

    # Clear existing handlers to avoid duplicates
    if logger.handlers:
        logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(log_format)
    formatter.datefmt = "%Y-%m-%d %H:%M:%S"

    # Console handler (always added)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level_value)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler with size-based rotation (only if not in testing mode)
    if os.getenv("FLASK_ENV") != "testing":
        try:
            # Ensure log directory exists
            log_dir = os.path.dirname(log_file_path)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            # Rotating file handler
            file_handler = RotatingFileHandler(
                log_file_path,
                maxBytes=log_max_bytes,
                backupCount=log_backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(log_level_value)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        except (OSError, IOError) as e:
            logger.warning(f"Could not set up file logging: {e}")

    # Add Flask app logger handler if app is provided
    if app:
        app.logger.handlers = logger.handlers
        app.logger.setLevel(log_level_value)

    # Log startup message
    logger.info("=" * 60)
    logger.info("Behavior-Based Authentication System Starting")
    logger.info(f"Log Level: {level_str}")
    logger.info(f"Log File: {log_file_path}")
    logger.info(f"Python Version: {sys.version}")
    logger.info("=" * 60)

    return logger


def get_logger(name=None):
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name (optional, defaults to 'behavior_auth')

    Returns:
        logging.Logger: Logger instance
    """
    logger_name = name or "behavior_auth"
    logger = logging.getLogger(logger_name)

    # If logger doesn't exist or has no handlers, set it up
    if not logger.handlers:
        setup_logging()

    return logger


# Example usage and testing
if __name__ == "__main__":
    # Test logging configuration
    test_logger = setup_logging()
    test_logger.debug("This is a DEBUG message")
    test_logger.info("This is an INFO message")
    test_logger.warning("This is a WARNING message")
    test_logger.error("This is an ERROR message")
    test_logger.critical("This is a CRITICAL message")
