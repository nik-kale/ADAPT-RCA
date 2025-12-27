"""
Tests for exception handling and custom exception types.

Verifies that specific exceptions are raised appropriately.
"""

import pytest
from pathlib import Path
import tempfile
import json

from src.adapt_rca.exceptions import (
    FileLoadError,
    InvalidFormatError,
    LogParseError,
    ValidationError,
    GraphBuildError,
    NodeNotFoundError,
)
from src.adapt_rca.ingestion.file_loader import load_jsonl
from src.adapt_rca.parsing.log_parser import normalize_event
from src.adapt_rca.graph.causal_graph import CausalGraph


# File loader exception tests
def test_file_loader_missing_file():
    """Test FileLoadError raised for missing file."""
    with pytest.raises(FileLoadError, match="not found"):
        list(load_jsonl("/nonexistent/path/file.jsonl"))


def test_file_loader_directory_not_file():
    """Test FileLoadError raised for directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(FileLoadError, match="Not a file"):
            list(load_jsonl(tmpdir))


def test_file_loader_invalid_encoding():
    """Test InvalidFormatError raised for invalid encoding."""
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.jsonl') as f:
        # Write invalid UTF-8
        f.write(b'\xff\xfe Invalid UTF-8')
        temp_path = f.name
    
    try:
        with pytest.raises(InvalidFormatError, match="encoding"):
            list(load_jsonl(temp_path))
    finally:
        Path(temp_path).unlink()


def test_file_loader_valid_file():
    """Test successful file loading doesn't raise exceptions."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
        f.write('{"test": "data"}\n')
        temp_path = f.name
    
    try:
        events = list(load_jsonl(temp_path))
        assert len(events) == 1
        assert events[0]["test"] == "data"
    finally:
        Path(temp_path).unlink()


# Log parser exception tests
def test_log_parser_invalid_type():
    """Test LogParseError raised for non-dict input."""
    with pytest.raises(LogParseError, match="must be a dictionary"):
        normalize_event("not a dict")


def test_log_parser_missing_required_fields():
    """Test ValidationError raised for insufficient data."""
    with pytest.raises(ValidationError, match="at least"):
        normalize_event({})


def test_log_parser_valid_event():
    """Test successful parsing doesn't raise exceptions."""
    event = normalize_event({
        "timestamp": "2024-01-01T00:00:00Z",
        "service": "api",
        "level": "error",
        "message": "Test error"
    })
    
    assert event["service"] == "api"
    assert event["message"] == "Test error"


def test_log_parser_minimal_valid_event():
    """Test parsing with minimal required fields."""
    event = normalize_event({"service": "test"})
    assert event["service"] == "test"
    
    event = normalize_event({"message": "test"})
    assert event["message"] == "test"


# Graph exception tests
def test_graph_duplicate_node():
    """Test GraphBuildError raised for duplicate node."""
    graph = CausalGraph()
    graph.add_node("node1")
    
    with pytest.raises(GraphBuildError, match="already exists"):
        graph.add_node("node1")


def test_graph_invalid_node_id():
    """Test GraphBuildError raised for invalid node ID."""
    graph = CausalGraph()
    
    with pytest.raises(GraphBuildError, match="non-empty string"):
        graph.add_node("")
    
    with pytest.raises(GraphBuildError, match="non-empty string"):
        graph.add_node(None)


def test_graph_edge_missing_source():
    """Test NodeNotFoundError raised for missing source node."""
    graph = CausalGraph()
    graph.add_node("target")
    
    with pytest.raises(NodeNotFoundError, match="Source node.*not found"):
        graph.add_edge("missing", "target")


def test_graph_edge_missing_target():
    """Test NodeNotFoundError raised for missing target node."""
    graph = CausalGraph()
    graph.add_node("source")
    
    with pytest.raises(NodeNotFoundError, match="Target node.*not found"):
        graph.add_edge("source", "missing")


def test_graph_self_loop():
    """Test GraphBuildError raised for self-loop."""
    graph = CausalGraph()
    graph.add_node("node1")
    
    with pytest.raises(GraphBuildError, match="Self-loops"):
        graph.add_edge("node1", "node1")


def test_graph_get_node_not_found():
    """Test NodeNotFoundError raised when getting missing node."""
    graph = CausalGraph()
    
    with pytest.raises(NodeNotFoundError, match="not found"):
        graph.get_node("missing")


def test_graph_valid_operations():
    """Test successful graph operations don't raise exceptions."""
    graph = CausalGraph()
    
    # Add nodes
    graph.add_node("service-a")
    graph.add_node("service-b")
    
    # Add edge
    graph.add_edge("service-a", "service-b", evidence=["log1", "log2"])
    
    # Get node
    node = graph.get_node("service-a")
    assert node["id"] == "service-a"
    
    # Export
    graph_dict = graph.to_dict()
    assert len(graph_dict["nodes"]) == 2
    assert len(graph_dict["edges"]) == 1


def test_exception_hierarchy():
    """Test exception hierarchy is correct."""
    from src.adapt_rca.exceptions import ADAPTError
    
    # All custom exceptions should inherit from ADAPTError
    assert issubclass(FileLoadError, ADAPTError)
    assert issubclass(InvalidFormatError, ADAPTError)
    assert issubclass(LogParseError, ADAPTError)
    assert issubclass(ValidationError, ADAPTError)
    assert issubclass(GraphBuildError, ADAPTError)
    assert issubclass(NodeNotFoundError, ADAPTError)

