"""
Centralized logging configuration for ADAPT-RCA.

This module provides a consistent logging setup across the entire application,
preventing multiple basicConfig() calls and ensuring proper log formatting.

Functions:
    setup_logging: Configure logging for ADAPT-RCA with appropriate handlers and formatters.
    get_logger: Get a logger instance with proper configuration.

Example:
    >>> from adapt_rca.logging_config import setup_logging
    >>> setup_logging(level='DEBUG', log_file='adapt_rca.log')
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional


# Track if logging has been configured to avoid duplicate configuration
_LOGGING_CONFIGURED = False


def setup_logging(
    level: str = 'INFO',
    log_file: Optional[str | Path] = None,
    log_format: Optional[str] = None,
    include_timestamp: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """
    Configure logging for ADAPT-RCA.

    Sets up console and optional file logging with consistent formatting.
    This should be called once at application startup.

    Args:
        level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        log_file: Optional path to log file. If provided, enables file logging
            with rotation.
        log_format: Custom log format string. If None, uses default format.
        include_timestamp: Whether to include timestamps in log messages.
            Default is True.
        max_bytes: Maximum size of log file before rotation (default 10MB).
        backup_count: Number of backup log files to keep (default 5).

    Example:
        >>> # Basic console logging
        >>> setup_logging(level='INFO')
        >>>
        >>> # Console + file logging with rotation
        >>> setup_logging(level='DEBUG', log_file='adapt_rca.log')
        >>>
        >>> # Custom format
        >>> setup_logging(
        ...     level='INFO',
        ...     log_format='[%(levelname)s] %(name)s: %(message)s'
        ... )
    """
    global _LOGGING_CONFIGURED

    if _LOGGING_CONFIGURED:
        # Logging already configured, just update level if needed
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, level.upper()))
        return

    # Default format with timestamp
    if log_format is None:
        if include_timestamp:
            log_format = (
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        else:
            log_format = '%(name)s - %(levelname)s - %(message)s'

    # Create formatter
    formatter = logging.Formatter(log_format)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove any existing handlers to prevent duplicates
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (with rotation)
    if log_file:
        log_path = Path(log_file)
        # Ensure parent directory exists
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        root_logger.info(f"Logging to file: {log_path}")

    # Mark as configured
    _LOGGING_CONFIGURED = True

    root_logger.info(f"Logging configured at {level} level")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.

    If logging hasn't been configured yet, this will set up basic logging
    at INFO level. For production use, call setup_logging() explicitly first.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Logger instance

    Example:
        >>> from adapt_rca.logging_config import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Application started")
    """
    # Ensure logging is configured
    if not _LOGGING_CONFIGURED:
        setup_logging(level='INFO')

    return logging.getLogger(name)


def reset_logging_config() -> None:
    """
    Reset logging configuration.

    This is primarily useful for testing. In production code, logging
    should only be configured once at startup.

    Example:
        >>> # In test teardown
        >>> reset_logging_config()
    """
    global _LOGGING_CONFIGURED

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    _LOGGING_CONFIGURED = False


# Convenience function for CLI usage
def configure_cli_logging(verbose: bool = False, quiet: bool = False) -> None:
    """
    Configure logging for CLI usage.

    Args:
        verbose: Enable DEBUG level logging
        quiet: Only show WARNING and above

    Example:
        >>> # In CLI entry point
        >>> from adapt_rca.logging_config import configure_cli_logging
        >>> configure_cli_logging(verbose=args.verbose, quiet=args.quiet)
    """
    if quiet:
        level = 'WARNING'
    elif verbose:
        level = 'DEBUG'
    else:
        level = 'INFO'

    setup_logging(
        level=level,
        include_timestamp=verbose  # Only show timestamps in verbose mode
    )
