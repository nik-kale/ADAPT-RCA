"""
ADAPT-RCA: Adaptive Diagnostic Agent for Proactive Troubleshooting – Root Cause Analyzer.
"""
from .version import __version__, VERSION_INFO, get_version, get_version_info
from .logging_context import (
    get_logger,
    set_context,
    get_context,
    clear_context,
    LoggingContext,
)
from .metrics import (
    track_pool_active_connections,
    track_pool_available_connections,
    track_pool_wait_time,
    track_pool_exhaustion,
    track_rca_duration,
    track_rca_total,
    get_metrics_text,
)

__all__ = [
    "__version__",
    "VERSION_INFO",
    "get_version",
    "get_version_info",
    "get_logger",
    "set_context",
    "get_context",
    "clear_context",
    "LoggingContext",
    "track_pool_active_connections",
    "track_pool_available_connections",
    "track_pool_wait_time",
    "track_pool_exhaustion",
    "track_rca_duration",
    "track_rca_total",
    "get_metrics_text",
]
