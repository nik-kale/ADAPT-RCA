"""
LLM-powered reasoning agent for enhanced root cause analysis.
"""
import logging
import json
from typing import List, Optional

from ..models import IncidentGroup, AnalysisResult, RootCause, RecommendedAction
from ..llm.base import LLMProvider, LLMMessage
from .agent import _analyze_error_patterns
from ..constants import (
    LLM_ANALYSIS_TEMPERATURE,
    DEFAULT_LLM_MAX_TOKENS,
    SAMPLE_EVENTS_DISPLAY_COUNT,
    MAX_TOP_SERVICES_DISPLAY,
    MAX_EDGES_DISPLAY
)

logger = logging.getLogger(__name__)


def analyze_with_llm(
    incident: IncidentGroup,
    llm_provider: LLMProvider,
    causal_graph_dict: dict
) -> AnalysisResult:
    """
    Analyze an incident using LLM-powered reasoning.

    Args:
        incident: The incident group to analyze
        llm_provider: LLM provider to use
        causal_graph_dict: Causal graph dictionary

    Returns:
        Analysis results
    """
    if not incident.events:
        return AnalysisResult(
            incident_summary="No events to analyze",
            event_count=0
        )

    logger.info(f"Using LLM for analysis ({llm_provider.model})")

    # Build context
    error_patterns = _analyze_error_patterns(incident.events)
    context = _build_context(incident, causal_graph_dict, error_patterns)

    # Create prompt
    messages = [
        llm_provider.create_system_message(_get_system_prompt()),
        llm_provider.create_user_message(context)
    ]

    try:
        # Get LLM response
        response = llm_provider.complete(
            messages,
            temperature=LLM_ANALYSIS_TEMPERATURE,
            max_tokens=DEFAULT_LLM_MAX_TOKENS
        )

        # Parse response
        result = _parse_llm_response(response.content, incident, causal_graph_dict)

        logger.info(f"LLM analysis complete (tokens: {response.usage.get('total_tokens', 'unknown')})")
        return result

    except Exception as e:
        logger.error(f"LLM analysis failed: {e}", exc_info=True)
        # Fall back to heuristic analysis
        from .agent import analyze_incident_group
        logger.warning("Falling back to heuristic analysis")
        return analyze_incident_group(incident)


def _get_system_prompt() -> str:
    """Get the system prompt for the LLM."""
    return """You are an expert Site Reliability Engineer and incident analyst. Your role is to analyze system logs and events to identify root causes and recommend remediation actions.

When analyzing incidents:
1. Identify temporal patterns and dependencies between services
2. Determine the most likely root cause(s) based on timing and error patterns
3. Provide actionable recommendations with clear priorities
4. Be specific and concrete in your analysis

Provide your analysis in the following JSON format:
{
  "summary": "Brief incident summary",
  "root_causes": [
    {
      "description": "Description of root cause",
      "confidence": 0.0-1.0,
      "evidence": ["Evidence 1", "Evidence 2"]
    }
  ],
  "recommendations": [
    {
      "description": "Specific action to take",
      "priority": 1-5,
      "category": "investigate|fix|monitor|document"
    }
  ]
}

Be concise and focus on actionable insights."""


