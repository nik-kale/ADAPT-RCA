"""
Data models for ADAPT-RCA using Pydantic for validation.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
from functools import lru_cache

from pydantic import BaseModel, Field, field_validator
from dateutil import parser as date_parser


# LRU cache for timestamp parsing to improve performance
# Common timestamp formats are parsed once and cached
@lru_cache(maxsize=1024)
def _parse_timestamp_cached(timestamp_str: str) -> Optional[datetime]:
    """
    Parse timestamp string with LRU caching for performance.

    Many log files contain repeated timestamp formats. By caching
    the parsing results, we can significantly improve performance
    when processing large log files with consistent timestamp formats.

    Args:
        timestamp_str: ISO 8601 or other timestamp string format.

    Returns:
        Parsed datetime object or None if parsing fails.

    Note:
        Cache size is 1024 which covers most use cases. For logs with
        microsecond-precision timestamps, each unique timestamp is cached.
        For logs with second-precision, cache hit rate is very high.
    """
    try:
        return date_parser.parse(timestamp_str)
    except (ValueError, TypeError):
        return None


class LogLevel(str, Enum):
    """Standard log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"


class Event(BaseModel):
    """
    Normalized event/log entry.

    Attributes:
        timestamp: ISO 8601 timestamp or datetime object
        service: Service or component name
        level: Log level
        message: Log message
        raw: Original raw event data
        metadata: Additional extracted fields
    """
    timestamp: Optional[datetime] = None
    service: Optional[str] = None
    level: Optional[str] = None
    message: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('timestamp', mode='before')
    @classmethod
    def parse_timestamp(cls, v: Any) -> Optional[datetime]:
        """Parse timestamp from various formats with caching.

        Handles ISO 8601 strings, datetime objects, and returns None for
        invalid formats. Uses cached parsing for improved performance when
        processing large log files with repeated timestamp formats.

        Args:
            v: Timestamp value (string, datetime, or None).

        Returns:
            Parsed datetime object or None if parsing fails.

        Example:
            >>> Event(timestamp="2024-01-01T10:00:00Z")
            >>> Event(timestamp=datetime.now())
            >>> Event(timestamp=None)
        """
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            # Use cached parsing for performance
            return _parse_timestamp_cached(v)
        return None

    @field_validator('level')
    @classmethod
    def normalize_level(cls, v: Optional[str]) -> Optional[str]:
        """Normalize log level to uppercase.

        Ensures consistent log level representation by converting to uppercase.

        Args:
            v: Log level string (can be None).

        Returns:
            Uppercase log level string or None.

        Example:
            >>> Event(level="error").level
            'ERROR'
            >>> Event(level="Info").level
            'INFO'
        """
        if v is None:
            return None
        return v.upper()

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class IncidentGroup(BaseModel):
    """
    A group of related events forming a potential incident.

    Attributes:
        events: List of events in this group
        start_time: Earliest event timestamp
        end_time: Latest event timestamp
        services: Set of services involved
        severity: Highest severity level
    """
    events: List[Event] = Field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    services: List[str] = Field(default_factory=list)
    severity: Optional[str] = None

    @classmethod
    def from_events(cls, events: List[Event]) -> 'IncidentGroup':
        """Create incident group from list of events.

        Aggregates events into a group, calculating time range, affected services,
        and determining the highest severity level present.

        Args:
            events: List of Event objects to group together.

        Returns:
            IncidentGroup with aggregated information.

        Example:
            >>> events = [Event(...), Event(...)]
            >>> group = IncidentGroup.from_events(events)
            >>> print(f"Services: {group.services}")
            >>> print(f"Severity: {group.severity}")
        """
        if not events:
            return cls()

        timestamps = [e.timestamp for e in events if e.timestamp]
        services = list({e.service for e in events if e.service})

        # Determine highest severity
        severity_order = ['DEBUG', 'INFO', 'WARN', 'WARNING', 'ERROR', 'CRITICAL', 'FATAL']
        levels = [e.level for e in events if e.level]
        severity = None
        if levels:
            for level in reversed(severity_order):
                if level in levels:
                    severity = level
                    break

        return cls(
            events=events,
            start_time=min(timestamps) if timestamps else None,
            end_time=max(timestamps) if timestamps else None,
            services=services,
            severity=severity
        )


class RootCause(BaseModel):
    """
    A probable root cause hypothesis.

    Attributes:
        description: Description of the root cause
        confidence: Confidence score (0.0 to 1.0)
        evidence: List of supporting evidence
    """
    description: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    evidence: List[str] = Field(default_factory=list)


class RecommendedAction(BaseModel):
    """
    A recommended remediation action.

    Attributes:
        description: Description of the action
        priority: Priority level (1-5, 1 being highest)
        category: Category of action (e.g., 'investigate', 'fix', 'monitor')
    """
    description: str
    priority: int = Field(ge=1, le=5, default=3)
    category: str = "investigate"


class AnalysisResult(BaseModel):
    """
    Complete analysis result for an incident.

    Attributes:
        incident_summary: Human-readable summary
        probable_root_causes: List of root cause hypotheses
        recommended_actions: List of recommended actions
        affected_services: Services affected by this incident
        event_count: Number of events analyzed
        time_range: Time range of the incident
        causal_graph: Causal graph showing service dependencies
        metadata: Additional analysis metadata
    """
    incident_summary: str
    probable_root_causes: List[RootCause] = Field(default_factory=list)
    recommended_actions: List[RecommendedAction] = Field(default_factory=list)
    affected_services: List[str] = Field(default_factory=list)
    event_count: int = 0
    time_range: Optional[Dict[str, Optional[datetime]]] = None
    causal_graph: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

    def to_legacy_dict(self) -> Dict[str, Any]:
        """Convert to legacy dictionary format for backward compatibility.

        Extracts simple string representations from the structured RootCause
        and RecommendedAction objects for use with older code expecting
        simple string lists.

        Returns:
            Dictionary with legacy structure containing:
                - incident_summary (str)
                - probable_root_causes (List[str])
                - recommended_actions (List[str])

        Example:
            >>> result = AnalysisResult(
            ...     incident_summary="Database failure",
            ...     probable_root_causes=[RootCause(description="Timeout")],
            ...     recommended_actions=[RecommendedAction(description="Restart")]
            ... )
            >>> legacy = result.to_legacy_dict()
            >>> legacy["probable_root_causes"]
            ['Timeout']
        """
        return {
            "incident_summary": self.incident_summary,
            "probable_root_causes": [rc.description for rc in self.probable_root_causes],
            "recommended_actions": [ra.description for ra in self.recommended_actions],
        }
