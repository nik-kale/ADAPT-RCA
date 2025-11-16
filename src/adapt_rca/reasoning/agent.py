"""Heuristic-based incident analysis agent.

This module provides the core analysis engine for ADAPT-RCA that uses
heuristic methods to identify root causes and generate recommendations.
It builds causal graphs, analyzes error patterns, and produces structured
analysis results.

Functions:
    analyze_incident: Legacy interface for analyzing event dictionaries.
    analyze_incident_group: Main analysis function for IncidentGroup objects.

Private Functions:
    _analyze_error_patterns: Identify patterns in error messages and types.
    _generate_summary: Create human-readable incident summary.
    _identify_root_causes: Determine probable root causes with evidence.
    _generate_recommendations: Produce prioritized remediation actions.

Example:
    >>> from adapt_rca.reasoning.agent import analyze_incident_group
    >>> from adapt_rca.models import IncidentGroup, Event
    >>>
    >>> events = [Event(...), Event(...)]
    >>> incident = IncidentGroup.from_events(events)
    >>> result = analyze_incident_group(incident)
    >>> print(result.incident_summary)
    >>> for rc in result.probable_root_causes:
    ...     print(f"{rc.description} (confidence: {rc.confidence})")
"""
from typing import List, Dict, Optional, Any
import logging
from collections import Counter

from ..models import Event, IncidentGroup, AnalysisResult, RootCause, RecommendedAction
from ..graph.causal_graph import CausalGraph
from ..constants import (
    REPEATED_ERROR_THRESHOLD,
    HIGH_CONFIDENCE_THRESHOLD,
    MEDIUM_CONFIDENCE_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    MAX_ERROR_MESSAGE_LENGTH,
    VALID_ACTION_CATEGORIES
)

logger = logging.getLogger(__name__)


