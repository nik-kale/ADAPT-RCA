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
    strict: bool = False
) -> Iterable[Dict[str, Any]]:
    """
    Load events from a JSONL (JSON Lines) file.

    Args:
        path: Path to JSONL file
        max_file_size: Maximum allowed file size in bytes
        strict: If True, raise exception on parse errors. If False, skip invalid lines.

    Yields:
        Dictionaries parsed from each JSON line

    Raises:
        PathValidationError: If file is too large
        ValueError: If path is invalid
        json.JSONDecodeError: If strict=True and line parsing fails
    """
    path = Path(path)

    # Validate file size using shared utility
    try:
        validate_file_size(path, max_size_bytes=max_file_size, raise_on_error=True)
    except PathValidationError as e:
        raise ValueError(str(e)) from e

    file_size = get_file_size(path)
    logger.debug(f"Loading JSONL file: {path} ({format_bytes(file_size)})")

    line_number = 0
    valid_lines = 0
    skipped_lines = 0

    try:
        with path.open(encoding='utf-8') as f:
            for line in f:
                line_number += 1
                line = line.strip()

                # Skip empty lines
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    valid_lines += 1
                    yield data
                except json.JSONDecodeError as e:
                    skipped_lines += 1
                    if strict:
                        logger.error(f"JSON parse error at line {line_number}: {e}")
                        raise
                    else:
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
