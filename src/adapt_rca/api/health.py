"""
Health check API endpoints.

Provides health and readiness checks for monitoring.
"""

import time
from typing import Dict

# Track server start time
_start_time = time.time()


def get_health_status() -> Dict:
    """
    Get health check status.

    Returns:
        Health status dictionary
    """
    uptime = time.time() - _start_time

    return {
        "status": "healthy",
        "uptime_seconds": round(uptime, 2),
        "service": "adapt-rca",
        "version": "5.0.0-alpha"
    }


def get_readiness_status() -> Dict:
    """
    Get readiness check status.

    Checks if service is ready to handle requests.

    Returns:
        Readiness status dictionary
    """
    # In production, check database connections, etc.
    checks = {
        "database": True,  # Placeholder
        "cache": True,  # Placeholder
    }

    is_ready = all(checks.values())

    return {
        "status": "ready" if is_ready else "not_ready",
        "checks": checks
    }


def get_version_info() -> Dict:
    """
    Get version information.

    Returns:
        Version information dictionary
    """
    return {
        "version": "5.0.0-alpha",
        "api_version": "v1",
        "platform": "ADAPT-RCA"
    }

