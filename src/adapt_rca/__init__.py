"""
ADAPT-RCA: Adaptive Diagnostic Agent for Proactive Troubleshooting – Root Cause Analyzer.
"""
from .logging_context import (
    get_logger,
    set_context,
    get_context,
    clear_context,
    LoggingContext,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "get_logger",
    "set_context",
    "get_context",
    "clear_context",
    "LoggingContext",
]
