"""
OpenTelemetry tracing support for ADAPT-RCA.

Enables ingestion and analysis of distributed tracing data from OpenTelemetry exporters.
Helps identify latency issues and trace error propagation across services.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class Span:
    """Represents an OpenTelemetry span."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    kind: str  # CLIENT, SERVER, INTERNAL, PRODUCER, CONSUMER
    start_time: datetime
    end_time: datetime
    service_name: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status_code: str = "OK"  # OK, ERROR, UNSET
    status_message: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        """Calculate span duration in milliseconds."""
        return (self.end_time - self.start_time).total_seconds() * 1000

    @property
    def is_error(self) -> bool:
        """Check if span represents an error."""
        return self.status_code == "ERROR"


@dataclass
class Trace:
    """Represents a complete distributed trace."""
    trace_id: str
    spans: List[Span]
    root_span: Optional[Span] = None
    services: Set[str] = field(default_factory=set)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    has_errors: bool = False

    def __post_init__(self):
        """Initialize computed fields."""
        if self.spans:
            # Find root span
            for span in self.spans:
                if span.parent_span_id is None:
                    self.root_span = span
                    break

            # Collect services
            self.services = {s.service_name for s in self.spans}

            # Calculate time range
            self.start_time = min(s.start_time for s in self.spans)
            self.end_time = max(s.end_time for s in self.spans)

            # Check for errors
            self.has_errors = any(s.is_error for s in self.spans)

    @property
    def total_duration_ms(self) -> float:
        """Total trace duration in milliseconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return 0.0

    def get_critical_path(self) -> List[Span]:
        """
        Get critical path (longest chain of spans).

        Returns:
            List of spans forming the critical path
        """
        if not self.root_span:
            return []

        # Build parent-child relationships
        children = defaultdict(list)
        for span in self.spans:
            if span.parent_span_id:
                children[span.parent_span_id].append(span)

        # DFS to find longest path
        def find_longest_path(span: Span) -> List[Span]:
            if span.span_id not in children:
                return [span]

            longest = []
            for child in children[span.span_id]:
                path = find_longest_path(child)
                if sum(s.duration_ms for s in path) > sum(s.duration_ms for s in longest):
                    longest = path

            return [span] + longest

        return find_longest_path(self.root_span)


class OpenTelemetryAnalyzer:
    """
    Analyzes OpenTelemetry traces for performance and error patterns.

    Example:
        >>> analyzer = OpenTelemetryAnalyzer()
        >>> trace = analyzer.parse_trace(trace_data)
        >>> issues = analyzer.analyze_trace(trace)
        >>> for issue in issues:
        ...     print(f"{issue['type']}: {issue['description']}")
    """

    def __init__(
        self,
        slow_span_threshold_ms: float = 1000.0,
        error_propagation_window_ms: float = 100.0
    ):
        """
        Initialize OpenTelemetry analyzer.

        Args:
            slow_span_threshold_ms: Threshold for identifying slow spans
            error_propagation_window_ms: Time window for error propagation detection
        """
        self.slow_span_threshold = slow_span_threshold_ms
        self.error_window = error_propagation_window_ms

    def parse_trace(self, trace_data: Dict[str, Any]) -> Trace:
        """
        Parse OpenTelemetry trace data.

        Args:
            trace_data: Trace data in OTLP format

        Returns:
            Trace object
        """
        trace_id = trace_data.get('traceId', '')
        spans = []

        for span_data in trace_data.get('spans', []):
            span = Span(
                trace_id=span_data.get('traceId', trace_id),
                span_id=span_data.get('spanId', ''),
                parent_span_id=span_data.get('parentSpanId'),
                name=span_data.get('name', ''),
                kind=span_data.get('kind', 'INTERNAL'),
                start_time=self._parse_timestamp(span_data.get('startTimeUnixNano', 0)),
                end_time=self._parse_timestamp(span_data.get('endTimeUnixNano', 0)),
                service_name=span_data.get('resource', {}).get('attributes', {}).get('service.name', 'unknown'),
                attributes=span_data.get('attributes', {}),
                events=span_data.get('events', []),
                status_code=span_data.get('status', {}).get('code', 'UNSET'),
                status_message=span_data.get('status', {}).get('message')
            )
            spans.append(span)

        return Trace(trace_id=trace_id, spans=spans)

    def analyze_trace(self, trace: Trace) -> List[Dict[str, Any]]:
        """
        Analyze trace for performance and error issues.

        Args:
            trace: Trace to analyze

        Returns:
            List of identified issues
        """
        issues = []

        # Check for errors
        if trace.has_errors:
            error_spans = [s for s in trace.spans if s.is_error]
            issues.append({
                'type': 'trace_error',
                'severity': 'high',
                'description': f"Trace contains {len(error_spans)} error span(s)",
                'affected_services': list({s.service_name for s in error_spans}),
                'error_spans': [s.span_id for s in error_spans]
            })

            # Check for error propagation
            propagation = self._detect_error_propagation(trace)
            if propagation:
                issues.append({
                    'type': 'error_propagation',
                    'severity': 'high',
                    'description': 'Error propagated across services',
                    'propagation_chain': propagation
                })

        # Check for slow spans
        slow_spans = [s for s in trace.spans if s.duration_ms > self.slow_span_threshold]
        if slow_spans:
            issues.append({
                'type': 'slow_spans',
                'severity': 'medium',
                'description': f"Found {len(slow_spans)} slow span(s) (>{self.slow_span_threshold}ms)",
                'slow_spans': [
                    {
                        'span_id': s.span_id,
                        'name': s.name,
                        'service': s.service_name,
                        'duration_ms': s.duration_ms
                    }
                    for s in sorted(slow_spans, key=lambda x: x.duration_ms, reverse=True)[:5]
                ]
            })

        # Analyze critical path
        critical_path = trace.get_critical_path()
        if critical_path:
            critical_duration = sum(s.duration_ms for s in critical_path)
            if critical_duration > self.slow_span_threshold:
                issues.append({
                    'type': 'slow_critical_path',
                    'severity': 'medium',
                    'description': f"Critical path duration: {critical_duration:.1f}ms",
                    'path': [
                        {
                            'service': s.service_name,
                            'operation': s.name,
                            'duration_ms': s.duration_ms
                        }
                        for s in critical_path
                    ]
                })

        # Check for service dependencies
        dependencies = self._analyze_dependencies(trace)
        if dependencies:
            issues.append({
                'type': 'service_dependencies',
                'severity': 'info',
                'description': f"Trace involves {len(trace.services)} service(s)",
                'dependencies': dependencies
            })

        return issues

    def _detect_error_propagation(self, trace: Trace) -> Optional[List[Dict[str, str]]]:
        """
        Detect if errors propagated across services.

        Args:
            trace: Trace to analyze

        Returns:
            List of propagation steps or None
        """
        error_spans = sorted(
            [s for s in trace.spans if s.is_error],
            key=lambda s: s.start_time
        )

        if len(error_spans) < 2:
            return None

        # Check if errors occurred in sequence
        propagation = []
        for i in range(len(error_spans) - 1):
            current = error_spans[i]
            next_span = error_spans[i + 1]

            time_diff = (next_span.start_time - current.end_time).total_seconds() * 1000

            if 0 <= time_diff <= self.error_window:
                propagation.append({
                    'from_service': current.service_name,
                    'to_service': next_span.service_name,
                    'time_diff_ms': time_diff
                })

        return propagation if propagation else None

    def _analyze_dependencies(self, trace: Trace) -> List[Dict[str, Any]]:
        """
        Analyze service dependencies in trace.

        Args:
            trace: Trace to analyze

        Returns:
            List of dependency relationships
        """
        dependencies = []
        service_spans = defaultdict(list)

        for span in trace.spans:
            service_spans[span.service_name].append(span)

        # Find parent-child service relationships
        seen_deps = set()

        for span in trace.spans:
            if span.parent_span_id:
                # Find parent span
                parent = next((s for s in trace.spans if s.span_id == span.parent_span_id), None)
                if parent and parent.service_name != span.service_name:
                    dep_key = (parent.service_name, span.service_name)
                    if dep_key not in seen_deps:
                        seen_deps.add(dep_key)
                        dependencies.append({
                            'caller': parent.service_name,
                            'callee': span.service_name,
                            'call_count': 1  # Could aggregate if needed
                        })

        return dependencies

    def _parse_timestamp(self, nanos: int) -> datetime:
        """Convert nanoseconds since epoch to datetime."""
        return datetime.fromtimestamp(nanos / 1e9)

    def aggregate_traces(
        self,
        traces: List[Trace],
        group_by: str = "service"
    ) -> Dict[str, Any]:
        """
        Aggregate statistics from multiple traces.

        Args:
            traces: List of traces to aggregate
            group_by: Grouping criteria ("service" or "operation")

        Returns:
            Dictionary with aggregated statistics
        """
        stats = defaultdict(lambda: {
            'count': 0,
            'error_count': 0,
            'total_duration_ms': 0.0,
            'min_duration_ms': float('inf'),
            'max_duration_ms': 0.0
        })

        for trace in traces:
            for span in trace.spans:
                if group_by == "service":
                    key = span.service_name
                else:  # operation
                    key = f"{span.service_name}:{span.name}"

                s = stats[key]
                s['count'] += 1
                if span.is_error:
                    s['error_count'] += 1

                s['total_duration_ms'] += span.duration_ms
                s['min_duration_ms'] = min(s['min_duration_ms'], span.duration_ms)
                s['max_duration_ms'] = max(s['max_duration_ms'], span.duration_ms)

        # Calculate averages
        result = {}
        for key, s in stats.items():
            result[key] = {
                'count': s['count'],
                'error_count': s['error_count'],
                'error_rate': s['error_count'] / s['count'] if s['count'] > 0 else 0,
                'avg_duration_ms': s['total_duration_ms'] / s['count'] if s['count'] > 0 else 0,
                'min_duration_ms': s['min_duration_ms'] if s['min_duration_ms'] != float('inf') else 0,
                'max_duration_ms': s['max_duration_ms']
            }

        return result