def _build_context(
    incident: IncidentGroup,
    causal_graph_dict: dict,
    error_patterns: dict
) -> str:
    """
    Build context string for LLM.

    Args:
        incident: Incident group
        causal_graph_dict: Causal graph dictionary
        error_patterns: Error pattern analysis

    Returns:
        Context string
    """
    lines = []

    # Basic stats
    lines.append(f"## Incident Overview")
    lines.append(f"- Events: {len(incident.events)}")
    lines.append(f"- Services: {', '.join(incident.services)}")
    lines.append(f"- Severity: {incident.severity or 'Unknown'}")

    if incident.start_time and incident.end_time:
        duration = (incident.end_time - incident.start_time).total_seconds()
        lines.append(f"- Duration: {duration:.0f} seconds")

    # Causal graph
    lines.append(f"\n## Causal Analysis")
    root_causes = causal_graph_dict.get('root_causes', [])
    if root_causes:
        lines.append(f"- Likely root cause services: {', '.join(root_causes)}")

    nodes = causal_graph_dict.get('nodes', [])
    if nodes:
        lines.append(f"\n### Service Error Counts:")
        for node in sorted(nodes, key=lambda n: n['error_count'], reverse=True)[:MAX_TOP_SERVICES_DISPLAY]:
            lines.append(f"- {node['id']}: {node['error_count']} errors")

    edges = causal_graph_dict.get('edges', [])
    if edges:
        lines.append(f"\n### Temporal Dependencies:")
        for edge in edges[:MAX_EDGES_DISPLAY]:
            time_delta = edge.get('time_delta_seconds', 0)
            conf = edge['confidence']
            lines.append(
                f"- {edge['from']} → {edge['to']} "
                f"(confidence: {conf:.2f}, {time_delta:.0f}s apart)"
            )

    # Error patterns
    lines.append(f"\n## Error Patterns")
    if error_patterns.get('error_types'):
        lines.append(f"Error levels: {error_patterns['error_types']}")

    if error_patterns.get('most_common_errors'):
        lines.append(f"\nMost common errors:")
        for err in error_patterns['most_common_errors'][:3]:
            lines.append(f"- ({err['count']}x) {err['message'][:100]}")

    # Sample events
    lines.append(f"\n## Sample Events")
    for i, event in enumerate(incident.events[:SAMPLE_EVENTS_DISPLAY_COUNT]):
        ts = event.timestamp.isoformat() if event.timestamp else "unknown time"
        lines.append(
            f"{i+1}. [{ts}] {event.service or 'unknown'} - "
            f"{event.level or 'INFO'}: {event.message[:80] if event.message else 'No message'}"
        )

    if len(incident.events) > SAMPLE_EVENTS_DISPLAY_COUNT:
        lines.append(f"... and {len(incident.events) - SAMPLE_EVENTS_DISPLAY_COUNT} more events")

    return "\n".join(lines)


def _parse_llm_response(
    response_text: str,
    incident: IncidentGroup,
    causal_graph_dict: dict
) -> AnalysisResult:
    """
    Parse LLM response into AnalysisResult.

    Args:
        response_text: LLM response text
        incident: Incident group
        causal_graph_dict: Causal graph dictionary

    Returns:
        AnalysisResult
    """
    try:
        # Try to extract JSON from response
        # LLMs sometimes wrap JSON in markdown code blocks
        response_text = response_text.strip()

        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()

        data = json.loads(response_text)

        # Parse root causes
        root_causes = []
        for rc_data in data.get('root_causes', []):
            root_causes.append(
                RootCause(
                    description=rc_data.get('description', 'Unknown'),
                    confidence=rc_data.get('confidence', 0.5),
                    evidence=rc_data.get('evidence', [])
                )
            )

        # Parse recommendations
        recommendations = []
        for rec_data in data.get('recommendations', []):
            recommendations.append(
                RecommendedAction(
                    description=rec_data.get('description', 'Unknown'),
                    priority=rec_data.get('priority', 3),
                    category=rec_data.get('category', 'investigate')
                )
            )

        # Build time range
        time_range = None
        if incident.start_time and incident.end_time:
            time_range = {
                "start": incident.start_time,
                "end": incident.end_time
            }

        return AnalysisResult(
            incident_summary=data.get('summary', 'LLM analysis completed'),
            probable_root_causes=root_causes,
            recommended_actions=recommendations,
            affected_services=incident.services,
            event_count=len(incident.events),
            time_range=time_range,
            causal_graph=causal_graph_dict,
            metadata={
                "llm_analysis": True,
                "severity": incident.severity
            }
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.debug(f"Response text: {response_text}")

        # Fall back to basic parsing
        return AnalysisResult(
            incident_summary=response_text[:200] if response_text else "LLM analysis failed",
            probable_root_causes=[
                RootCause(
                    description="See full LLM response for details",
                    confidence=0.5,
                    evidence=[response_text[:500]]
                )
            ],
            affected_services=incident.services,
            event_count=len(incident.events),
            causal_graph=causal_graph_dict
        )
