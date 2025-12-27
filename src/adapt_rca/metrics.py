"""
Prometheus metrics for ADAPT-RCA observability.

This module provides metrics collection for monitoring system health,
performance, and resource usage. Metrics are exposed in Prometheus format.
"""

from typing import Dict, Optional
from datetime import datetime
import threading


class MetricsCollector:
    """
    Singleton metrics collector for ADAPT-RCA.

    Collects and exposes metrics in Prometheus-compatible format.
    In production, this would integrate with prometheus_client library.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize metrics storage."""
        self._gauges: Dict[str, Dict[str, float]] = {}
        self._counters: Dict[str, Dict[str, int]] = {}
        self._histograms: Dict[str, Dict[str, list]] = {}

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Set a gauge metric value.

        Args:
            name: Metric name
            value: Metric value
            labels: Label dictionary (e.g., {'connector': 'prometheus', 'host': 'localhost'})
        """
        labels = labels or {}
        label_key = self._make_label_key(labels)

        if name not in self._gauges:
            self._gauges[name] = {}

        self._gauges[name][label_key] = value

    def increment_counter(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None):
        """
        Increment a counter metric.

        Args:
            name: Metric name
            value: Increment amount (default 1)
            labels: Label dictionary
        """
        labels = labels or {}
        label_key = self._make_label_key(labels)

        if name not in self._counters:
            self._counters[name] = {}

        self._counters[name][label_key] = self._counters[name].get(label_key, 0) + value

    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Record a histogram observation.

        Args:
            name: Metric name
            value: Observed value
            labels: Label dictionary
        """
        labels = labels or {}
        label_key = self._make_label_key(labels)

        if name not in self._histograms:
            self._histograms[name] = {}

        if label_key not in self._histograms[name]:
            self._histograms[name][label_key] = []

        self._histograms[name][label_key].append(value)

    def get_metrics(self) -> str:
        """
        Get all metrics in Prometheus text format.

        Returns:
            Prometheus-formatted metrics string
        """
        lines = []

        # Gauges
        for name, labels_dict in self._gauges.items():
            lines.append(f"# TYPE {name} gauge")
            for label_key, value in labels_dict.items():
                lines.append(f"{name}{{{label_key}}} {value}")

        # Counters
        for name, labels_dict in self._counters.items():
            lines.append(f"# TYPE {name} counter")
            for label_key, value in labels_dict.items():
                lines.append(f"{name}{{{label_key}}} {value}")

        # Histograms (simplified - just count and sum)
        for name, labels_dict in self._histograms.items():
            lines.append(f"# TYPE {name} histogram")
            for label_key, values in labels_dict.items():
                count = len(values)
                total = sum(values)
                lines.append(f"{name}_count{{{label_key}}} {count}")
                lines.append(f"{name}_sum{{{label_key}}} {total}")

        return "\n".join(lines)

    def _make_label_key(self, labels: Dict[str, str]) -> str:
        """Convert label dict to string key."""
        if not labels:
            return ""
        return ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))


# Singleton instance
metrics = MetricsCollector()


# Convenience functions for common metrics
def track_pool_active_connections(connector: str, host: str, count: int):
    """Track active connections in connection pool."""
    metrics.set_gauge(
        "adapt_connector_pool_active",
        count,
        {"connector": connector, "host": host}
    )


def track_pool_available_connections(connector: str, host: str, count: int):
    """Track available connections in connection pool."""
    metrics.set_gauge(
        "adapt_connector_pool_available",
        count,
        {"connector": connector, "host": host}
    )


def track_pool_wait_time(connector: str, host: str, seconds: float):
    """Track connection pool wait time."""
    metrics.record_histogram(
        "adapt_connector_pool_wait_seconds",
        seconds,
        {"connector": connector, "host": host}
    )


def track_pool_exhaustion(connector: str, host: str):
    """Increment pool exhaustion counter."""
    metrics.increment_counter(
        "adapt_connector_pool_exhaustion_total",
        1,
        {"connector": connector, "host": host}
    )


def track_rca_duration(duration_seconds: float, status: str = "success"):
    """Track RCA analysis duration."""
    metrics.record_histogram(
        "adapt_rca_duration_seconds",
        duration_seconds,
        {"status": status}
    )


def track_rca_total(status: str = "success"):
    """Increment total RCA counter."""
    metrics.increment_counter(
        "adapt_rca_total",
        1,
        {"status": status}
    )


def get_metrics_text() -> str:
    """
    Get all metrics in Prometheus text format.

    This can be exposed via an HTTP endpoint (e.g., /metrics).

    Returns:
        Prometheus-formatted metrics
    """
    return metrics.get_metrics()

