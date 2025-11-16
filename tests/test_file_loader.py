"""
Tests for file loading functionality.
"""
import pytest
from pathlib import Path
import json

from adapt_rca.ingestion.file_loader import load_jsonl


def test_load_jsonl_valid(tmp_path: Path) -> None:
    """Test loading valid JSONL file."""
    test_file = tmp_path / "test.jsonl"
    data = [
        {"timestamp": "2025-11-16T10:00:00Z", "message": "Event 1"},
        {"timestamp": "2025-11-16T10:01:00Z", "message": "Event 2"}
    ]

    with test_file.open('w') as f:
        for item in data:
            f.write(json.dumps(item) + '\n')

    events = list(load_jsonl(test_file))

    assert len(events) == 2
    assert events[0]["message"] == "Event 1"
    assert events[1]["message"] == "Event 2"


def test_load_jsonl_with_empty_lines(tmp_path: Path) -> None:
    """Test loading JSONL file with empty lines."""
    test_file = tmp_path / "test.jsonl"

    with test_file.open('w') as f:
        f.write('{"message": "Event 1"}\n')
        f.write('\n')  # Empty line
        f.write('{"message": "Event 2"}\n')
        f.write('   \n')  # Whitespace line

    events = list(load_jsonl(test_file))

    assert len(events) == 2


def test_load_jsonl_with_invalid_json(tmp_path: Path) -> None:
    """Test loading JSONL file with invalid JSON (non-strict mode)."""
    test_file = tmp_path / "test.jsonl"

    with test_file.open('w') as f:
        f.write('{"message": "Valid"}\n')
        f.write('invalid json\n')
        f.write('{"message": "Also valid"}\n')

    events = list(load_jsonl(test_file, strict=False))

    assert len(events) == 2
    assert events[0]["message"] == "Valid"
    assert events[1]["message"] == "Also valid"


def test_load_jsonl_strict_mode_invalid_json(tmp_path: Path) -> None:
    """Test loading JSONL file with invalid JSON in strict mode."""
    test_file = tmp_path / "test.jsonl"

    with test_file.open('w') as f:
        f.write('{"message": "Valid"}\n')
        f.write('invalid json\n')

    with pytest.raises(json.JSONDecodeError):
        list(load_jsonl(test_file, strict=True))


def test_load_jsonl_file_too_large(tmp_path: Path) -> None:
    """Test loading file that exceeds size limit."""
    test_file = tmp_path / "large.jsonl"

    with test_file.open('w') as f:
        f.write('{"test": "data"}\n')

    # Set very small size limit
    with pytest.raises(ValueError, match="File too large"):
        list(load_jsonl(test_file, max_file_size=5))


def test_load_jsonl_utf8_encoding(tmp_path: Path) -> None:
    """Test loading JSONL file with UTF-8 characters."""
    test_file = tmp_path / "utf8.jsonl"

    with test_file.open('w', encoding='utf-8') as f:
        f.write('{"message": "Hello 世界"}\n')
        f.write('{"message": "Émojis: 🎉"}\n')

    events = list(load_jsonl(test_file))

    assert len(events) == 2
    assert "世界" in events[0]["message"]
    assert "🎉" in events[1]["message"]
