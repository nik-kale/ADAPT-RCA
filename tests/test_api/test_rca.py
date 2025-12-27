"""
Tests for RCA API endpoints.

Verifies RCA request processing and response format.
"""

import pytest
from src.adapt_rca.api.rca import (
    RCARequest,
    process_rca_request,
    get_rca_status,
)


def test_rca_request_creation():
    """Test RCA request creation."""
    events = [{"service": "api", "level": "error"}]
    request = RCARequest(events)
    
    assert request.events == events
    assert request.incident_id is not None
    assert request.timestamp is not None


def test_rca_request_with_incident_id():
    """Test RCA request with custom incident ID."""
    events = [{"service": "api"}]
    incident_id = "custom-incident-123"
    request = RCARequest(events, incident_id)
    
    assert request.incident_id == incident_id


def test_rca_request_validation_empty_events():
    """Test validation fails for empty events."""
    request = RCARequest([])
    is_valid, error = request.validate()
    
    assert not is_valid
    assert "empty" in error.lower()


def test_rca_request_validation_invalid_events_type():
    """Test validation fails for invalid events type."""
    request = RCARequest("not a list")
    is_valid, error = request.validate()
    
    assert not is_valid
    assert "list" in error.lower()


def test_rca_request_validation_invalid_event_format():
    """Test validation fails for invalid event format."""
    request = RCARequest([{"valid": "event"}, "invalid event"])
    is_valid, error = request.validate()
    
    assert not is_valid
    assert "dictionary" in error.lower()


def test_rca_request_validation_success():
    """Test validation succeeds for valid request."""
    events = [
        {"service": "api", "level": "error"},
        {"service": "db", "level": "warn"}
    ]
    request = RCARequest(events)
    is_valid, error = request.validate()
    
    assert is_valid
    assert error is None


def test_process_rca_request_success():
    """Test successful RCA request processing."""
    request_data = {
        "events": [
            {"service": "api", "level": "error", "message": "Connection timeout"},
            {"service": "db", "level": "error", "message": "Slow query"}
        ]
    }
    
    result = process_rca_request(request_data)
    
    assert result["status"] == "success"
    assert "incident_id" in result
    assert "timestamp" in result
    assert "summary" in result
    assert "root_causes" in result
    assert "recommendations" in result


def test_process_rca_request_with_incident_id():
    """Test RCA request processing with custom incident ID."""
    incident_id = "test-incident-456"
    request_data = {
        "events": [{"service": "api"}],
        "incident_id": incident_id
    }
    
    result = process_rca_request(request_data)
    
    assert result["incident_id"] == incident_id


def test_process_rca_request_empty_events():
    """Test RCA request processing with empty events."""
    request_data = {"events": []}
    
    result = process_rca_request(request_data)
    
    assert result["status"] == "error"
    assert "error" in result
    assert "empty" in result["error"].lower()


def test_process_rca_request_identifies_services():
    """Test RCA request identifies services from events."""
    request_data = {
        "events": [
            {"service": "api"},
            {"service": "db"},
            {"service": "api"},  # Duplicate
        ]
    }
    
    result = process_rca_request(request_data)
    
    assert result["status"] == "success"
    assert "services" in result
    assert set(result["services"]) == {"api", "db"}


def test_process_rca_request_returns_root_causes():
    """Test RCA request returns root causes."""
    request_data = {
        "events": [{"service": "api", "level": "error"}]
    }
    
    result = process_rca_request(request_data)
    
    assert result["status"] == "success"
    assert "root_causes" in result
    assert isinstance(result["root_causes"], list)
    assert len(result["root_causes"]) > 0


def test_process_rca_request_returns_recommendations():
    """Test RCA request returns recommendations."""
    request_data = {
        "events": [{"service": "api", "level": "error"}]
    }
    
    result = process_rca_request(request_data)
    
    assert result["status"] == "success"
    assert "recommendations" in result
    assert isinstance(result["recommendations"], list)
    assert len(result["recommendations"]) > 0


def test_get_rca_status():
    """Test getting RCA analysis status."""
    incident_id = "test-incident-789"
    
    status = get_rca_status(incident_id)
    
    assert status["incident_id"] == incident_id
    assert "status" in status
    assert "progress" in status
    assert "message" in status


def test_get_rca_status_completed():
    """Test RCA status shows completed."""
    status = get_rca_status("any-incident-id")
    
    assert status["status"] == "completed"
    assert status["progress"] == 100


def test_process_rca_request_missing_events():
    """Test RCA request with missing events field."""
    request_data = {}
    
    result = process_rca_request(request_data)
    
    assert result["status"] == "error"


def test_process_rca_request_event_count():
    """Test RCA result includes event count."""
    events_count = 5
    request_data = {
        "events": [{"service": f"service-{i}"} for i in range(events_count)]
    }
    
    result = process_rca_request(request_data)
    
    assert result["status"] == "success"
    assert str(events_count) in result["summary"]


def test_rca_request_timestamp_format():
    """Test RCA request timestamp is ISO format."""
    request = RCARequest([{"service": "api"}])
    
    # Should not raise exception
    from datetime import datetime
    datetime.fromisoformat(request.timestamp)

