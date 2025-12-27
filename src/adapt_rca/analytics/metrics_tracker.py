"""
Metrics tracking for ADAPT-RCA performance and incident history.

This module provides time-series metrics collection and analysis to support
anomaly detection and historical trend analysis.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


@dataclass
class Metric:
    """A single metric data point."""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class MetricsTracker:
    """
    Time-series metrics tracker with automatic retention and aggregation.

    Tracks metrics over time with automatic cleanup of old data. Supports
    aggregation for performance analysis and anomaly detection.

    Example:
        >>> tracker = MetricsTracker(retention_hours=24)
        >>> tracker.record("error_rate", 15.5, tags={"service": "api"})
        >>> metrics = tracker.get_recent("error_rate", hours=1)
        >>> avg = tracker.get_average("error_rate", hours=6)
    """

    def __init__(
        self,
        retention_hours: int = 168,  # 7 days default
        max_points_per_metric: int = 10000
    ):
        """
        Initialize metrics tracker.

        Args:
            retention_hours: How long to keep metrics (default 7 days)
            max_points_per_metric: Maximum data points per metric to prevent memory issues
        """
        self.retention_hours = retention_hours
        self.max_points_per_metric = max_points_per_metric
        self._metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_points_per_metric))
        self._last_cleanup = datetime.now()

    def record(
        self,
        name: str,
        value: float,
        timestamp: Optional[datetime] = None,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a metric value.

        Args:
            name: Metric name (e.g., "error_rate", "response_time")
            value: Metric value
            timestamp: Timestamp (defaults to now)
            tags: Optional tags for filtering {"service": "api", "region": "us-west"}
            metadata: Optional metadata
        """
        if timestamp is None:
            timestamp = datetime.now()

        metric = Metric(
            name=name,
            value=value,
            timestamp=timestamp,
            tags=tags or {},
            metadata=metadata or {}
        )

        self._metrics[name].append(metric)

        # Periodic cleanup to prevent memory issues
        if (datetime.now() - self._last_cleanup).seconds > 3600:  # Every hour
            self._cleanup_old_metrics()

    def get_recent(
        self,
        name: str,
        hours: Optional[float] = None,
        minutes: Optional[int] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> List[Metric]:
        """
        Get recent metrics for a given name.

        Args:
            name: Metric name
            hours: How many hours of data to retrieve
            minutes: How many minutes of data to retrieve
            tags: Optional tag filters

        Returns:
            List of matching metrics, sorted by timestamp
        """
        if name not in self._metrics:
            return []

        # Calculate cutoff time
        if hours is not None:
            cutoff = datetime.now() - timedelta(hours=hours)
        elif minutes is not None:
            cutoff = datetime.now() - timedelta(minutes=minutes)
        else:
            cutoff = datetime.now() - timedelta(hours=self.retention_hours)

        # Filter metrics
        metrics = [
            m for m in self._metrics[name]
            if m.timestamp >= cutoff
        ]

        # Apply tag filters if provided
        if tags:
            metrics = [
                m for m in metrics
                if all(m.tags.get(k) == v for k, v in tags.items())
            ]

        return sorted(metrics, key=lambda m: m.timestamp)

    def get_values(
        self,
        name: str,
        hours: Optional[float] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> List[float]:
        """
        Get recent metric values (without timestamp/metadata).

        Args:
            name: Metric name
            hours: How many hours of data
            tags: Optional tag filters

        Returns:
            List of metric values
        """
        metrics = self.get_recent(name, hours=hours, tags=tags)
        return [m.value for m in metrics]

    def get_average(
        self,
        name: str,
        hours: Optional[float] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> Optional[float]:
        """
        Calculate average of recent metrics.

        Args:
            name: Metric name
            hours: How many hours to average
            tags: Optional tag filters

        Returns:
            Average value or None if no data
        """
        values = self.get_values(name, hours=hours, tags=tags)
        if not values:
            return None

        return sum(values) / len(values)

    def get_percentile(
        self,
        name: str,
        percentile: float,
        hours: Optional[float] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> Optional[float]:
        """
        Calculate percentile of recent metrics.

        Args:
            name: Metric name
            percentile: Percentile to calculate (0-100)
            hours: How many hours of data
            tags: Optional tag filters

        Returns:
            Percentile value or None if no data
        """
        values = self.get_values(name, hours=hours, tags=tags)
        if not values:
            return None

        sorted_values = sorted(values)
        index = int(len(sorted_values) * (percentile / 100.0))
        index = min(index, len(sorted_values) - 1)

        return sorted_values[index]

    def get_count(
        self,
        name: str,
        hours: Optional[float] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> int:
        """
        Count recent metrics.

        Args:
            name: Metric name
            hours: How many hours to count
            tags: Optional tag filters

        Returns:
            Number of matching metrics
        """
        return len(self.get_recent(name, hours=hours, tags=tags))

    def get_rate(
        self,
        name: str,
        hours: float = 1.0,
        tags: Optional[Dict[str, str]] = None
    ) -> float:
        """
        Calculate rate (count per hour) for a metric.

        Args:
            name: Metric name
            hours: Time window
            tags: Optional tag filters

        Returns:
            Rate (count per hour)
        """
        count = self.get_count(name, hours=hours, tags=tags)
        return count / hours if hours > 0 else 0.0

    def get_all_tags(self, name: str) -> Dict[str, set]:
        """
        Get all unique tag values for a metric.

        Args:
            name: Metric name

        Returns:
            Dictionary of tag names to sets of unique values
        """
        if name not in self._metrics:
            return {}

        all_tags = defaultdict(set)
        for metric in self._metrics[name]:
            for tag_name, tag_value in metric.tags.items():
                all_tags[tag_name].add(tag_value)

        return dict(all_tags)

    def clear(self, name: Optional[str] = None) -> None:
        """
        Clear metrics.

        Args:
            name: Optional metric name. If None, clears all metrics.
        """
        if name:
            if name in self._metrics:
                self._metrics[name].clear()
        else:
            self._metrics.clear()

    def _cleanup_old_metrics(self) -> None:
        """Remove metrics older than retention period."""
        cutoff = datetime.now() - timedelta(hours=self.retention_hours)
        cleaned_count = 0

        for name, metrics_deque in self._metrics.items():
            # Count how many to remove from the left
            remove_count = 0
            for metric in metrics_deque:
                if metric.timestamp < cutoff:
                    remove_count += 1
                else:
                    break

            # Remove old metrics from the left
            for _ in range(remove_count):
                metrics_deque.popleft()
                cleaned_count += 1

        self._last_cleanup = datetime.now()

        if cleaned_count > 0:
            logger.debug(f"Cleaned up {cleaned_count} old metrics")

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of all tracked metrics.

        Returns:
            Dictionary with metric names and their counts
        """
        summary = {}
        for name, metrics_deque in self._metrics.items():
            summary[name] = {
                "count": len(metrics_deque),
                "tags": list(self.get_all_tags(name).keys())
            }

        return summary
