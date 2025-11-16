"""
Utility functions for ADAPT-RCA.
"""
import logging
import os
from pathlib import Path
from typing import Optional

from .constants import MAX_FILE_SIZE_BYTES

logger = logging.getLogger(__name__)


class PathValidationError(Exception):
    """Raised when path validation fails."""
    pass


def validate_input_path(path: str | Path) -> Path:
    """
    Validate that an input file path is safe and exists.

    Args:
        path: Path to validate

    Returns:
        Resolved Path object

    Raises:
        PathValidationError: If path is invalid or doesn't exist
    """
    try:
        path_obj = Path(path).resolve()
    except (ValueError, OSError) as e:
        raise PathValidationError(f"Invalid input path: {e}") from e

    if not path_obj.exists():
        raise PathValidationError(f"Input file does not exist: {path_obj}")

    if not path_obj.is_file():
        raise PathValidationError(f"Input path is not a file: {path_obj}")

    # Check for suspicious patterns
    if ".." in str(path):
        logger.warning(f"Path contains '..' but resolved to: {path_obj}")

    return path_obj


def validate_output_path(
    path: str | Path,
    allow_overwrite: bool = True,
    allowed_extensions: Optional[set[str]] = None
) -> Path:
    """
    Validate that an output file path is safe.

    Args:
        path: Path to validate
        allow_overwrite: Whether to allow overwriting existing files
        allowed_extensions: Set of allowed file extensions (e.g., {'.json', '.md'})

    Returns:
        Resolved Path object

    Raises:
        PathValidationError: If path is invalid or unsafe
    """
    try:
        path_obj = Path(path).resolve()
    except (ValueError, OSError) as e:
        raise PathValidationError(f"Invalid output path: {e}") from e

    # Check file extension
    if allowed_extensions and path_obj.suffix not in allowed_extensions:
        raise PathValidationError(
            f"Invalid file extension '{path_obj.suffix}'. "
            f"Allowed: {', '.join(sorted(allowed_extensions))}"
        )

    # Check if file exists and overwrite is not allowed
    if path_obj.exists() and not allow_overwrite:
        raise PathValidationError(f"Output file already exists: {path_obj}")

    # Ensure parent directory exists
    parent = path_obj.parent
    if not parent.exists():
        raise PathValidationError(f"Parent directory does not exist: {parent}")

    if not parent.is_dir():
        raise PathValidationError(f"Parent path is not a directory: {parent}")

    # Check write permissions
    if not os.access(parent, os.W_OK):
        raise PathValidationError(f"No write permission for directory: {parent}")

    # Warn about suspicious patterns
    if ".." in str(path):
        logger.warning(f"Output path contains '..' but resolved to: {path_obj}")

    return path_obj


def get_file_size(path: Path) -> int:
    """
    Get file size in bytes.

    Args:
        path: File path

    Returns:
        File size in bytes
    """
    return path.stat().st_size


def format_bytes(size: int) -> str:
    """
    Format bytes to human-readable string.

    Args:
        size: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def validate_file_size(
    path: Path,
    max_size_bytes: int = MAX_FILE_SIZE_BYTES,
    raise_on_error: bool = True
) -> bool:
    """
    Validate that a file size is within acceptable limits.

    Args:
        path: Path to file
        max_size_bytes: Maximum allowed file size in bytes
        raise_on_error: Whether to raise exception on validation failure

    Returns:
        True if file size is acceptable, False otherwise

    Raises:
        PathValidationError: If file is too large and raise_on_error is True
    """
    file_size = get_file_size(path)

    if file_size > max_size_bytes:
        msg = (
            f"File size {format_bytes(file_size)} exceeds maximum "
            f"allowed size of {format_bytes(max_size_bytes)}: {path}"
        )
        logger.warning(msg)

        if raise_on_error:
            raise PathValidationError(msg)
        return False

    logger.debug(f"File size validation passed: {format_bytes(file_size)}")
    return True
