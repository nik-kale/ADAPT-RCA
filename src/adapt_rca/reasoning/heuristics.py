"""Event grouping heuristics for incident detection and clustering.

This module provides various heuristic algorithms for grouping related events
into incident candidates. Different strategies are provided based on temporal
proximity, service relationships, and event characteristics.

Functions:
    simple_grouping: Basic grouping that treats all events as a single incident.
    time_window_grouping: Groups events within a specified time window.
    service_based_grouping: Groups events by service and time window.

Example:
    >>> from adapt_rca.reasoning.heuristics import time_window_grouping
    >>> from adapt_rca.models import Event
    >>>
    >>> events = [Event(...), Event(...)]
    >>> incidents = time_window_grouping(events, window_minutes=15)
    >>> print(f"Found {len(incidents)} incidents")
"""
from typing import List, Dict, Any
from datetime import timedelta
import logging

from ..models import Event, IncidentGroup

logger = logging.getLogger(__name__)


def simple_grouping(events: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Very basic grouping: put all events into a single incident candidate.

    This is the simplest grouping strategy that treats all provided events
    as part of a single incident. Useful for testing or when all events
    are known to be related.

    Args:
        events: List of event dictionaries to group.

    Returns:
        List containing a single group with all events, or empty list if
        no events provided.

    Example:
        >>> events = [{"message": "Error 1"}, {"message": "Error 2"}]
        >>> groups = simple_grouping(events)
        >>> len(groups)  # Should be 1
        1
        >>> len(groups[0])  # Should be 2
        2
    """
    if not events:
        return []
    return [events]


def time_window_grouping(
    events: List[Event],
    window_minutes: int = 15,
    min_events: int = 1
) -> List[IncidentGroup]:
    """Group events using time-window based clustering.

    Events are grouped if they occur within the specified time window.
    This is a temporal proximity-based approach where events close in
    time are considered part of the same incident.

    The algorithm:
    1. Separates events with/without timestamps
    2. Sorts timestamped events chronologically
    3. Creates groups where consecutive events are within the time window
    4. Filters groups by minimum event count
    5. Handles non-timestamped events separately

    Args:
        events: List of Event objects to group.
        window_minutes: Maximum time difference in minutes between consecutive
            events in the same group. Default is 15 minutes.
        min_events: Minimum number of events required to form a valid group.
            Default is 1 (all groups are valid).

    Returns:
        List of IncidentGroup objects, each containing temporally related events.

    Example:
        >>> from datetime import datetime
        >>> events = [
        ...     Event(service="api", timestamp=datetime(2024, 1, 1, 10, 0)),
        ...     Event(service="db", timestamp=datetime(2024, 1, 1, 10, 5)),
        ...     Event(service="cache", timestamp=datetime(2024, 1, 1, 12, 0))
        ... ]
        >>> groups = time_window_grouping(events, window_minutes=15)
        >>> len(groups)  # First two events grouped, third separate
        2
    """
    if not events:
        return []

    # Filter out events without timestamps
    events_with_time = [e for e in events if e.timestamp is not None]
    events_without_time = [e for e in events if e.timestamp is None]

    if events_without_time:
        logger.warning(
            f"{len(events_without_time)} events without timestamps will be grouped separately"
        )

    if not events_with_time:
        # If no events have timestamps, return single group
        if len(events) >= min_events:
            return [IncidentGroup.from_events(events)]
        return []

    # Sort events by timestamp
    sorted_events = sorted(events_with_time, key=lambda e: e.timestamp)

    groups: List[List[Event]] = []
    current_group: List[Event] = []
    window_delta = timedelta(minutes=window_minutes)

    for event in sorted_events:
        if not current_group:
            # Start new group
            current_group.append(event)
        else:
            # Check if event is within time window of the last event in group
            time_diff = event.timestamp - current_group[-1].timestamp

            if time_diff <= window_delta:
                # Add to current group
                current_group.append(event)
            else:
                # Start new group
                if len(current_group) >= min_events:
                    groups.append(current_group)
                current_group = [event]

    # Add final group
    if current_group and len(current_group) >= min_events:
        groups.append(current_group)

    # Add events without timestamps as a separate group if enough
    if events_without_time and len(events_without_time) >= min_events:
        groups.append(events_without_time)

    # Convert to IncidentGroup objects
    incident_groups = [IncidentGroup.from_events(g) for g in groups]

    logger.info(
        f"Grouped {len(events)} events into {len(incident_groups)} incidents "
        f"using {window_minutes}-minute time window"
    )

    return incident_groups


def service_based_grouping(
    events: List[Event],
    window_minutes: int = 15,
    min_events_per_service: int = 2
) -> List[IncidentGroup]:
    """Group events by service and time window.

    This strategy first partitions events by service, then applies time-window
    grouping within each service. This is useful when you want to detect
    service-specific incidents while still considering temporal patterns.

    The algorithm:
    1. Partitions events by service (or "unknown" if no service specified)
    2. For each service with enough events, applies time_window_grouping
    3. Combines all service-specific groups into final result

    Args:
        events: List of Event objects to group.
        window_minutes: Time window in minutes for grouping events within
            each service. Default is 15 minutes.
        min_events_per_service: Minimum number of events a service must have
            to be considered for grouping. Default is 2.

    Returns:
        List of IncidentGroup objects, each containing events from a single
        service within a time window.

    Example:
        >>> events = [
        ...     Event(service="api", timestamp=datetime(2024, 1, 1, 10, 0)),
        ...     Event(service="api", timestamp=datetime(2024, 1, 1, 10, 5)),
        ...     Event(service="db", timestamp=datetime(2024, 1, 1, 10, 3)),
        ...     Event(service="db", timestamp=datetime(2024, 1, 1, 10, 8)),
        ... ]
        >>> groups = service_based_grouping(events, min_events_per_service=2)
        >>> # Will create separate groups for 'api' and 'db' services
        >>> len(groups)
        2
    """
    if not events:
        return []

    # Group events by service first
    service_events: Dict[str, List[Event]] = {}
    for event in events:
        service = event.service or "unknown"
        if service not in service_events:
            service_events[service] = []
        service_events[service].append(event)

    # Apply time window grouping within each service
    all_groups: List[IncidentGroup] = []
    for service, service_event_list in service_events.items():
        if len(service_event_list) >= min_events_per_service:
            groups = time_window_grouping(
                service_event_list,
                window_minutes=window_minutes,
                min_events=min_events_per_service
            )
            all_groups.extend(groups)
        else:
            logger.debug(
                f"Service '{service}' has only {len(service_event_list)} events "
                f"(min: {min_events_per_service}), skipping"
            )

    logger.info(
        f"Grouped {len(events)} events into {len(all_groups)} incidents "
        f"by service and time window"
    )

    return all_groups
