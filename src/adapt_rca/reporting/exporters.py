from typing import Dict
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

    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        logger.info(f"Exported Markdown to: {path}")
    except Exception as e:
        logger.error(f"Failed to export Markdown: {e}")
        raise
