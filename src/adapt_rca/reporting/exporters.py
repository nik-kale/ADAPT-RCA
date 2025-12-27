"""Export incident analysis results to various file formats.

This module provides exporters for saving analysis results and causal graphs
to different file formats including JSON, Markdown, Mermaid diagrams, and
Graphviz DOT format.

Functions:
    export_json: Export results to JSON format.
    export_markdown: Export results to Markdown report.
    export_graph_mermaid: Export causal graph as Mermaid diagram.
    export_graph_dot: Export causal graph as Graphviz DOT format.

Example:
    >>> from adapt_rca.reporting.exporters import export_json, export_markdown
    >>> result = {"incident_summary": "Service failure", ...}
    >>> export_json(result, "output/analysis.json")
    >>> export_markdown(result, "output/report.md")
"""
from typing import Dict, Any
import json
import logging
from pathlib import Path

from ..utils import validate_output_path, PathValidationError

logger = logging.getLogger(__name__)


def export_json(result: Dict[str, Any], output_path: str | Path) -> None:
    """Export analysis results to JSON format.

    Serializes the analysis results dictionary to a formatted JSON file
    with 2-space indentation and UTF-8 encoding. The output path will be
    validated and must have a .json extension.

    Args:
        result: Analysis results dictionary containing incident summary,
            root causes, recommended actions, and optional causal graph.
        output_path: Path where the JSON file should be written. Must have
            .json extension. Can be string or Path object.

    Raises:
        PathValidationError: If output path is invalid or has wrong extension.
        IOError: If file cannot be written.

    Example:
        >>> result = {
        ...     "incident_summary": "Database timeout",
        ...     "probable_root_causes": ["High query load"],
        ...     "recommended_actions": ["Optimize queries"]
        ... }
        >>> export_json(result, "output/analysis.json")
    """
    path = validate_output_path(
        output_path,
        allow_overwrite=True,
        allowed_extensions={'.json'}
    )

    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"Exported JSON to: {path}")
    except Exception as e:
        logger.error(f"Failed to export JSON: {e}")
        raise


def export_markdown(result: Dict[str, Any], output_path: str | Path) -> None:
    """Export analysis results to Markdown format.

    Generates a formatted Markdown report with sections for summary,
    root causes, recommended actions, and causal analysis (if available).
    The output includes proper Markdown headers and bullet lists.

    Args:
        result: Analysis results dictionary with keys:
            - incident_summary (str): Brief incident description
            - probable_root_causes (List[str]): Identified root causes
            - recommended_actions (List[str]): Suggested remediation steps
            - causal_graph (Dict, optional): Causal graph data including
              root_causes, nodes, and edges
        output_path: Path where the Markdown file should be written. Must have
            .md or .markdown extension. Can be string or Path object.

    Raises:
        PathValidationError: If output path is invalid or has wrong extension.
        IOError: If file cannot be written.

    Example:
        >>> result = {
        ...     "incident_summary": "API service degradation",
        ...     "probable_root_causes": ["Database connection pool exhaustion"],
        ...     "recommended_actions": ["Increase pool size"],
        ...     "causal_graph": {"root_causes": ["database"], "nodes": [...]}
        ... }
        >>> export_markdown(result, "output/incident_report.md")
    """
    path = validate_output_path(
        output_path,
        allow_overwrite=True,
        allowed_extensions={'.md', '.markdown'}
    )

    lines = []
    lines.append("# Incident Analysis Report")
    lines.append("")
    lines.append("## Summary")
    lines.append(result.get('incident_summary', 'N/A'))
    lines.append("")
    lines.append("## Probable Root Causes")
    for rc in result.get("probable_root_causes", []):
        lines.append(f"- {rc}")
    lines.append("")
    lines.append("## Recommended Actions")
    for action in result.get("recommended_actions", []):
        lines.append(f"- {action}")
    lines.append("")

    # Add causal graph if available
    causal_graph = result.get('causal_graph')
    if causal_graph and causal_graph.get('root_causes'):
        lines.append("## Causal Analysis")
        lines.append("")
        lines.append("**Identified Root Causes:**")
        for root_cause in causal_graph['root_causes']:
            lines.append(f"- {root_cause}")
        lines.append("")

        if causal_graph.get('nodes'):
            lines.append("**Affected Services:**")
            for node in causal_graph['nodes']:
                lines.append(f"- {node['id']}: {node['error_count']} errors")
            lines.append("")

    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        logger.info(f"Exported Markdown to: {path}")
    except Exception as e:
        logger.error(f"Failed to export Markdown: {e}")
        raise


