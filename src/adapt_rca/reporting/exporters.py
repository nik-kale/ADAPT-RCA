from typing import Dict, Any
import json
import logging
from pathlib import Path

from ..utils import validate_output_path, PathValidationError

logger = logging.getLogger(__name__)


def export_json(result: Dict, output_path: str | Path) -> None:
    """
    Export analysis results to JSON format.

    Args:
        result: Analysis results dictionary
        output_path: Path to write JSON file

    Raises:
        PathValidationError: If output path is invalid
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


def export_markdown(result: Dict, output_path: str | Path) -> None:
    """
    Export analysis results to Markdown format.

    Args:
        result: Analysis results dictionary
        output_path: Path to write Markdown file

    Raises:
        PathValidationError: If output path is invalid
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
    """
    Export causal graph as Mermaid diagram.

    Args:
        causal_graph_dict: Causal graph dictionary from CausalGraph.to_dict()
        output_path: Path to write Mermaid file

    Raises:
        PathValidationError: If output path is invalid
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
    """
    Export causal graph as Graphviz DOT format.

    Args:
        causal_graph_dict: Causal graph dictionary from CausalGraph.to_dict()
        output_path: Path to write DOT file

    Raises:
        PathValidationError: If output path is invalid
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
