from typing import List, Dict, Any
from datetime import timedelta
import logging

from ..models import Event, IncidentGroup

logger = logging.getLogger(__name__)


def simple_grouping(events: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    Very basic grouping: put all events into a single incident candidate.

    Args:
        events: List of event dictionaries

    Returns:
        List of event groups (list of lists)
    """
    if not events:
        return []
    return [events]


def time_window_grouping(
    events: List[Event],
    window_minutes: int = 15,
    min_events: int = 1
) -> List[IncidentGroup]:
    """
    Group events using time-window based clustering.

    Events are grouped if they occur within the specified time window
    and involve related services.

    Args:
        events: List of Event objects
        window_minutes: Time window in minutes for grouping
        min_events: Minimum number of events to form a group

    Returns:
        List of IncidentGroup objects
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
    """
    Group events by service and time window.

    Args:
        events: List of Event objects
        window_minutes: Time window in minutes
        min_events_per_service: Minimum events per service to form a group

    Returns:
        List of IncidentGroup objects
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
