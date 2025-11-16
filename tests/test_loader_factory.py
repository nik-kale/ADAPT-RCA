"""
Tests for file loader factory.
"""
import pytest
from pathlib import Path
from adapt_rca.ingestion.loader_factory import (
    FileLoaderFactory,
    JSONLLoader,
    CSVLoader,
    TextLoader
)


def test_get_loader_jsonl():
    """Test getting JSONL loader."""
    loader = FileLoaderFactory.get_loader('jsonl')
    assert isinstance(loader, JSONLLoader)


def test_get_loader_csv():
    """Test getting CSV loader."""
    loader = FileLoaderFactory.get_loader('csv')
    assert isinstance(loader, CSVLoader)


def test_get_loader_text():
    """Test getting text loader."""
    loader = FileLoaderFactory.get_loader('text')
    assert isinstance(loader, TextLoader)


def test_get_loader_invalid_format():
    """Test error on unsupported format."""
    with pytest.raises(ValueError, match="Unsupported format"):
        FileLoaderFactory.get_loader('invalid_format')


def test_get_loader_for_file_jsonl():
    """Test auto-detection for JSONL files."""
    loader = FileLoaderFactory.get_loader_for_file('events.jsonl')
    assert isinstance(loader, JSONLLoader)


def test_get_loader_for_file_csv():
    """Test auto-detection for CSV files."""
    loader = FileLoaderFactory.get_loader_for_file('data.csv')
    assert isinstance(loader, CSVLoader)


def test_get_loader_for_file_log():
    """Test auto-detection for log files."""
    loader = FileLoaderFactory.get_loader_for_file('app.log')
    assert isinstance(loader, TextLoader)


def test_get_loader_for_file_unknown():
    """Test fallback to TextLoader for unknown extensions."""
    loader = FileLoaderFactory.get_loader_for_file('data.unknown')
    assert isinstance(loader, TextLoader)


def test_list_supported_formats():
    """Test listing supported formats."""
    formats = FileLoaderFactory.list_supported_formats()

    assert 'jsonl' in formats
    assert 'csv' in formats
    assert 'text' in formats

    assert '.jsonl' in formats['jsonl']
    assert '.csv' in formats['csv']
    assert '.log' in formats['text']


def test_register_custom_loader():
    """Test registering a custom loader."""
    from adapt_rca.ingestion.loader_factory import FileLoader

    class CustomLoader(FileLoader):
        def load(self, path, **kwargs):
            return []

        @property
        def supported_extensions(self):
            return ['.custom']

    # Register custom loader
    FileLoaderFactory.register_loader('custom', CustomLoader())

    # Verify it's registered
    loader = FileLoaderFactory.get_loader('custom')
    assert isinstance(loader, CustomLoader)

    # Verify it works with file auto-detection
    loader = FileLoaderFactory.get_loader_for_file('data.custom')
    assert isinstance(loader, CustomLoader)
