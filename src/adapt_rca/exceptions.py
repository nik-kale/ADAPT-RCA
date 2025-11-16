"""
Custom exceptions for ADAPT-RCA.

This module defines a hierarchy of custom exceptions for consistent error handling
throughout the application.
"""


class AdaptRCAError(Exception):
    """Base exception for all ADAPT-RCA errors."""
    pass


# Configuration and validation errors
class ConfigurationError(AdaptRCAError):
    """Raised when configuration is invalid."""
    pass


class ValidationError(AdaptRCAError):
    """Raised when data validation fails."""
    pass


# File handling errors
class FileProcessingError(AdaptRCAError):
    """Base exception for file processing errors."""
    pass


class FileTooLargeError(FileProcessingError):
    """Raised when file exceeds size limit."""

    def __init__(self, file_size: int, max_size: int, file_path: str = ""):
        self.file_size = file_size
        self.max_size = max_size
        self.file_path = file_path
        super().__init__(
            f"File size {file_size} bytes exceeds maximum {max_size} bytes"
            + (f": {file_path}" if file_path else "")
        )


class UnsupportedFormatError(FileProcessingError):
    """Raised when file format is not supported."""
    pass


class ParseError(FileProcessingError):
    """Raised when file parsing fails."""
    pass


# Analysis errors
class AnalysisError(AdaptRCAError):
    """Base exception for analysis errors."""
    pass


class InsufficientDataError(AnalysisError):
    """Raised when there's not enough data to perform analysis."""

    def __init__(self, message: str = "Insufficient data for analysis"):
        super().__init__(message)


class GraphBuildError(AnalysisError):
    """Raised when causal graph construction fails."""
    pass


# LLM errors
class LLMError(AdaptRCAError):
    """Base exception for LLM-related errors."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM API call times out."""

    def __init__(self, timeout: int, provider: str = ""):
        self.timeout = timeout
        self.provider = provider
        super().__init__(
            f"LLM API timeout after {timeout} seconds"
            + (f" ({provider})" if provider else "")
        )


class LLMProviderError(LLMError):
    """Raised when LLM provider is not available or configured incorrectly."""
    pass


class LLMRateLimitError(LLMError):
    """Raised when LLM API rate limit is exceeded."""

    def __init__(self, retry_after: int = None):
        self.retry_after = retry_after
        msg = "LLM API rate limit exceeded"
        if retry_after:
            msg += f". Retry after {retry_after} seconds"
        super().__init__(msg)


# Export errors
class ExportError(AdaptRCAError):
    """Raised when export operation fails."""
    pass


# Web/API errors
class WebError(AdaptRCAError):
    """Base exception for web interface errors."""
    pass


class UploadError(WebError):
    """Raised when file upload fails."""
    pass
