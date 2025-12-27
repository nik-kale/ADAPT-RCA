"""
Tests for utility functions.
"""
import pytest
from pathlib import Path
import tempfile
import os

from adapt_rca.utils import (
    validate_input_path,
    validate_output_path,
    PathValidationError,
    get_file_size,
    format_bytes
)


def test_validate_input_path_valid(tmp_path: Path) -> None:
    """Test input path validation with valid file."""
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"test": "data"}')

    result = validate_input_path(test_file)
    assert result.exists()
    assert result.is_file()


def test_validate_input_path_missing() -> None:
    """Test input path validation with missing file."""
    with pytest.raises(PathValidationError, match="does not exist"):
        validate_input_path("/nonexistent/file.jsonl")


def test_validate_input_path_directory(tmp_path: Path) -> None:
    """Test input path validation with directory instead of file."""
    with pytest.raises(PathValidationError, match="not a file"):
        validate_input_path(tmp_path)


def test_validate_output_path_valid(tmp_path: Path) -> None:
    """Test output path validation with valid path."""
    output_file = tmp_path / "output.json"

    result = validate_output_path(output_file, allowed_extensions={'.json'})
    assert result.parent == tmp_path


def test_validate_output_path_invalid_extension(tmp_path: Path) -> None:
    """Test output path validation with invalid extension."""
    output_file = tmp_path / "output.txt"

    with pytest.raises(PathValidationError, match="Invalid file extension"):
        validate_output_path(output_file, allowed_extensions={'.json', '.md'})


def test_validate_output_path_existing_no_overwrite(tmp_path: Path) -> None:
    """Test output path validation with existing file and overwrite disabled."""
    output_file = tmp_path / "existing.json"
    output_file.write_text('{"existing": "data"}')

    with pytest.raises(PathValidationError, match="already exists"):
        validate_output_path(output_file, allow_overwrite=False)


def test_validate_output_path_existing_allow_overwrite(tmp_path: Path) -> None:
    """Test output path validation with existing file and overwrite enabled."""
    output_file = tmp_path / "existing.json"
    output_file.write_text('{"existing": "data"}')

    result = validate_output_path(output_file, allow_overwrite=True)
    assert result.exists()


def test_validate_output_path_missing_parent() -> None:
    """Test output path validation with missing parent directory."""
    with pytest.raises(PathValidationError, match="Parent directory does not exist"):
        validate_output_path("/nonexistent/dir/file.json")


def test_get_file_size(tmp_path: Path) -> None:
    """Test file size calculation."""
    test_file = tmp_path / "test.txt"
    content = "Hello, World!"
    test_file.write_text(content)

    size = get_file_size(test_file)
    assert size == len(content)


def test_format_bytes() -> None:
    """Test byte formatting."""
    assert format_bytes(0) == "0.00 B"
    assert format_bytes(512) == "512.00 B"
    assert format_bytes(1024) == "1.00 KB"
    assert format_bytes(1024 * 1024) == "1.00 MB"
    assert format_bytes(1024 * 1024 * 1024) == "1.00 GB"
    assert format_bytes(1024 * 1024 * 1024 * 1024) == "1.00 TB"


def test_format_bytes_fractional() -> None:
    """Test byte formatting with fractional values."""
    assert format_bytes(1536) == "1.50 KB"  # 1.5 KB
    assert format_bytes(2.5 * 1024 * 1024) == "2.50 MB"  # 2.5 MB
