"""
Text and syslog file loader.
"""
import re
import logging
from pathlib import Path
from typing import Iterable, Dict, Any, Optional, Pattern
from datetime import datetime

from ..utils import validate_file_size, get_file_size, format_bytes, PathValidationError
from ..constants import MAX_FILE_SIZE_BYTES
from ..security.sanitization import validate_regex_safety

logger = logging.getLogger(__name__)

# Common log patterns
SYSLOG_PATTERN = re.compile(
    r'^(?P<timestamp>\w+\s+\d+\s+\d+:\d+:\d+)\s+'
    r'(?P<host>\S+)\s+'
    r'(?P<service>\S+?)(\[(?P<pid>\d+)\])?\s*:\s*'
    r'(?P<message>.+)$'
)

NGINX_PATTERN = re.compile(
    r'^(?P<ip>\S+)\s+-\s+\S+\s+\[(?P<timestamp>[^\]]+)\]\s+'
    r'"(?P<method>\S+)\s+(?P<path>\S+)\s+\S+"\s+'
    r'(?P<status>\d+)\s+(?P<size>\d+)'
)

APACHE_PATTERN = re.compile(
    r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<timestamp>[^\]]+)\]\s+'
    r'"(?P<method>\S+)\s+(?P<path>\S+)\s+\S+"\s+'
    r'(?P<status>\d+)\s+(?P<size>\S+)'
)

# Generic log pattern (timestamp + level + message)
GENERIC_PATTERN = re.compile(
    r'^(?P<timestamp>\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}[^\s]*)\s+'
    r'\[?(?P<level>DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL|FATAL)\]?\s*'
    r'(?:\[(?P<service>[^\]]+)\]\s*)?'
    r'(?P<message>.+)$',
    re.IGNORECASE
)


def load_text_log(
    path: str | Path,
    max_file_size: int = MAX_FILE_SIZE_BYTES,
    log_format: str = "auto",
    custom_pattern: Optional[str] = None
) -> Iterable[Dict[str, Any]]:
    """
    Load events from a text log file.

    Supports multiple log formats:
    - syslog: Standard syslog format
    - nginx: Nginx access logs
    - apache: Apache access logs
    - generic: Generic timestamp + level + message format
    - auto: Automatically detect format (default)

    Args:
        path: Path to log file
        max_file_size: Maximum allowed file size in bytes
        log_format: Log format to parse ("auto", "syslog", "nginx", "apache", "generic")
        custom_pattern: Custom regex pattern with named groups

    Yields:
        Dictionaries parsed from each log line

    Raises:
        PathValidationError: If file is too large
        ValueError: If invalid format or path
    """
    path = Path(path)

    # Validate file size using shared utility
    try:
        validate_file_size(path, max_size_bytes=max_file_size, raise_on_error=True)
    except PathValidationError as e:
        raise ValueError(str(e)) from e

    file_size = get_file_size(path)
    logger.debug(f"Loading text log file: {path} ({format_bytes(file_size)})")

    # Select pattern
    if custom_pattern:
        # Validate custom pattern for ReDoS vulnerabilities
        try:
            if not validate_regex_safety(custom_pattern, timeout=1.0):
                raise ValueError(
                    f"Custom regex pattern appears unsafe (potential ReDoS): {custom_pattern[:50]}"
                )
        except ValueError as e:
            # Re-raise validation errors
            raise ValueError(f"Unsafe regex pattern: {e}") from e
        except Exception as e:
            logger.warning(f"Could not validate regex pattern safety: {e}")
            # Allow it but log warning

        try:
            pattern = re.compile(custom_pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}") from e
    elif log_format == "syslog":
        pattern = SYSLOG_PATTERN
    elif log_format == "nginx":
        pattern = NGINX_PATTERN
    elif log_format == "apache":
        pattern = APACHE_PATTERN
    elif log_format == "generic":
        pattern = GENERIC_PATTERN
    else:  # auto
        pattern = None  # Will try multiple patterns

    line_number = 0
    parsed_lines = 0
    skipped_lines = 0

    try:
        with path.open(encoding='utf-8') as f:
            for line in f:
                line_number += 1
                line = line.strip()

                if not line or line.startswith('#'):  # Skip empty and comment lines
                    continue

                event = None

                if pattern:
                    # Use specified pattern
                    event = _parse_line_with_pattern(line, pattern)
                else:
                    # Auto-detect: try multiple patterns
                    for p in [SYSLOG_PATTERN, GENERIC_PATTERN, NGINX_PATTERN, APACHE_PATTERN]:
                        event = _parse_line_with_pattern(line, p)
                        if event:
                            break

                if event:
                    parsed_lines += 1
                    yield event
                else:
                    skipped_lines += 1
                    if skipped_lines <= 5:  # Log first few unparseable lines
                        logger.debug(f"Could not parse line {line_number}: {line[:100]}")

    except UnicodeDecodeError as e:
        logger.error(f"File encoding error: {e}")
        raise ValueError(f"File encoding error. Expected UTF-8: {e}") from e

    logger.info(
        f"Loaded {parsed_lines} events from {line_number} lines "
        f"({skipped_lines} skipped)"
    )


def _parse_line_with_pattern(line: str, pattern: Pattern) -> Optional[Dict[str, Any]]:
    """
    Parse a log line with the given regex pattern.

    Args:
        line: Log line to parse
        pattern: Compiled regex pattern

    Returns:
        Parsed event dict or None if no match
    """
    match = pattern.match(line)
    if not match:
        return None

    event = match.groupdict()

    # Infer log level from HTTP status codes
    if 'status' in event and 'level' not in event:
        status = int(event['status'])
        if status >= 500:
            event['level'] = 'ERROR'
        elif status >= 400:
            event['level'] = 'WARN'
        else:
            event['level'] = 'INFO'

    # Set service from various possible fields
    if 'service' not in event or not event['service']:
        if 'host' in event:
            event['service'] = event['host']
        elif 'path' in event:
            # Use path as service for web logs
            event['service'] = 'web'

    # Construct message if not present
    if 'message' not in event:
        if 'method' in event and 'path' in event:
            event['message'] = f"{event.get('method')} {event.get('path')} - {event.get('status')}"
        else:
            # Use the whole line as message
            event['message'] = line

    # Remove None values
    event = {k: v for k, v in event.items() if v is not None}

    return event
