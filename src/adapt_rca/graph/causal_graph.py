"""Causal graph construction and analysis for incident root cause detection.

This module provides classes and methods for building directed graphs that represent
causal relationships between services based on temporal patterns and error propagation.
The graph structure helps identify root causes by analyzing event sequences and
service dependencies.

Classes:
    CausalNode: Represents a service or component node in the causal graph.
    CausalEdge: Represents a directed edge showing potential causation between nodes.
    CausalGraph: Main graph structure for building and analyzing causal relationships.

Example:
    >>> from adapt_rca.graph.causal_graph import CausalGraph
    >>> from adapt_rca.models import IncidentGroup
    >>>
    >>> # Build graph from incident
    >>> graph = CausalGraph.from_incident_group(incident)
    >>> root_causes = graph.get_root_causes()
    >>> print(f"Root causes: {root_causes}")
"""
from typing import List, Dict, Optional, Set, Any
from datetime import datetime, timedelta
import logging

from ..models import Event, IncidentGroup
from ..constants import (
    TIME_CORRELATION_WINDOW_MINUTES,
    MIN_CONFIDENCE,
    MAX_CONFIDENCE
)

logger = logging.getLogger(__name__)


class CausalNode:
    """Represents a node (service/component) in the causal graph.

    A node tracks error events for a specific service or component, including
    timing information and error counts. This information is used to determine
    causal relationships and identify root causes.

    Attributes:
        id (str): Unique identifier for the node (typically service/component name).
        metadata (Dict[str, Any]): Additional metadata about the node.
        error_count (int): Total number of errors recorded for this node.
        first_error (Optional[datetime]): Timestamp of the first error event.
        last_error (Optional[datetime]): Timestamp of the most recent error event.
    """

    def __init__(self, node_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Initialize a causal node.

        Args:
            node_id: Unique identifier for the node.
            metadata: Optional dictionary of additional metadata.
        """
        self.id = node_id
        self.metadata = metadata or {}
        self.error_count = 0
        self.first_error: Optional[datetime] = None
        self.last_error: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary representation.

        Returns:
            Dictionary containing node id, metadata, error statistics, and timing info.
        """
        return {
            "id": self.id,
            "metadata": self.metadata,
            "error_count": self.error_count,
            "first_error": self.first_error.isoformat() if self.first_error else None,
            "last_error": self.last_error.isoformat() if self.last_error else None,
        }


class CausalEdge:
    """Represents a directed edge showing potential causation between services.

    An edge indicates that errors in the source node may have caused errors
    in the target node. The confidence score and time delta provide additional
    context for the causal relationship.

    Attributes:
        from_node (str): Source node ID (potentially causing service).
        to_node (str): Target node ID (potentially affected service).
        evidence (List[str]): List of evidence supporting this causal relationship.
        time_delta (Optional[timedelta]): Time difference between error events.
        confidence (float): Confidence score between 0.0 and 1.0.
    """

    def __init__(
        self,
        from_node: str,
        to_node: str,
        evidence: Optional[List[str]] = None,
        time_delta: Optional[timedelta] = None,
        confidence: float = 0.5
    ) -> None:
        """Initialize a causal edge.

        Args:
            from_node: Source node identifier.
            to_node: Target node identifier.
            evidence: List of evidence strings supporting this edge.
            time_delta: Time difference between the causally related events.
            confidence: Confidence score (0.0 to 1.0, default 0.5).
        """
        self.from_node = from_node
        self.to_node = to_node
        self.evidence = evidence or []
        self.time_delta = time_delta
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        """Convert edge to dictionary representation.

        Returns:
            Dictionary containing edge endpoints, evidence, timing, and confidence.
        """
        return {
            "from": self.from_node,
            "to": self.to_node,
            "evidence": self.evidence,
            "time_delta_seconds": self.time_delta.total_seconds() if self.time_delta else None,
            "confidence": self.confidence,
        }


class CausalGraph:
    """Builds and manages a directed graph of components, errors, and dependencies.

    This graph represents the causal relationships between services based on
    temporal patterns and error propagation. It analyzes event sequences to
    identify which services may have caused errors in other services.

    Attributes:
        nodes (Dict[str, CausalNode]): Dictionary mapping node IDs to CausalNode objects.
        edges (List[CausalEdge]): List of directed edges representing causal relationships.

    Example:
        >>> graph = CausalGraph()
        >>> graph.add_node("api-gateway")
        >>> graph.add_node("database")
        >>> graph.add_edge("api-gateway", "database", confidence=0.8)
        >>> root_causes = graph.get_root_causes()
    """

    def __init__(self) -> None:
        """Initialize an empty causal graph."""
        self.nodes: Dict[str, CausalNode] = {}
        self.edges: List[CausalEdge] = []

    def add_node(self, node_id: str, metadata: Optional[Dict[str, Any]] = None) -> CausalNode:
        """
        Add a node (service/component) to the graph.

        Args:
            node_id: Unique identifier for the node
            metadata: Additional metadata about the node

        Returns:
            The created or existing CausalNode
        """
        if node_id not in self.nodes:
            self.nodes[node_id] = CausalNode(node_id, metadata)
            logger.debug(f"Added node: {node_id}")
        return self.nodes[node_id]

    def add_edge(
        self,
        from_node: str,
        to_node: str,
        evidence: Optional[List[str]] = None,
        time_delta: Optional[timedelta] = None,
        confidence: float = 0.5
    ) -> None:
        """
        Add a directed edge with optional evidence.

        Args:
            from_node: Source node ID
            to_node: Target node ID
            evidence: List of evidence supporting this edge
            time_delta: Time difference between events
            confidence: Confidence score (0.0 to 1.0)

        Raises:
            ValueError: If either node doesn't exist in the graph
        """
        # Validate that both nodes exist
        if from_node not in self.nodes:
            raise ValueError(f"Source node '{from_node}' does not exist in graph. Add node first.")
        if to_node not in self.nodes:
            raise ValueError(f"Target node '{to_node}' does not exist in graph. Add node first.")

        # Validate confidence score
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {confidence}")

        edge = CausalEdge(from_node, to_node, evidence, time_delta, confidence)
        self.edges.append(edge)
        logger.debug(f"Added edge: {from_node} -> {to_node} (confidence: {confidence})")

    def record_error(self, service: str, timestamp: Optional[datetime], message: str) -> None:
        """Record an error event for a service.

        This method updates the error statistics for the specified service node,
        including error count and timing information. If the node doesn't exist,
        it will be created automatically.

        Args:
            service: Service name (will be created as node if not exists).
            timestamp: Error timestamp (can be None for events without timing).
            message: Error message text.
        """
        node = self.add_node(service)
        node.error_count += 1

        if timestamp:
            if node.first_error is None or timestamp < node.first_error:
                node.first_error = timestamp
            if node.last_error is None or timestamp > node.last_error:
                node.last_error = timestamp

    @classmethod
    def from_incident_group(cls, incident: IncidentGroup) -> 'CausalGraph':
        """Build a causal graph from an incident group.

        Analyzes temporal patterns and service relationships to infer causation.
        Events that occur close together in time are analyzed to determine if
        one service's errors may have caused another service's errors.

        The algorithm:
        1. Sorts events by timestamp
        2. Records all errors in the graph
        3. Identifies event pairs within the correlation time window
        4. Creates edges with confidence based on temporal proximity
        5. Closer events receive higher confidence scores

        Args:
            incident: The incident group containing events to analyze.

        Returns:
            A CausalGraph with nodes for each service and edges representing
            potential causal relationships.

        Example:
            >>> incident = IncidentGroup.from_events(events)
            >>> graph = CausalGraph.from_incident_group(incident)
            >>> print(f"Found {len(graph.edges)} causal relationships")
        """
        graph = cls()

        if not incident.events:
            return graph

        # Sort events by timestamp
        sorted_events = sorted(
            [e for e in incident.events if e.timestamp],
            key=lambda e: e.timestamp
        )

        if not sorted_events:
            # No timestamps, create nodes without edges
            for event in incident.events:
                if event.service:
                    graph.record_error(event.service, None, event.message or "")
            return graph

        # Record all errors
        for event in sorted_events:
            if event.service:
                graph.record_error(event.service, event.timestamp, event.message or "")

        # Detect causal relationships based on temporal patterns
        # If service A errors, then service B errors shortly after, A might cause B
        # OPTIMIZED: O(n·k) where k is events within time window (was O(n²))
        max_time_window = timedelta(minutes=TIME_CORRELATION_WINDOW_MINUTES)

        # Track which edges we've already added to avoid duplicates
        # Using set of tuples is more efficient than checking list each time
        existing_edges: Set[tuple] = set()

        # Use sliding window approach for O(n·k) complexity
        for i, event1 in enumerate(sorted_events):
            if not event1.service:
                continue

            # Only look at events within the time window (bounded by k)
            # Since events are sorted, we can break early when outside window
            j = i + 1
            while j < len(sorted_events):
                event2 = sorted_events[j]

                # Calculate time difference
                time_diff = event2.timestamp - event1.timestamp

                # Break early if beyond time window (optimization)
                if time_diff > max_time_window:
                    break

                # Skip if same service or no service
                if event2.service and event2.service != event1.service:
                    # Calculate confidence based on time proximity
                    # Closer events = higher confidence
                    confidence = 1.0 - (time_diff.total_seconds() / max_time_window.total_seconds())
                    # Clamp between MIN_CONFIDENCE + 0.1 and MAX_CONFIDENCE - 0.1
                    confidence = max(MIN_CONFIDENCE + 0.1, min(MAX_CONFIDENCE - 0.1, confidence))

                    # Check if edge already exists using set (O(1) lookup)
                    edge_key = (event1.service, event2.service)
                    if edge_key not in existing_edges:
                        existing_edges.add(edge_key)

                        evidence = [
                            f"{event1.service}: {event1.message or 'error'}",
                            f"{event2.service}: {event2.message or 'error'}"
                        ]
                        graph.add_edge(
                            event1.service,
                            event2.service,
                            evidence=evidence,
                            time_delta=time_diff,
                            confidence=confidence
                        )

                j += 1

        return graph

    def get_root_causes(self) -> List[str]:
        """Identify potential root cause services.

        Root causes are identified using graph topology and timing:
        - Services with outgoing edges (affect others) but no incoming edges
        - If no clear topology root, the service with the earliest error

        This heuristic assumes that root cause services:
        1. Cause errors in downstream services (outgoing edges)
        2. Are not caused by other services (no incoming edges)
        3. Experience errors first in the incident timeline

        Returns:
            List of service IDs that are likely root causes. May be empty
            if no services have errors.

        Example:
            >>> root_causes = graph.get_root_causes()
            >>> if root_causes:
            ...     print(f"Root cause: {root_causes[0]}")
        """
        # Count incoming edges for each node
        incoming_count: Dict[str, int] = {node_id: 0 for node_id in self.nodes}
        outgoing_count: Dict[str, int] = {node_id: 0 for node_id in self.nodes}

        for edge in self.edges:
            if edge.to_node in incoming_count:
                incoming_count[edge.to_node] += 1
            if edge.from_node in outgoing_count:
                outgoing_count[edge.from_node] += 1

        # Services with outgoing edges but few incoming are likely root causes
        root_causes = []
        for node_id, node in self.nodes.items():
            if outgoing_count[node_id] > 0 and incoming_count[node_id] == 0:
                root_causes.append(node_id)

        # If no clear root causes, return services with earliest errors
        if not root_causes:
            sorted_nodes = sorted(
                [(nid, n) for nid, n in self.nodes.items() if n.first_error],
                key=lambda x: x[1].first_error
            )
            if sorted_nodes:
                root_causes = [sorted_nodes[0][0]]

        return root_causes

    def to_dict(self) -> Dict[str, Any]:
        """Export graph as a dictionary.

        Serializes the entire graph structure including nodes, edges, and
        identified root causes into a dictionary format suitable for JSON
        export or further processing.

        Returns:
            Dictionary containing:
                - nodes: List of node dictionaries
                - edges: List of edge dictionaries
                - root_causes: List of root cause service IDs
        """
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
            "root_causes": self.get_root_causes()
        }

    def to_mermaid(self) -> str:
        """Export graph as Mermaid diagram syntax.

        Generates a Mermaid flowchart showing services as nodes and causal
        relationships as edges. Node labels include error counts, and edge
        labels show confidence scores and time deltas.

        Returns:
            String containing Mermaid diagram syntax (graph TD format).

        Example:
            >>> mermaid = graph.to_mermaid()
            >>> with open('graph.mmd', 'w') as f:
            ...     f.write(mermaid)
        """
        lines = ["graph TD"]

        # Add nodes
        for node_id, node in self.nodes.items():
            # Sanitize node ID for Mermaid
            safe_id = node_id.replace("-", "_").replace(".", "_")
            label = f"{node_id}<br/>Errors: {node.error_count}"
            lines.append(f"    {safe_id}[{label}]")

        # Add edges
        for edge in self.edges:
            safe_from = edge.from_node.replace("-", "_").replace(".", "_")
            safe_to = edge.to_node.replace("-", "_").replace(".", "_")
            label = f"{edge.confidence:.2f}"
            if edge.time_delta:
                label += f"<br/>{edge.time_delta.total_seconds():.0f}s"
            lines.append(f"    {safe_from} -->|{label}| {safe_to}")

        return "\n".join(lines)

    def to_dot(self) -> str:
        """Export graph as Graphviz DOT format.

        Generates a DOT format graph suitable for rendering with Graphviz.
        Root cause nodes are highlighted with a light coral background color.
        The graph uses left-to-right layout (rankdir=LR).

        Returns:
            String containing DOT format graph specification.

        Example:
            >>> dot = graph.to_dot()
            >>> with open('graph.dot', 'w') as f:
            ...     f.write(dot)
            >>> # Render with: dot -Tpng graph.dot -o graph.png
        """
        lines = ["digraph CausalGraph {"]
        lines.append("    rankdir=LR;")
        lines.append("    node [shape=box];")

        # Add nodes
        root_causes = set(self.get_root_causes())
        for node_id, node in self.nodes.items():
            # Escape quotes in node_id
            safe_id = node_id.replace('"', '\\"')
            label = f"{node_id}\\nErrors: {node.error_count}"

            # Highlight root causes
            if node_id in root_causes:
                lines.append(
                    f'    "{safe_id}" [label="{label}", style=filled, fillcolor=lightcoral];'
                )
            else:
                lines.append(f'    "{safe_id}" [label="{label}"];')

        # Add edges
        for edge in self.edges:
            safe_from = edge.from_node.replace('"', '\\"')
            safe_to = edge.to_node.replace('"', '\\"')
            label = f"conf: {edge.confidence:.2f}"
            if edge.time_delta:
                label += f"\\n{edge.time_delta.total_seconds():.0f}s"
            lines.append(f'    "{safe_from}" -> "{safe_to}" [label="{label}"];')

        lines.append("}")
        return "\n".join(lines)

