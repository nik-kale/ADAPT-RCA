"""
Tests for health check API endpoints.

Verifies health, readiness, and version endpoints.
"""

import pytest
from src.adapt_rca.api.health import (
    get_health_status,
    get_readiness_status,
    get_version_info,
)


def test_health_status_returns_healthy():
    """Test health endpoint returns healthy status."""
    health = get_health_status()
    
    assert health["status"] == "healthy"
    assert "uptime_seconds" in health
    assert health["service"] == "adapt-rca"
    assert "version" in health


def test_health_status_includes_uptime():
    """Test health status includes uptime metric."""
    health = get_health_status()
    
    assert "uptime_seconds" in health
    assert isinstance(health["uptime_seconds"], (int, float))
    assert health["uptime_seconds"] >= 0


def test_health_status_format():
    """Test health status has correct format."""
    health = get_health_status()
    
    required_fields = ["status", "uptime_seconds", "service", "version"]
    for field in required_fields:
        assert field in health, f"Missing required field: {field}"


def test_readiness_status_returns_ready():
    """Test readiness endpoint returns ready status."""
    readiness = get_readiness_status()
    
    assert "status" in readiness
    assert readiness["status"] in ["ready", "not_ready"]
    assert "checks" in readiness


def test_readiness_status_includes_checks():
    """Test readiness status includes health checks."""
    readiness = get_readiness_status()
    
    assert "checks" in readiness
    assert isinstance(readiness["checks"], dict)
    
    # Should have some checks
    assert len(readiness["checks"]) > 0


def test_readiness_status_all_checks_pass():
    """Test readiness status when all checks pass."""
    readiness = get_readiness_status()
    
    # In current implementation, all checks should pass
    assert readiness["status"] == "ready"
    assert all(readiness["checks"].values())


def test_version_info_returns_version():
    """Test version endpoint returns version information."""
    version = get_version_info()
    
    assert "version" in version
    assert "api_version" in version
    assert "platform" in version


def test_version_info_format():
    """Test version info has correct format."""
    version = get_version_info()
    
    assert isinstance(version["version"], str)
    assert isinstance(version["api_version"], str)
    assert isinstance(version["platform"], str)


def test_version_info_matches_expected():
    """Test version info matches expected values."""
    version = get_version_info()
    
    assert version["version"] == "5.0.0-alpha"
    assert version["api_version"] == "v1"
    assert version["platform"] == "ADAPT-RCA"


def test_health_status_consistency():
    """Test health status is consistent across calls."""
    health1 = get_health_status()
    health2 = get_health_status()
    
    # Service and version should be the same
    assert health1["service"] == health2["service"]
    assert health1["version"] == health2["version"]
    
    # Uptime should increase
    assert health2["uptime_seconds"] >= health1["uptime_seconds"]


def test_readiness_status_consistency():
    """Test readiness status is consistent across calls."""
    readiness1 = get_readiness_status()
    readiness2 = get_readiness_status()
    
    # Checks structure should be the same
    assert readiness1["checks"].keys() == readiness2["checks"].keys()


def test_version_info_immutable():
    """Test version info doesn't change."""
    version1 = get_version_info()
    version2 = get_version_info()
    
    assert version1 == version2

