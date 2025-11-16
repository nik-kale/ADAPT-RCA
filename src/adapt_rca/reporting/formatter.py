"""Human-readable formatting of incident analysis results.

This module provides functions to format analysis results into text-based
representations suitable for console output or text files.

Functions:
    format_human_readable: Format analysis results as human-readable text.

Example:
    >>> from adapt_rca.reporting.formatter import format_human_readable
    >>> result = {
    ...     "incident_summary": "Database connection failure",
    ...     "probable_root_causes": ["DB timeout", "Network issue"],
    ...     "recommended_actions": ["Check DB logs", "Verify network"]
    ... }
    >>> print(format_human_readable(result))
"""
from typing import Dict, Any, List


def format_human_readable(result: Dict[str, Any]) -> str:
    """Format analysis results as human-readable text.

    Converts a structured analysis result dictionary into a formatted
    text string suitable for display in terminals or text files. The
    output includes incident summary, root causes, and recommended actions.

    Args:
        result: Dictionary containing analysis results with keys:
            - incident_summary (str): Brief description of the incident
            - probable_root_causes (List[str]): List of identified root causes
            - recommended_actions (List[str]): List of suggested remediation steps

    Returns:
        Formatted multi-line string with incident analysis information.

    Example:
        >>> result = {
        ...     "incident_summary": "API service degradation",
        ...     "probable_root_causes": ["Database connection pool exhaustion"],
        ...     "recommended_actions": ["Increase pool size", "Add connection monitoring"]
        ... }
        >>> output = format_human_readable(result)
        >>> print(output)
        # Incident Analysis
        <BLANKLINE>
        Summary: API service degradation
        <BLANKLINE>
        Probable root causes:
        - Database connection pool exhaustion
        <BLANKLINE>
        Recommended actions:
        - Increase pool size
        - Add connection monitoring
    """
    lines: List[str] = []
    lines.append("# Incident Analysis")
    lines.append("")
    lines.append(f"Summary: {result.get('incident_summary', 'N/A')}")
    lines.append("")
    lines.append("Probable root causes:")
    for rc in result.get("probable_root_causes", []):
        lines.append(f"- {rc}")
    lines.append("")
    lines.append("Recommended actions:")
    for action in result.get("recommended_actions", []):
        lines.append(f"- {action}")
    return "\n".join(lines)
