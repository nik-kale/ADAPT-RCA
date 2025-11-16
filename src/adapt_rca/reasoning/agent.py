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


def analyze_incident(events: List[Dict]) -> Dict:
    """
    Analyze an incident from a list of event dictionaries.

    This is the legacy interface for backward compatibility.

    Args:
        events: List of event dictionaries

    Returns:
        Analysis results as dictionary
    """
    # Convert dict events to Event objects
    event_objects = [Event(**e) for e in events]
    incident = IncidentGroup.from_events(event_objects)

    # Perform analysis
    result = analyze_incident_group(incident)

    # Return legacy format
    return result.to_legacy_dict()


def analyze_incident_group(incident: IncidentGroup) -> AnalysisResult:
    """
    Analyze an incident group and produce analysis results.

    Uses heuristic analysis and causal graph building to identify
    root causes and recommend actions.

    Args:
        incident: The incident group to analyze

    Returns:
        Complete analysis results
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
    """
    Analyze error patterns in events.

    Args:
        events: List of Event objects

    Returns:
        Dictionary of error patterns
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
    """
    Generate incident summary.

    Args:
        incident: The incident group
        root_causes: Identified root cause services
        error_patterns: Error pattern analysis

    Returns:
        Human-readable summary
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
    """
    Identify probable root causes.

    Args:
        incident: The incident group
        causal_graph: Built causal graph
        root_cause_services: Services identified as root causes
        error_patterns: Error pattern analysis

    Returns:
        List of RootCause objects
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
    """
    Generate recommended actions.

    Args:
        incident: The incident group
        root_cause_services: Services identified as root causes
        error_patterns: Error pattern analysis

    Returns:
        List of RecommendedAction objects
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
