"""
CSV log file loader.
"""
import csv
import logging
from pathlib import Path
from typing import Iterable, Dict, Any, List, Optional

from ..utils import get_file_size, format_bytes

logger = logging.getLogger(__name__)

# Maximum file size: 100MB by default
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024


def load_csv(
    path: str | Path,
    max_file_size: int = MAX_FILE_SIZE_BYTES,
    field_mapping: Optional[Dict[str, str]] = None,
    delimiter: str = ',',
    has_header: bool = True
) -> Iterable[Dict[str, Any]]:
    """
    Load events from a CSV file.

    Args:
        path: Path to CSV file
        max_file_size: Maximum allowed file size in bytes
        field_mapping: Map CSV columns to event fields
            e.g., {"timestamp_col": "timestamp", "service_col": "service"}
        delimiter: CSV delimiter character
        has_header: Whether the CSV has a header row

    Yields:
        Dictionaries parsed from each CSV row

    Raises:
        ValueError: If file is too large or path is invalid
    """
    path = Path(path)

    # Check file size
    file_size = get_file_size(path)
    if file_size > max_file_size:
        raise ValueError(
            f"File too large: {format_bytes(file_size)} "
            f"(max: {format_bytes(max_file_size)})"
        )

    logger.debug(f"Loading CSV file: {path} ({format_bytes(file_size)})")

    # Default field mapping if none provided
    if field_mapping is None:
        field_mapping = {
            "timestamp": "timestamp",
            "service": "service",
            "level": "level",
            "message": "message",
            "severity": "level",
            "component": "service"
        }

    row_number = 0
    valid_rows = 0

    try:
        with path.open(encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f, delimiter=delimiter) if has_header else csv.reader(f, delimiter=delimiter)

            for row in reader:
                row_number += 1

                if has_header:
                    # Map CSV fields to event fields
                    event = {}
                    for csv_field, event_field in field_mapping.items():
                        if csv_field in row and row[csv_field]:
                            event[event_field] = row[csv_field]

                    if event:  # Only yield if we got some data
                        valid_rows += 1
                        yield event
                else:
                    # Without header, assume standard order: timestamp, service, level, message
                    if len(row) >= 4:
                        valid_rows += 1
                        yield {
                            "timestamp": row[0],
                            "service": row[1],
                            "level": row[2],
                            "message": row[3]
                        }

    except UnicodeDecodeError as e:
        logger.error(f"File encoding error: {e}")
        raise ValueError(f"File encoding error. Expected UTF-8: {e}") from e

    logger.info(f"Loaded {valid_rows} events from {row_number} rows")
