"""File loading utilities for ADAPT-RCA.

This module provides functions for loading event data from various file formats.
All loaders perform validation, error handling, and provide detailed logging.

Functions:
    load_jsonl: Load events from JSONL (JSON Lines) format files.

Example:
    >>> from adapt_rca.ingestion.file_loader import load_jsonl
    >>> events = list(load_jsonl("logs/events.jsonl"))
    >>> print(f"Loaded {len(events)} events")
"""
from pathlib import Path
from typing import Iterable, Dict, Any
import json
import logging

from ..utils import validate_file_size, get_file_size, format_bytes, PathValidationError
from ..constants import MAX_FILE_SIZE_BYTES

logger = logging.getLogger(__name__)


def load_jsonl(
    path: str | Path,
    max_file_size: int = MAX_FILE_SIZE_BYTES,
    strict: bool = False,
    buffer_size: int = 8192,
    progress_every: int = 10000
) -> Iterable[Dict[str, Any]]:
    """Load events from a JSONL (JSON Lines) file with chunked reading.

    Reads a file where each line contains a separate JSON object representing
    an event. Uses buffered reading for improved I/O performance on large files.
    Validates file size, handles encoding errors, and optionally skips malformed
    lines in non-strict mode.

    Args:
        path: Path to JSONL file (string or Path object).
        max_file_size: Maximum allowed file size in bytes. Default is from
            constants.MAX_FILE_SIZE_BYTES (100MB).
        strict: If True, raise exception on parse errors. If False, skip
            invalid lines with a warning. Default is False.
        buffer_size: Buffer size in bytes for file reading. Default is 8KB.
            Larger buffers improve performance for large files.
        progress_every: Log progress every N lines. Default is 10000.
            Set to 0 to disable progress logging.

    Yields:
        Dictionary objects parsed from each valid JSON line.

    Raises:
        PathValidationError: If file exceeds max_file_size.
        ValueError: If path is invalid or encoding errors occur.
        json.JSONDecodeError: If strict=True and line parsing fails.

    Example:
        >>> # Load with default settings (lenient)
        >>> events = list(load_jsonl("events.jsonl"))
        >>>
        >>> # Load in strict mode (fail on errors)
        >>> events = list(load_jsonl("events.jsonl", strict=True))
        >>>
        >>> # Load with custom size limit and larger buffer (10MB file, 64KB buffer)
        >>> events = list(load_jsonl("events.jsonl", max_file_size=10*1024*1024, buffer_size=65536))
    """
    path = Path(path)

    # Validate file size using shared utility
    try:
        validate_file_size(path, max_size_bytes=max_file_size, raise_on_error=True)
    except PathValidationError as e:
        raise ValueError(str(e)) from e

    file_size = get_file_size(path)
    logger.debug(f"Loading JSONL file: {path} ({format_bytes(file_size)}) with {format_bytes(buffer_size)} buffer")

    line_number = 0
    valid_lines = 0
    skipped_lines = 0

    try:
        # Use buffering for better I/O performance on large files
        with path.open(encoding='utf-8', buffering=buffer_size) as f:
            for line in f:
                line_number += 1
                line = line.strip()

                # Skip empty lines
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    valid_lines += 1

                    # Log progress for large files
                    if progress_every > 0 and valid_lines % progress_every == 0:
                        logger.info(f"Progress: Loaded {valid_lines} events...")

                    yield data
                except json.JSONDecodeError as e:
                    skipped_lines += 1
                    if strict:
                        logger.error(f"JSON parse error at line {line_number}: {e}")
                        raise
                    else:
                        # Only log first few errors to avoid spam
                        if skipped_lines <= 5:
                            logger.warning(
                                f"Skipping invalid JSON at line {line_number}: {e.msg}"
                            )
                        continue

    except UnicodeDecodeError as e:
        logger.error(f"File encoding error: {e}")
        raise ValueError(f"File encoding error. Expected UTF-8: {e}") from e

    logger.info(
        f"Loaded {valid_lines} events from {line_number} lines "
        f"({skipped_lines} skipped)"
    )
