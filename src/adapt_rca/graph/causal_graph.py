from typing import List, Dict, Optional, Set, Any
from datetime import datetime, timedelta
import logging

from ..models import Event, IncidentGroup

logger = logging.getLogger(__name__)


class CausalNode:
    """Represents a node (service/component) in the causal graph."""

    def __init__(self, node_id: str, metadata: Optional[Dict[str, Any]] = None):
        self.id = node_id
        self.metadata = metadata or {}
        self.error_count = 0
        self.first_error: Optional[datetime] = None
        self.last_error: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "metadata": self.metadata,
            "error_count": self.error_count,
            "first_error": self.first_error.isoformat() if self.first_error else None,
            "last_error": self.last_error.isoformat() if self.last_error else None,
        }


class CausalEdge:
    """Represents a directed edge showing potential causation."""

    def __init__(
        self,
        from_node: str,
        to_node: str,
        evidence: Optional[List[str]] = None,
        time_delta: Optional[timedelta] = None,
        confidence: float = 0.5
    ):
        self.from_node = from_node
        self.to_node = to_node
        self.evidence = evidence or []
        self.time_delta = time_delta
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "from": self.from_node,
            "to": self.to_node,
            "evidence": self.evidence,
            "time_delta_seconds": self.time_delta.total_seconds() if self.time_delta else None,
            "confidence": self.confidence,
        }


class CausalGraph:
    """
    Builds and manages a directed graph of components, errors, and dependencies.

    This graph represents the causal relationships between services based on
    temporal patterns and error propagation.
    """

    def __init__(self):
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
        """
        edge = CausalEdge(from_node, to_node, evidence, time_delta, confidence)
        self.edges.append(edge)
        logger.debug(f"Added edge: {from_node} -> {to_node} (confidence: {confidence})")

    def record_error(self, service: str, timestamp: Optional[datetime], message: str) -> None:
        """
        Record an error event for a service.

        Args:
            service: Service name
            timestamp: Error timestamp
            message: Error message
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
        """
        Build a causal graph from an incident group.

        Analyzes temporal patterns and service relationships to infer causation.

        Args:
            incident: The incident group to analyze

        Returns:
            A CausalGraph representing the incident
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
        max_time_window = timedelta(minutes=5)

        for i, event1 in enumerate(sorted_events):
            if not event1.service:
                continue

            for event2 in sorted_events[i + 1:]:
                if not event2.service or event2.service == event1.service:
                    continue

                time_diff = event2.timestamp - event1.timestamp

                if time_diff > max_time_window:
                    break  # Events too far apart

                # Calculate confidence based on time proximity
                # Closer events = higher confidence
                confidence = 1.0 - (time_diff.total_seconds() / max_time_window.total_seconds())
                confidence = max(0.1, min(0.9, confidence))  # Clamp between 0.1 and 0.9

                # Check if edge already exists
                existing = any(
                    e.from_node == event1.service and e.to_node == event2.service
                    for e in graph.edges
                )

                if not existing:
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

        return graph

    def get_root_causes(self) -> List[str]:
        """
        Identify potential root cause services.

        Root causes are services with outgoing edges but few/no incoming edges,
        and errors that occurred earliest.

        Returns:
            List of service IDs that are likely root causes
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
        """
        Export graph as a dictionary.

        Returns:
            Dictionary with nodes and edges
        """
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
            "root_causes": self.get_root_causes()
        }

    def to_mermaid(self) -> str:
        """
        Export graph as Mermaid diagram syntax.

        Returns:
            Mermaid diagram as string
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
        """
        Export graph as Graphviz DOT format.

        Returns:
            DOT format string
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

