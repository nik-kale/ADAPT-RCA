"""
Tests for causal graph module.
"""
import pytest
from datetime import datetime, timedelta
from adapt_rca.graph.causal_graph import CausalGraph, CausalNode, CausalEdge
from adapt_rca.models import Event, IncidentGroup


def test_causal_node_creation() -> None:
    """Test CausalNode creation."""
    node = CausalNode("api-gateway", metadata={"version": "1.0"})

    assert node.id == "api-gateway"
    assert node.metadata["version"] == "1.0"
    assert node.error_count == 0
    assert node.first_error is None
    assert node.last_error is None


def test_causal_edge_creation() -> None:
    """Test CausalEdge creation."""
    edge = CausalEdge(
        "service-a",
        "service-b",
        evidence=["Error in A", "Error in B"],
        time_delta=timedelta(seconds=30),
        confidence=0.8
    )

    assert edge.from_node == "service-a"
    assert edge.to_node == "service-b"
    assert len(edge.evidence) == 2
    assert edge.time_delta.total_seconds() == 30
    assert edge.confidence == 0.8


def test_graph_add_node() -> None:
    """Test adding nodes to graph."""
    graph = CausalGraph()

    node1 = graph.add_node("service-a")
    node2 = graph.add_node("service-b")

    assert len(graph.nodes) == 2
    assert "service-a" in graph.nodes
    assert "service-b" in graph.nodes

    # Adding same node again should return existing
    node1_again = graph.add_node("service-a")
    assert len(graph.nodes) == 2
    assert node1 is node1_again


def test_graph_add_edge() -> None:
    """Test adding edges to graph."""
    graph = CausalGraph()

    graph.add_node("service-a")
    graph.add_node("service-b")
    graph.add_edge("service-a", "service-b", confidence=0.7)

    assert len(graph.edges) == 1
    assert graph.edges[0].from_node == "service-a"
    assert graph.edges[0].to_node == "service-b"
    assert graph.edges[0].confidence == 0.7


def test_graph_record_error() -> None:
    """Test recording errors in graph."""
    graph = CausalGraph()

    timestamp1 = datetime(2025, 11, 16, 10, 0, 0)
    timestamp2 = datetime(2025, 11, 16, 10, 5, 0)

    graph.record_error("api", timestamp1, "Error 1")
    graph.record_error("api", timestamp2, "Error 2")

    node = graph.nodes["api"]
    assert node.error_count == 2
    assert node.first_error == timestamp1
    assert node.last_error == timestamp2


def test_graph_from_incident_group_empty() -> None:
    """Test building graph from empty incident."""
    incident = IncidentGroup()
    graph = CausalGraph.from_incident_group(incident)

    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0


def test_graph_from_incident_group_no_timestamps() -> None:
    """Test building graph from incident without timestamps."""
    events = [
        Event(service="api", level="ERROR", message="Error 1"),
        Event(service="db", level="ERROR", message="Error 2")
    ]

    incident = IncidentGroup.from_events(events)
    graph = CausalGraph.from_incident_group(incident)

    assert len(graph.nodes) == 2
    assert "api" in graph.nodes
    assert "db" in graph.nodes
    assert len(graph.edges) == 0  # No edges without timestamps


def test_graph_from_incident_group_with_timestamps() -> None:
    """Test building graph from incident with timestamps."""
    events = [
        Event(
            service="api",
            level="ERROR",
            message="Error 1",
            timestamp=datetime(2025, 11, 16, 10, 0, 0)
        ),
        Event(
            service="db",
            level="ERROR",
            message="Error 2",
            timestamp=datetime(2025, 11, 16, 10, 0, 30)
        ),
        Event(
            service="cache",
            level="ERROR",
            message="Error 3",
            timestamp=datetime(2025, 11, 16, 10, 1, 0)
        )
    ]

    incident = IncidentGroup.from_events(events)
    graph = CausalGraph.from_incident_group(incident)

    assert len(graph.nodes) == 3
    assert len(graph.edges) == 2  # api->db, db->cache


def test_graph_get_root_causes_with_edges() -> None:
    """Test identifying root causes from graph topology."""
    graph = CausalGraph()

    graph.add_node("api")
    graph.add_node("db")
    graph.add_node("cache")

    # api causes db, db causes cache
    # api should be root cause
    graph.add_edge("api", "db", confidence=0.8)
    graph.add_edge("db", "cache", confidence=0.7)

    root_causes = graph.get_root_causes()

    assert "api" in root_causes
    assert "db" not in root_causes
    assert "cache" not in root_causes


def test_graph_get_root_causes_no_edges() -> None:
    """Test root cause identification when no edges exist."""
    graph = CausalGraph()

    timestamp = datetime(2025, 11, 16, 10, 0, 0)
    graph.record_error("api", timestamp, "First error")
    graph.record_error("db", timestamp + timedelta(minutes=5), "Later error")

    root_causes = graph.get_root_causes()

    # Should return service with earliest error
    assert "api" in root_causes


def test_graph_to_dict() -> None:
    """Test graph export to dictionary."""
    graph = CausalGraph()

    graph.add_node("api")
    graph.add_node("db")
    graph.add_edge("api", "db", confidence=0.8)

    graph_dict = graph.to_dict()

    assert "nodes" in graph_dict
    assert "edges" in graph_dict
    assert "root_causes" in graph_dict
    assert len(graph_dict["nodes"]) == 2
    assert len(graph_dict["edges"]) == 1


def test_graph_to_mermaid() -> None:
    """Test Mermaid diagram export."""
    graph = CausalGraph()

    graph.add_node("api-gateway")
    graph.add_node("user-service")
    graph.add_edge("api-gateway", "user-service", confidence=0.8)

    mermaid = graph.to_mermaid()

    assert "graph TD" in mermaid
    assert "api_gateway" in mermaid  # Sanitized name
    assert "user_service" in mermaid
    assert "0.80" in mermaid  # Confidence


def test_graph_to_dot() -> None:
    """Test DOT diagram export."""
    graph = CausalGraph()

    graph.add_node("api")
    graph.add_node("db")
    graph.add_edge("api", "db", confidence=0.7)

    dot = graph.to_dot()

    assert "digraph CausalGraph" in dot
    assert '"api"' in dot
    assert '"db"' in dot
    assert '->' in dot
    assert "0.70" in dot


def test_graph_confidence_calculation() -> None:
    """Test confidence score calculation based on time proximity."""
    events = [
        Event(
            service="api",
            timestamp=datetime(2025, 11, 16, 10, 0, 0),
            level="ERROR",
            message="Error"
        ),
        Event(
            service="db",
            timestamp=datetime(2025, 11, 16, 10, 0, 10),  # 10 seconds later
            level="ERROR",
            message="Error"
        )
    ]

    incident = IncidentGroup.from_events(events)
    graph = CausalGraph.from_incident_group(incident)

    # Should have high confidence due to close timing
    assert len(graph.edges) == 1
    assert graph.edges[0].confidence > 0.9  # Very close in time


def test_graph_time_window_cutoff() -> None:
    """Test that events beyond time window don't create edges."""
    events = [
        Event(
            service="api",
            timestamp=datetime(2025, 11, 16, 10, 0, 0),
            level="ERROR",
            message="Error"
        ),
        Event(
            service="db",
            timestamp=datetime(2025, 11, 16, 10, 10, 0),  # 10 minutes later
            level="ERROR",
            message="Error"
        )
    ]

    incident = IncidentGroup.from_events(events)
    graph = CausalGraph.from_incident_group(incident)

    # Should not have edge (beyond 5-minute window)
    assert len(graph.edges) == 0