def analyze_incident(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze an incident from a list of event dictionaries.

    This is the legacy interface for backward compatibility with older code
    that expects dictionary inputs and outputs.

    Args:
        events: List of event dictionaries with keys like 'timestamp',
            'service', 'level', 'message', etc.

    Returns:
        Analysis results as dictionary with keys:
            - incident_summary (str)
            - probable_root_causes (List[str])
            - recommended_actions (List[str])

    Example:
        >>> events = [
        ...     {"timestamp": "2024-01-01T10:00:00Z", "service": "api", "message": "Error"},
        ...     {"timestamp": "2024-01-01T10:01:00Z", "service": "db", "message": "Timeout"}
        ... ]
        >>> result = analyze_incident(events)
        >>> print(result["incident_summary"])
    """
    # Convert dict events to Event objects
    event_objects = [Event(**e) for e in events]
    incident = IncidentGroup.from_events(event_objects)

    # Perform analysis
    result = analyze_incident_group(incident)

    # Return legacy format
    return result.to_legacy_dict()


def analyze_incident_group(incident: IncidentGroup) -> AnalysisResult:
    """Analyze an incident group and produce analysis results.

    Uses heuristic analysis and causal graph building to identify
    root causes and recommend actions. This is the main analysis
    function that orchestrates the entire analysis pipeline.

    The analysis process:
    1. Build causal graph from event timing and relationships
    2. Identify root cause services using graph topology
    3. Analyze error patterns and message frequencies
    4. Generate human-readable summary
    5. Identify probable root causes with evidence
    6. Generate prioritized recommendations

    Args:
        incident: The incident group containing related events to analyze.

    Returns:
        AnalysisResult object containing:
            - incident_summary: Human-readable summary
            - probable_root_causes: List of RootCause objects with evidence
            - recommended_actions: Prioritized list of RecommendedAction objects
            - affected_services: List of service names
            - causal_graph: Graph showing service relationships
            - metadata: Additional analysis metadata

    Example:
        >>> from adapt_rca.models import Event, IncidentGroup
        >>> events = [
        ...     Event(service="api", message="Connection failed"),
        ...     Event(service="db", message="Query timeout")
        ... ]
        >>> incident = IncidentGroup.from_events(events)
        >>> result = analyze_incident_group(incident)
        >>> print(result.incident_summary)
        >>> for cause in result.probable_root_causes:
        ...     print(f"{cause.description}: {cause.confidence}")
    """
    if not incident.events:
        return AnalysisResult(
            incident_summary="No events to analyze",
            event_count=0
        )

    logger.info(f"Analyzing incident with {len(incident.events)} events")

    # Build causal graph
    causal_graph = CausalGraph.from_incident_group(incident)
    root_cause_services = causal_graph.get_root_causes()

    # Analyze error patterns
    error_patterns = _analyze_error_patterns(incident.events)

    # Generate summary
    summary = _generate_summary(incident, root_cause_services, error_patterns)

    # Identify root causes
    root_causes = _identify_root_causes(
        incident, causal_graph, root_cause_services, error_patterns
    )

    # Generate recommendations
    recommendations = _generate_recommendations(
        incident, root_cause_services, error_patterns
    )

    # Build time range
    time_range = None
    if incident.start_time and incident.end_time:
        time_range = {
            "start": incident.start_time,
            "end": incident.end_time
        }

    return AnalysisResult(
        incident_summary=summary,
        probable_root_causes=root_causes,
        recommended_actions=recommendations,
        affected_services=incident.services,
        event_count=len(incident.events),
        time_range=time_range,
        causal_graph=causal_graph.to_dict(),
        metadata={
            "severity": incident.severity,
            "error_patterns": error_patterns,
        }
    )


def _analyze_error_patterns(events: List[Event]) -> Dict[str, Any]:
    """Analyze error patterns in events.

    Identifies common patterns including most frequent error messages,
    distribution of error types/levels, and temporal patterns.

    Args:
        events: List of Event objects to analyze.

    Returns:
        Dictionary containing:
            - most_common_errors: List of most frequent error messages with counts
            - error_types: Dictionary mapping error levels to their counts
            - temporal_distribution: Time-based distribution info (currently empty)

    Example:
        >>> events = [Event(message="DB timeout"), Event(message="DB timeout")]
        >>> patterns = _analyze_error_patterns(events)
        >>> patterns["most_common_errors"][0]
        {'message': 'DB timeout', 'count': 2}
    """
    patterns = {
        "most_common_errors": [],
        "error_types": {},
        "temporal_distribution": {}
    }

    # Count error messages
    messages = [e.message for e in events if e.message]
    if messages:
        message_counts = Counter(messages)
        patterns["most_common_errors"] = [
            {"message": msg, "count": count}
            for msg, count in message_counts.most_common(5)
        ]

    # Count error levels
    levels = [e.level for e in events if e.level]
    if levels:
        patterns["error_types"] = dict(Counter(levels))

    return patterns


def _generate_summary(
    incident: IncidentGroup,
    root_causes: List[str],
    error_patterns: Dict[str, Any]
) -> str:
    """Generate human-readable incident summary.

    Creates a concise summary describing the incident's scope, affected
    services, identified root causes, and severity.

    Args:
        incident: The incident group containing events and metadata.
        root_causes: List of service names identified as root causes.
        error_patterns: Error pattern analysis from _analyze_error_patterns.

    Returns:
        Multi-sentence summary string describing the incident.

    Example:
        >>> summary = _generate_summary(incident, ["api-service"], patterns)
        >>> print(summary)
        'Incident involving 5 events across 2 service(s). Affected services: api-service, database. Likely originated in: api-service. Highest severity: ERROR.'
    """
    event_count = len(incident.events)
    service_count = len(incident.services)

    summary_parts = []

    # Basic stats
    summary_parts.append(
        f"Incident involving {event_count} events across {service_count} service(s)"
    )

    # Services
    if incident.services:
        services_str = ", ".join(incident.services[:3])
        if len(incident.services) > 3:
            services_str += f", and {len(incident.services) - 3} more"
        summary_parts.append(f"Affected services: {services_str}")

    # Root causes
    if root_causes:
        root_str = ", ".join(root_causes)
        summary_parts.append(f"Likely originated in: {root_str}")

    # Severity
    if incident.severity:
        summary_parts.append(f"Highest severity: {incident.severity}")

    return ". ".join(summary_parts) + "."


def _identify_root_causes(
    incident: IncidentGroup,
    causal_graph: CausalGraph,
    root_cause_services: List[str],
    error_patterns: Dict[str, Any]
) -> List[RootCause]:
    """Identify probable root causes with evidence and confidence scores.

    Combines graph-based analysis (topology-based root causes) with
    pattern-based analysis (repeated errors) to identify likely root causes.
    Each root cause includes supporting evidence and a confidence score.

    Args:
        incident: The incident group being analyzed.
        causal_graph: Built causal graph showing service relationships.
        root_cause_services: Services identified as root causes from graph topology.
        error_patterns: Error pattern analysis results.

    Returns:
        List of RootCause objects, each containing:
            - description: Human-readable root cause description
            - confidence: Confidence score (0.0 to 1.0)
            - evidence: List of supporting evidence strings

    Example:
        >>> causes = _identify_root_causes(incident, graph, ["api"], patterns)
        >>> for cause in causes:
        ...     print(f"{cause.description} ({cause.confidence})")
        ...     for evidence in cause.evidence:
        ...         print(f"  - {evidence}")
    """
    root_causes = []

    # Add root cause services from graph
    for service in root_cause_services:
        node = causal_graph.nodes.get(service)
        if node:
            evidence = [
                f"Service {service} had {node.error_count} error(s)",
                f"Errors started at {node.first_error.isoformat() if node.first_error else 'unknown time'}"
            ]

            # Find outgoing edges to show impact
            outgoing = [e for e in causal_graph.edges if e.from_node == service]
            if outgoing:
                impacted = [e.to_node for e in outgoing]
                evidence.append(f"Likely caused errors in: {', '.join(impacted)}")

            root_causes.append(
                RootCause(
                    description=f"{service} service failure or degradation",
                    confidence=HIGH_CONFIDENCE_THRESHOLD,
                    evidence=evidence
                )
            )

    # Add pattern-based root causes
    if error_patterns.get("most_common_errors") and len(incident.events) > 0:
        most_common = error_patterns["most_common_errors"][0]
        if most_common["count"] >= len(incident.events) * REPEATED_ERROR_THRESHOLD:
            percentage = (most_common['count'] / len(incident.events)) * 100
            root_causes.append(
                RootCause(
                    description=f"Repeated error: {most_common['message'][:MAX_ERROR_MESSAGE_LENGTH]}",
                    confidence=MEDIUM_CONFIDENCE_THRESHOLD,
                    evidence=[
                        f"Occurred {most_common['count']} times",
                        f"Represents {percentage:.1f}% of all errors"
                    ]
                )
            )

    # If no specific root causes found, provide generic one
    if not root_causes:
        root_causes.append(
            RootCause(
                description="Service interdependency issue or cascading failure",
                confidence=LOW_CONFIDENCE_THRESHOLD,
                evidence=[
                    f"{len(incident.services)} services affected",
                    "Requires deeper investigation to pinpoint exact cause"
                ]
            )
        )

    return root_causes


def _generate_recommendations(
    incident: IncidentGroup,
    root_cause_services: List[str],
    error_patterns: Dict[str, Any]
) -> List[RecommendedAction]:
    """Generate prioritized recommended actions for remediation.

    Creates a list of actionable recommendations organized by category
    (investigate, fix, monitor, document) and priority level. Recommendations
    are tailored to the specific incident characteristics.

    Args:
        incident: The incident group being analyzed.
        root_cause_services: Services identified as root causes.
        error_patterns: Error pattern analysis results.

    Returns:
        List of RecommendedAction objects, each containing:
            - description: Action description
            - priority: Priority level (1=critical to 5=low)
            - category: Action category (investigate/fix/monitor/document)

    Example:
        >>> actions = _generate_recommendations(incident, ["api"], patterns)
        >>> for action in sorted(actions, key=lambda a: a.priority):
        ...     print(f"[P{action.priority}] {action.description} ({action.category})")
    """
    recommendations = []

    # Recommendations for root cause services
    if root_cause_services:
        recommendations.append(
            RecommendedAction(
                description=f"Investigate {', '.join(root_cause_services)} for root cause",
                priority=PRIORITY_CRITICAL,
                category="investigate"
            )
        )

    # Check for critical errors
    if error_patterns.get("error_types", {}).get("CRITICAL") or \
       error_patterns.get("error_types", {}).get("FATAL"):
        recommendations.append(
            RecommendedAction(
                description="Review critical/fatal errors immediately",
                priority=PRIORITY_CRITICAL,
                category="investigate"
            )
        )

    # Service-specific recommendations
    for service in incident.services[:3]:  # Top 3 services
        recommendations.append(
            RecommendedAction(
                description=f"Check {service} logs, metrics, and recent deployments",
                priority=PRIORITY_HIGH,
                category="investigate"
            )
        )

    # Generic monitoring recommendation
    recommendations.append(
        RecommendedAction(
            description="Set up alerts for similar error patterns",
            priority=PRIORITY_MEDIUM,
            category="monitor"
        )
    )

    # Generic documentation recommendation
    recommendations.append(
        RecommendedAction(
            description="Document findings and add to incident postmortem",
            priority=PRIORITY_LOW,
            category="document"
        )
    )

    return recommendations
