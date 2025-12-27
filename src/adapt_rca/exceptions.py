"""
Custom exception types for ADAPT-RCA.

Provides specific exception classes for better error handling and debugging.
"""


class ADAPTError(Exception):
    """Base exception for all ADAPT-RCA errors."""
    pass


# Ingestion errors
class IngestionError(ADAPTError):
    """Base exception for ingestion errors."""
    pass


class FileLoadError(IngestionError):
    """Error loading log file."""
    pass


class InvalidFormatError(IngestionError):
    """Invalid file format."""
    pass


# Parsing errors
class ParsingError(ADAPTError):
    """Base exception for parsing errors."""
    pass


class LogParseError(ParsingError):
    """Error parsing log entry."""
    pass


class ValidationError(ParsingError):
    """Data validation error."""
    pass


# Analysis errors
class AnalysisError(ADAPTError):
    """Base exception for analysis errors."""
    pass


class InsufficientDataError(AnalysisError):
    """Insufficient data for analysis."""
    pass


class IncidentNotFoundError(AnalysisError):
    """Incident not found."""
    pass


# Graph errors
class GraphError(ADAPTError):
    """Base exception for graph operations."""
    pass


class GraphBuildError(GraphError):
    """Error building causal graph."""
    pass


class NodeNotFoundError(GraphError):
    """Graph node not found."""
    pass


# External service errors
class ExternalServiceError(ADAPTError):
    """Base exception for external service errors."""
    pass


class ConnectionError(ExternalServiceError):
    """Connection to external service failed."""
    pass


class TimeoutError(ExternalServiceError):
    """External service request timed out."""
    pass


class AuthenticationError(ExternalServiceError):
    """Authentication with external service failed."""
    pass


class RateLimitError(ExternalServiceError):
    """Rate limit exceeded for external service."""
    pass


# Configuration errors
class ConfigurationError(ADAPTError):
    """Base exception for configuration errors."""
    pass


class InvalidConfigError(ConfigurationError):
    """Invalid configuration."""
    pass


class MissingConfigError(ConfigurationError):
    """Required configuration missing."""
    pass


# API errors
class APIError(ADAPTError):
    """Base exception for API errors."""
    pass


class BadRequestError(APIError):
    """Invalid API request."""
    pass


class UnauthorizedError(APIError):
    """Unauthorized API access."""
    pass


class NotFoundError(APIError):
    """API resource not found."""
    pass


class ConflictError(APIError):
    """API resource conflict."""
    pass


# Export mapping for common usage
__all__ = [
    "ADAPTError",
    "IngestionError",
    "FileLoadError",
    "InvalidFormatError",
    "ParsingError",
    "LogParseError",
    "ValidationError",
    "AnalysisError",
    "InsufficientDataError",
    "IncidentNotFoundError",
    "GraphError",
    "GraphBuildError",
    "NodeNotFoundError",
    "ExternalServiceError",
    "ConnectionError",
    "TimeoutError",
    "AuthenticationError",
    "RateLimitError",
    "ConfigurationError",
    "InvalidConfigError",
    "MissingConfigError",
    "APIError",
    "BadRequestError",
    "UnauthorizedError",
    "NotFoundError",
    "ConflictError",
]

