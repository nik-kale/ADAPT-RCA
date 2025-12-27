"""
Version information for ADAPT-RCA.

This module provides a single source of truth for version information
across the entire codebase.
"""

__version__ = "5.0.0-alpha"

VERSION_INFO = {
    "version": __version__,
    "api_version": "v1",
    "platform": "ADAPT",
    "name": "ADAPT-RCA",
    "full_name": "Adaptive Diagnostic Agent for Proactive Troubleshooting - Root Cause Analyzer",
}


def get_version() -> str:
    """Return the current version string."""
    return __version__


def get_version_info() -> dict:
    """Return detailed version information."""
    return VERSION_INFO.copy()

