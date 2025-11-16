"""
Tests for enhanced reasoning agent.
"""
import pytest
from datetime import datetime
from adapt_rca.reasoning.agent import (
    analyze_incident_group,
    _analyze_error_patterns,
    _generate_summary,
    _identify_root_causes,
    _generate_recommendations
)
from adapt_rca.models import Event, IncidentGroup, RootCause, RecommendedAction
from adapt_rca.graph.causal_graph import CausalGraph


def test_analyze_error_patterns_empty() -> None:
    """Test error pattern analysis with no events."""
    patterns = _analyze_error_patterns([])

    assert patterns["most_common_errors"] == []
    assert patterns["error_types"] == {}


def test_analyze_error_patterns_with_data() -> None:
    """Test error pattern analysis with real events."""
    events = [
        Event(level="ERROR", message="Connection timeout"),
        Event(level="ERROR", message="Connection timeout"),
        Event(level="WARN", message="Slow query"),
        Event(level="CRITICAL", message="Out of memory")
    ]

    patterns = _analyze_error_patterns(events)

    assert len(patterns["most_common_errors"]) > 0
    assert patterns["most_common_errors"][0]["message"] == "Connection timeout"
    assert patterns["most_common_errors"][0]["count"] == 2
    assert patterns["error_types"]["ERROR"] == 2
    assert patterns["error_types"]["WARN"] == 1
    assert patterns["error_types"]["CRITICAL"] == 1


def test_generate_summary() -> None:
    """Test incident summary generation."""
    events = [
        Event(service="api", level="ERROR", message="Error 1"),
        Event(service="db", level="ERROR", message="Error 2")
    ]

    incident = IncidentGroup.from_events(events)
    summary = _generate_summary(incident, ["api"], {})

    assert "2 events" in summary
    assert "2 service" in summary
    assert "api" in summary or "db" in summary


def test_identify_root_causes_from_graph() -> None:
    """Test root cause identification from causal graph."""
    events = [
        Event(
            service="api",
            level="ERROR",
            message="Timeout",
            timestamp=datetime(2025, 11, 16, 10, 0, 0)
        ),
        Event(
            service="db",
            level="ERROR",
            message="Connection failed",
            timestamp=datetime(2025, 11, 16, 10, 0, 30)
        )
    ]

    incident = IncidentGroup.from_events(events)
    graph = CausalGraph.from_incident_group(incident)
    root_cause_services = graph.get_root_causes()

    root_causes = _identify_root_causes(
        incident,
        graph,
        root_cause_services,
        {}
    )

    assert len(root_causes) > 0
    assert all(isinstance(rc, RootCause) for rc in root_causes)
    assert all(0.0 <= rc.confidence <= 1.0 for rc in root_causes)


def test_identify_root_causes_pattern_based() -> None:
    """Test pattern-based root cause identification."""
    events = [
        Event(level="ERROR", message="Database deadlock") for _ in range(5)
    ]

    incident = IncidentGroup.from_events(events)
    graph = CausalGraph()
    error_patterns = _analyze_error_patterns(events)

    root_causes = _identify_root_causes(
        incident,
        graph,
        [],
        error_patterns
    )

    # Should identify the repeated error pattern
    assert len(root_causes) > 0
    assert any("Database deadlock" in rc.description for rc in root_causes)


def test_generate_recommendations() -> None:
    """Test recommendation generation."""
    events = [Event(service="api", level="ERROR", message="Error")]
    incident = IncidentGroup.from_events(events)

    recommendations = _generate_recommendations(
        incident,
        ["api"],
        {"error_types": {"ERROR": 1}}
    )

    assert len(recommendations) > 0
    assert all(isinstance(r, RecommendedAction) for r in recommendations)
    assert all(1 <= r.priority <= 5 for r in recommendations)
    assert all(r.category in ["investigate", "fix", "monitor", "document"] for r in recommendations)


def test_generate_recommendations_critical_errors() -> None:
    """Test recommendations for critical errors."""
    events = [Event(level="CRITICAL", message="System failure")]
    incident = IncidentGroup.from_events(events)

    error_patterns = _analyze_error_patterns(events)
    recommendations = _generate_recommendations(
        incident,
        [],
        error_patterns
    )

    # Should have high-priority recommendation for critical errors
    priorities = [r.priority for r in recommendations]
    assert 1 in priorities  # At least one priority-1 action


def test_analyze_incident_group_complete() -> None:
    """Test complete incident analysis."""
    events = [
        Event(
            service="api",
            level="ERROR",
            message="Connection timeout",
            timestamp=datetime(2025, 11, 16, 10, 0, 0)
        ),
        Event(
            service="db",
            level="ERROR",
            message="Too many connections",
            timestamp=datetime(2025, 11, 16, 10, 0, 30)
        )
    ]

    incident = IncidentGroup.from_events(events)
    result = analyze_incident_group(incident)

    assert result.incident_summary
    assert len(result.probable_root_causes) > 0
    assert len(result.recommended_actions) > 0
    assert result.event_count == 2
    assert len(result.affected_services) == 2
    assert result.causal_graph is not None


def test_analyze_incident_group_empty() -> None:
    """Test analysis with no events."""
    incident = IncidentGroup()
    result = analyze_incident_group(incident)

    assert result.incident_summary == "No events to analyze"
    assert result.event_count == 0


def test_legacy_analyze_incident_compatibility() -> None:
    """Test that legacy analyze_incident function still works."""
    from adapt_rca.reasoning.agent import analyze_incident

    events = [
        {"service": "api", "level": "ERROR", "message": "Error"}
    ]

    result = analyze_incident(events)

    assert "incident_summary" in result
    assert "probable_root_causes" in result
    assert "recommended_actions" in result
