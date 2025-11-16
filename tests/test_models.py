"""
Tests for Pydantic models.
"""
import pytest
from datetime import datetime
from adapt_rca.models import (
    Event,
    IncidentGroup,
    RootCause,
    RecommendedAction,
    AnalysisResult
)


def test_event_creation() -> None:
    """Test Event model creation."""
    event = Event(
        timestamp=datetime(2025, 11, 16, 10, 0, 0),
        service="api-gateway",
        level="ERROR",
        message="Test error"
    )

    assert event.service == "api-gateway"
    assert event.level == "ERROR"
    assert event.message == "Test error"


def test_event_timestamp_parsing() -> None:
    """Test Event timestamp parsing from string."""
    event = Event(
        timestamp="2025-11-16T10:00:00Z",
        service="test",
        level="INFO",
        message="Test"
    )

    assert isinstance(event.timestamp, datetime)
    assert event.timestamp.year == 2025


def test_event_level_normalization() -> None:
    """Test Event level normalization to uppercase."""
    event = Event(level="error", message="Test")
    assert event.level == "ERROR"


def test_event_invalid_timestamp() -> None:
    """Test Event with invalid timestamp."""
    event = Event(timestamp="not-a-date", message="Test")
    assert event.timestamp is None


def test_incident_group_from_events() -> None:
    """Test IncidentGroup creation from events."""
    events = [
        Event(
            timestamp=datetime(2025, 11, 16, 10, 0, 0),
            service="api",
            level="ERROR",
            message="Error 1"
        ),
        Event(
            timestamp=datetime(2025, 11, 16, 10, 5, 0),
            service="db",
            level="CRITICAL",
            message="Error 2"
        )
    ]

    group = IncidentGroup.from_events(events)

    assert len(group.events) == 2
    assert group.start_time == datetime(2025, 11, 16, 10, 0, 0)
    assert group.end_time == datetime(2025, 11, 16, 10, 5, 0)
    assert set(group.services) == {"api", "db"}
    assert group.severity == "CRITICAL"


def test_incident_group_empty() -> None:
    """Test IncidentGroup with no events."""
    group = IncidentGroup.from_events([])
    assert len(group.events) == 0
    assert group.start_time is None
    assert group.end_time is None


def test_root_cause_validation() -> None:
    """Test RootCause model validation."""
    rc = RootCause(
        description="Database connection pool exhausted",
        confidence=0.85,
        evidence=["Max connections reached", "Connection timeout errors"]
    )

    assert rc.description == "Database connection pool exhausted"
    assert rc.confidence == 0.85
    assert len(rc.evidence) == 2


def test_root_cause_invalid_confidence() -> None:
    """Test RootCause with invalid confidence score."""
    with pytest.raises(ValueError):
        RootCause(description="Test", confidence=1.5)  # > 1.0

    with pytest.raises(ValueError):
        RootCause(description="Test", confidence=-0.1)  # < 0.0


def test_recommended_action_creation() -> None:
    """Test RecommendedAction model creation."""
    action = RecommendedAction(
        description="Increase connection pool size",
        priority=1,
        category="fix"
    )

    assert action.description == "Increase connection pool size"
    assert action.priority == 1
    assert action.category == "fix"


def test_recommended_action_invalid_priority() -> None:
    """Test RecommendedAction with invalid priority."""
    with pytest.raises(ValueError):
        RecommendedAction(description="Test", priority=0)  # < 1

    with pytest.raises(ValueError):
        RecommendedAction(description="Test", priority=6)  # > 5


def test_analysis_result_creation() -> None:
    """Test AnalysisResult model creation."""
    result = AnalysisResult(
        incident_summary="Database connection issues",
        probable_root_causes=[
            RootCause(description="Pool exhaustion", confidence=0.9)
        ],
        recommended_actions=[
            RecommendedAction(description="Increase pool size", priority=1)
        ],
        affected_services=["api", "database"],
        event_count=10
    )

    assert result.incident_summary == "Database connection issues"
    assert len(result.probable_root_causes) == 1
    assert len(result.recommended_actions) == 1
    assert len(result.affected_services) == 2
    assert result.event_count == 10


def test_analysis_result_to_legacy_dict() -> None:
    """Test AnalysisResult conversion to legacy format."""
    result = AnalysisResult(
        incident_summary="Test incident",
        probable_root_causes=[
            RootCause(description="Cause 1", confidence=0.8),
            RootCause(description="Cause 2", confidence=0.6)
        ],
        recommended_actions=[
            RecommendedAction(description="Action 1", priority=1),
            RecommendedAction(description="Action 2", priority=2)
        ]
    )

    legacy = result.to_legacy_dict()

    assert legacy["incident_summary"] == "Test incident"
    assert legacy["probable_root_causes"] == ["Cause 1", "Cause 2"]
    assert legacy["recommended_actions"] == ["Action 1", "Action 2"]
