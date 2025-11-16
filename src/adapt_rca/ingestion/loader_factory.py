"""
File loader factory for ADAPT-RCA.

This module provides a factory pattern for creating appropriate file loaders
based on file format or auto-detection. This improves extensibility and
makes it easier to add new file formats.

Classes:
    FileLoaderFactory: Factory for creating file loaders based on format.

Example:
    >>> from adapt_rca.ingestion.loader_factory import FileLoaderFactory
    >>> loader = FileLoaderFactory.get_loader('jsonl')
    >>> events = list(loader.load('events.jsonl'))
"""
import logging
from pathlib import Path
from typing import Iterable, Dict, Any, Optional, Callable
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class FileLoader(ABC):
    """Abstract base class for file loaders."""

    @abstractmethod
    def load(
        self,
        path: str | Path,
        **kwargs
    ) -> Iterable[Dict[str, Any]]:
        """
        Load events from file.

        Args:
            path: Path to file
            **kwargs: Additional loader-specific parameters

        Yields:
            Event dictionaries
        """
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        pass


class JSONLLoader(FileLoader):
    """Loader for JSONL (JSON Lines) files."""

    def load(
        self,
        path: str | Path,
        max_file_size: Optional[int] = None,
        strict: bool = False,
        **kwargs
    ) -> Iterable[Dict[str, Any]]:
        """Load events from JSONL file."""
        from .file_loader import load_jsonl
        from ..constants import MAX_FILE_SIZE_BYTES

        return load_jsonl(
            path,
            max_file_size=max_file_size or MAX_FILE_SIZE_BYTES,
            strict=strict
        )

    @property
    def supported_extensions(self) -> list[str]:
        return ['.jsonl', '.json']


class CSVLoader(FileLoader):
    """Loader for CSV files."""

    def load(
        self,
        path: str | Path,
        max_file_size: Optional[int] = None,
        **kwargs
    ) -> Iterable[Dict[str, Any]]:
        """Load events from CSV file."""
        from .csv_loader import load_csv
        from ..constants import MAX_FILE_SIZE_BYTES

        return load_csv(
            path,
            max_file_size=max_file_size or MAX_FILE_SIZE_BYTES
        )

    @property
    def supported_extensions(self) -> list[str]:
        return ['.csv']


class TextLoader(FileLoader):
    """Loader for text/syslog files."""

    def load(
        self,
        path: str | Path,
        max_file_size: Optional[int] = None,
        log_format: str = "auto",
        custom_pattern: Optional[str] = None,
        **kwargs
    ) -> Iterable[Dict[str, Any]]:
        """Load events from text/syslog file."""
        from .text_loader import load_text_log
        from ..constants import MAX_FILE_SIZE_BYTES

        return load_text_log(
            path,
            max_file_size=max_file_size or MAX_FILE_SIZE_BYTES,
            log_format=log_format,
            custom_pattern=custom_pattern
        )

    @property
    def supported_extensions(self) -> list[str]:
        return ['.log', '.txt', '.syslog']


class FileLoaderFactory:
    """
    Factory for creating appropriate file loaders.

    This factory provides a centralized way to get the right loader
    for a given file format, supporting both explicit format specification
    and auto-detection based on file extensions.

    Example:
        >>> # Get loader by format
        >>> loader = FileLoaderFactory.get_loader('jsonl')
        >>> events = list(loader.load('events.jsonl'))
        >>>
        >>> # Auto-detect from file path
        >>> loader = FileLoaderFactory.get_loader_for_file('logs/app.csv')
        >>> events = list(loader.load('logs/app.csv'))
        >>>
        >>> # Register custom loader
        >>> FileLoaderFactory.register_loader('custom', MyCustomLoader())
    """

    _loaders: Dict[str, FileLoader] = {
        'jsonl': JSONLLoader(),
        'json': JSONLLoader(),
        'csv': CSVLoader(),
        'text': TextLoader(),
        'syslog': TextLoader(),
        'generic': TextLoader(),
        'nginx': TextLoader(),
        'apache': TextLoader(),
    }

    @classmethod
    def register_loader(cls, format_name: str, loader: FileLoader) -> None:
        """
        Register a custom file loader.

        Args:
            format_name: Format identifier (e.g., 'xml', 'parquet')
            loader: FileLoader instance

        Example:
            >>> class XMLLoader(FileLoader):
            ...     def load(self, path, **kwargs):
            ...         # Custom XML loading logic
            ...         pass
            ...     @property
            ...     def supported_extensions(self):
            ...         return ['.xml']
            >>>
            >>> FileLoaderFactory.register_loader('xml', XMLLoader())
        """
        cls._loaders[format_name] = loader
        logger.info(f"Registered loader for format: {format_name}")

    @classmethod
    def get_loader(cls, format_name: str) -> FileLoader:
        """
        Get loader for specified format.

        Args:
            format_name: Format identifier ('jsonl', 'csv', 'text', etc.)

        Returns:
            FileLoader instance for the format

        Raises:
            ValueError: If format is not supported

        Example:
            >>> loader = FileLoaderFactory.get_loader('jsonl')
            >>> events = list(loader.load('events.jsonl'))
        """
        if format_name not in cls._loaders:
            supported = ', '.join(sorted(cls._loaders.keys()))
            raise ValueError(
                f"Unsupported format: '{format_name}'. "
                f"Supported formats: {supported}"
            )

        return cls._loaders[format_name]

    @classmethod
    def get_loader_for_file(cls, file_path: str | Path) -> FileLoader:
        """
        Auto-detect and get appropriate loader for file.

        Determines the appropriate loader based on file extension.
        Falls back to TextLoader if extension is not recognized.

        Args:
            file_path: Path to file

        Returns:
            FileLoader instance appropriate for the file

        Example:
            >>> loader = FileLoaderFactory.get_loader_for_file('logs/app.csv')
            >>> isinstance(loader, CSVLoader)
            True
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        # Try to find loader by extension
        for loader in cls._loaders.values():
            if ext in loader.supported_extensions:
                logger.debug(f"Auto-detected loader for {ext}: {type(loader).__name__}")
                return loader

        # Default to text loader for unknown extensions
        logger.debug(f"No specific loader for {ext}, using TextLoader")
        return cls._loaders['text']

    @classmethod
    def list_supported_formats(cls) -> Dict[str, list[str]]:
        """
        List all supported formats and their file extensions.

        Returns:
            Dictionary mapping format names to list of supported extensions

        Example:
            >>> formats = FileLoaderFactory.list_supported_formats()
            >>> 'jsonl' in formats
            True
            >>> '.csv' in formats['csv']
            True
        """
        formats = {}
        for name, loader in cls._loaders.items():
            formats[name] = loader.supported_extensions
        return formats
