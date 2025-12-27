"""
Structured logging with correlation IDs for distributed tracing.

This module provides context-aware logging that automatically includes
correlation IDs (request_id, tenant_id, user_id) in all log messages.
"""

import contextvars
import logging
import json
from typing import Any, Optional
from datetime import datetime

# Context variables for storing request context across async boundaries
request_context: contextvars.ContextVar[dict] = contextvars.ContextVar(
    'request_context', default={}
)


class ContextualLogger(logging.LoggerAdapter):
    """
    Logger adapter that automatically injects correlation IDs into log records.

    Usage:
        logger = get_logger(__name__)
        with set_context(request_id='abc-123', tenant_id='tenant-1'):
            logger.info("Processing request")
            # Logs: {"message": "Processing request", "request_id": "abc-123", ...}
    """

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        """Inject context variables into log extra fields."""
        ctx = request_context.get({})
        extra = kwargs.get('extra', {})

        # Merge context into extra fields
        extra.update({
            'request_id': ctx.get('request_id'),
            'tenant_id': ctx.get('tenant_id'),
            'user_id': ctx.get('user_id'),
            'incident_id': ctx.get('incident_id'),
            'timestamp': datetime.utcnow().isoformat(),
        })

        # Remove None values
        extra = {k: v for k, v in extra.items() if v is not None}

        kwargs['extra'] = extra
        return msg, kwargs


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Outputs log records as JSON objects with consistent fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.utcfromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add extra fields from context
        for key in ['request_id', 'tenant_id', 'user_id', 'incident_id']:
            if hasattr(record, key):
                log_data[key] = getattr(record, key)

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def get_logger(name: str, use_json: bool = False) -> ContextualLogger:
    """
    Get a contextual logger instance.

    Args:
        name: Logger name (typically __name__)
        use_json: Whether to use JSON formatting

    Returns:
        ContextualLogger instance
    """
    base_logger = logging.getLogger(name)

    if use_json and not base_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        base_logger.addHandler(handler)
        base_logger.setLevel(logging.INFO)

    return ContextualLogger(base_logger, {})


def set_context(**kwargs: Any) -> contextvars.Token:
    """
    Set request context for correlation.

    Args:
        **kwargs: Context values (request_id, tenant_id, user_id, etc.)

    Returns:
        Token to reset context later

    Usage:
        token = set_context(request_id='abc-123', tenant_id='tenant-1')
        try:
            # ... do work ...
        finally:
            request_context.reset(token)
    """
    current = request_context.get({}).copy()
    current.update(kwargs)
    return request_context.set(current)


def get_context() -> dict:
    """Get current request context."""
    return request_context.get({}).copy()


def clear_context() -> None:
    """Clear request context."""
    request_context.set({})


class LoggingContext:
    """
    Context manager for setting logging context.

    Usage:
        with LoggingContext(request_id='abc-123'):
            logger.info("Processing")  # Includes request_id
    """

    def __init__(self, **kwargs: Any):
        self.kwargs = kwargs
        self.token: Optional[contextvars.Token] = None

    def __enter__(self):
        self.token = set_context(**self.kwargs)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            request_context.reset(self.token)
        return False