def export_graph_mermaid(
    causal_graph_dict: Dict[str, Any],
    output_path: str | Path
) -> None:
    """Export causal graph as Mermaid diagram.

    Generates a Mermaid flowchart (graph TD) syntax file that can be
    rendered into a visual diagram. The diagram shows services as nodes
    with error counts, and edges labeled with confidence scores and time deltas.

    Args:
        causal_graph_dict: Causal graph dictionary from CausalGraph.to_dict()
            with keys:
            - nodes (List[Dict]): List of node dictionaries with 'id' and 'error_count'
            - edges (List[Dict]): List of edge dictionaries with 'from', 'to',
              'confidence', and optional 'time_delta_seconds'
        output_path: Path where the Mermaid file should be written. Must have
            .mmd or .mermaid extension. Can be string or Path object.

    Raises:
        PathValidationError: If output path is invalid or has wrong extension.
        IOError: If file cannot be written.

    Example:
        >>> from adapt_rca.graph.causal_graph import CausalGraph
        >>> graph = CausalGraph.from_incident_group(incident)
        >>> graph_dict = graph.to_dict()
        >>> export_graph_mermaid(graph_dict, "output/causal_graph.mmd")
        >>> # View in Mermaid Live Editor or render with mermaid-cli
    """
    path = validate_output_path(
        output_path,
        allow_overwrite=True,
        allowed_extensions={'.mmd', '.mermaid'}
    )

    # Reconstruct basic graph from dict
    lines = ["graph TD"]

    # Add nodes
    for node in causal_graph_dict.get('nodes', []):
        node_id = node['id'].replace("-", "_").replace(".", "_")
        label = f"{node['id']}<br/>Errors: {node['error_count']}"
        lines.append(f"    {node_id}[\"{label}\"]")

    # Add edges
    for edge in causal_graph_dict.get('edges', []):
        from_id = edge['from'].replace("-", "_").replace(".", "_")
        to_id = edge['to'].replace("-", "_").replace(".", "_")
        label = f"{edge['confidence']:.2f}"
        if edge.get('time_delta_seconds'):
            label += f"<br/>{edge['time_delta_seconds']:.0f}s"
        lines.append(f"    {from_id} -->|\"{label}\"| {to_id}")

    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        logger.info(f"Exported Mermaid diagram to: {path}")
    except Exception as e:
        logger.error(f"Failed to export Mermaid: {e}")
        raise


def export_graph_dot(
    causal_graph_dict: Dict[str, Any],
    output_path: str | Path
) -> None:
    """Export causal graph as Graphviz DOT format.

    Generates a DOT format file that can be rendered with Graphviz tools
    into various image formats (PNG, SVG, PDF, etc.). Root cause nodes are
    highlighted with a light coral background color.

    Args:
        causal_graph_dict: Causal graph dictionary from CausalGraph.to_dict()
            with keys:
            - nodes (List[Dict]): List of node dictionaries with 'id' and 'error_count'
            - edges (List[Dict]): List of edge dictionaries with 'from', 'to',
              'confidence', and optional 'time_delta_seconds'
            - root_causes (List[str]): List of root cause service IDs
        output_path: Path where the DOT file should be written. Must have
            .dot or .gv extension. Can be string or Path object.

    Raises:
        PathValidationError: If output path is invalid or has wrong extension.
        IOError: If file cannot be written.

    Example:
        >>> from adapt_rca.graph.causal_graph import CausalGraph
        >>> graph = CausalGraph.from_incident_group(incident)
        >>> graph_dict = graph.to_dict()
        >>> export_graph_dot(graph_dict, "output/causal_graph.dot")
        >>> # Render with: dot -Tpng output/causal_graph.dot -o graph.png
        >>> # Or: dot -Tsvg output/causal_graph.dot -o graph.svg
    """
    path = validate_output_path(
        output_path,
        allow_overwrite=True,
        allowed_extensions={'.dot', '.gv'}
    )

    lines = ["digraph CausalGraph {"]
    lines.append("    rankdir=LR;")
    lines.append("    node [shape=box];")

    # Get root causes
    root_causes = set(causal_graph_dict.get('root_causes', []))

    # Add nodes
    for node in causal_graph_dict.get('nodes', []):
        node_id = node['id'].replace('"', '\\"')
        label = f"{node['id']}\\nErrors: {node['error_count']}"

        if node['id'] in root_causes:
            lines.append(
                f'    "{node_id}" [label="{label}", style=filled, fillcolor=lightcoral];'
            )
        else:
            lines.append(f'    "{node_id}" [label="{label}"];')

    # Add edges
    for edge in causal_graph_dict.get('edges', []):
        from_id = edge['from'].replace('"', '\\"')
        to_id = edge['to'].replace('"', '\\"')
        label = f"conf: {edge['confidence']:.2f}"
        if edge.get('time_delta_seconds'):
            label += f"\\n{edge['time_delta_seconds']:.0f}s"
        lines.append(f'    "{from_id}" -> "{to_id}" [label="{label}"];')

    lines.append("}")

    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        logger.info(f"Exported DOT diagram to: {path}")
    except Exception as e:
        logger.error(f"Failed to export DOT: {e}")
        raise
