"""
ADAPT-RCA: Adaptive Diagnostic Agent for Proactive Troubleshooting – Root Cause Analyzer.
"""
from .metrics import (
    track_pool_active_connections,
    track_pool_available_connections,
    track_pool_wait_time,
    track_pool_exhaustion,
    track_rca_duration,
    track_rca_total,
    get_metrics_text,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "track_pool_active_connections",
    "track_pool_available_connections",
    "track_pool_wait_time",
    "track_pool_exhaustion",
    "track_rca_duration",
    "track_rca_total",
    "get_metrics_text",
]
