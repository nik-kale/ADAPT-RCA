from typing import List, Dict, Tuple, Optional

from ..exceptions import GraphError, NodeNotFoundError, GraphBuildError


class CausalGraph:
    """
    Builds and manages a directed graph of components, errors, and dependencies.

    This is a placeholder implementation. In a full version, this would:
    - Build nodes from services/components
    - Add edges based on temporal relationships and dependencies
    - Annotate edges with evidence (log lines, metrics, time deltas)
    """

    def __init__(self):
        self.nodes = []
        self.edges = []
        self._node_ids = set()

    def add_node(self, node_id: str, metadata: Dict = None):
        """
        Add a node (service/component) to the graph.
        
        Args:
            node_id: Unique node identifier
            metadata: Optional node metadata
            
        Raises:
            GraphBuildError: If node_id is invalid or already exists
        """
        if not node_id or not isinstance(node_id, str):
            raise GraphBuildError("Node ID must be a non-empty string")
        
        if node_id in self._node_ids:
            raise GraphBuildError(f"Node '{node_id}' already exists")
        
        self.nodes.append({"id": node_id, "metadata": metadata or {}})
        self._node_ids.add(node_id)

    def add_edge(self, from_node: str, to_node: str, evidence: List[str] = None):
        """
        Add a directed edge with optional evidence.
        
        Args:
            from_node: Source node ID
            to_node: Target node ID
            evidence: Optional evidence list
            
        Raises:
            NodeNotFoundError: If either node doesn't exist
            GraphBuildError: If edge is invalid
        """
        if from_node not in self._node_ids:
            raise NodeNotFoundError(f"Source node '{from_node}' not found")
        
        if to_node not in self._node_ids:
            raise NodeNotFoundError(f"Target node '{to_node}' not found")
        
        if from_node == to_node:
            raise GraphBuildError("Self-loops are not allowed")
        
        self.edges.append({
            "from": from_node,
            "to": to_node,
            "evidence": evidence or []
        })

    def get_node(self, node_id: str) -> Optional[Dict]:
        """
        Get node by ID.
        
        Args:
            node_id: Node identifier
            
        Returns:
            Node dictionary or None
            
        Raises:
            NodeNotFoundError: If node doesn't exist
        """
        for node in self.nodes:
            if node["id"] == node_id:
                return node
        
        raise NodeNotFoundError(f"Node '{node_id}' not found")

    def to_dict(self) -> Dict:
        """
        Export graph as a dictionary.
        
        Returns:
            Graph dictionary with nodes and edges
        """
        try:
            return {
                "nodes": self.nodes,
                "edges": self.edges
            }
        except (AttributeError, KeyError) as e:
            raise GraphError(f"Failed to export graph: {e}") from e
