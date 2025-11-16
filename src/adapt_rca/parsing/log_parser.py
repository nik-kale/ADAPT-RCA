"""Log parsing and event normalization utilities.

This module provides utilities for parsing and normalizing log events from
various sources into a common schema. The normalization process handles
different log formats and field naming conventions.

Functions:
    normalize_event: Normalize a raw log record into a common event schema.

Example:
    >>> from adapt_rca.parsing.log_parser import normalize_event
    >>> raw_log = {
    ...     "timestamp": "2024-01-01T10:00:00Z",
    ...     "component": "api-gateway",
    ...     "severity": "ERROR",
    ...     "message": "Connection timeout"
    ... }
    >>> normalized = normalize_event(raw_log)
    >>> print(normalized["service"])  # "api-gateway"
"""
from typing import Dict, Any, Optional


def normalize_event(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a raw log record into a common event schema.

    This function transforms log records from various formats into a
    standardized schema. It handles different field naming conventions
    (e.g., "service" vs "component", "level" vs "severity") and preserves
    the original raw data for reference.

    The normalization is intentionally simple to serve as a starting point
    that can be extended for more complex log formats.

    Args:
        raw: Raw log record dictionary with fields that may include:
            - timestamp: Event timestamp (ISO format string or datetime)
            - service or component: Service/component identifier
            - level or severity: Log level (ERROR, WARN, INFO, etc.)
            - message: Log message text

    Returns:
        Normalized event dictionary with keys:
            - timestamp: Event timestamp (preserved as-is)
            - service: Service identifier (from 'service' or 'component' field)
            - level: Log level (from 'level' or 'severity' field)
            - message: Log message text
            - raw: Original raw log record for reference

    Example:
        >>> raw = {
        ...     "timestamp": "2024-01-01T10:00:00Z",
        ...     "component": "database",
        ...     "severity": "ERROR",
        ...     "message": "Query timeout after 30s"
        ... }
        >>> normalized = normalize_event(raw)
        >>> normalized["service"]
        'database'
        >>> normalized["level"]
        'ERROR'
        >>> "raw" in normalized
        True

    Example with alternative field names:
        >>> raw = {
        ...     "timestamp": "2024-01-01T10:05:00Z",
        ...     "service": "api-gateway",
        ...     "level": "WARN",
        ...     "message": "High latency detected"
        ... }
        >>> normalized = normalize_event(raw)
        >>> normalized["service"]
        'api-gateway'
    """
    return {
        "timestamp": raw.get("timestamp"),
        "service": raw.get("service") or raw.get("component"),
        "level": raw.get("level") or raw.get("severity"),
        "message": raw.get("message"),
        "raw": raw,
    }
