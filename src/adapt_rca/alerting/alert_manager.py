"""
Alert management system for ADAPT-RCA.

Manages alert lifecycle, deduplication, and routing to appropriate notifiers.
Based on best practices from PagerDuty, Datadog, and industry standards.
"""
import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Dict, Optional, Any, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels following industry standards."""
    CRITICAL = "critical"  # Requires immediate action
    HIGH = "high"  # Requires urgent attention
    MEDIUM = "medium"  # Should be addressed soon
    LOW = "low"  # Informational
    INFO = "info"  # Just for awareness


class AlertStatus(str, Enum):
    """Alert lifecycle status."""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"  # Muted due to correlation/deduplication


@dataclass
class Alert:
    """
    Represents an alert/notification.

    Attributes:
        title: Short alert title
        message: Detailed message
        severity: Alert severity level
        source: Source of the alert (service, component, etc.)
        status: Current alert status
        created_at: When alert was created
        tags: Optional tags for filtering/routing
        metadata: Additional context
    """
    title: str
    message: str
    severity: AlertSeverity
    source: str
    status: AlertStatus = AlertStatus.OPEN
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    alert_id: Optional[str] = None
    fingerprint: Optional[str] = None
    count: int = 1  # For deduplicated alerts

    def __post_init__(self):
        """Generate alert ID and fingerprint."""
        if self.alert_id is None:
            # Generate unique ID based on timestamp and source
            self.alert_id = hashlib.md5(
                f"{self.created_at.isoformat()}-{self.source}-{self.title}".encode()
            ).hexdigest()[:12]

        if self.fingerprint is None:
            # Generate fingerprint for deduplication (excludes timestamp)
            fingerprint_str = f"{self.title}:{self.source}:{self.severity.value}"
            self.fingerprint = hashlib.md5(fingerprint_str.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "status": self.status.value,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags,
            "metadata": self.metadata,
            "count": self.count,
            "fingerprint": self.fingerprint
        }


class AlertManager:
    """
    Manages alerts with deduplication, correlation, and routing.

    Features:
    - Alert deduplication (merge identical alerts)
    - Rate limiting (prevent alert storms)
    - Multi-channel notification routing
    - Alert history tracking

    Example:
        >>> from adapt_rca.alerting import AlertManager, Alert, AlertSeverity
        >>> manager = AlertManager()
        >>> manager.add_notifier("console", ConsoleNotifier())
        >>>
        >>> alert = Alert(
        ...     title="High Error Rate Detected",
        ...     message="API service error rate: 150 errors/min",
        ...     severity=AlertSeverity.CRITICAL,
        ...     source="api-service"
        ... )
        >>> manager.send_alert(alert)
    """

    def __init__(
        self,
        deduplication_window_minutes: int = 60,
        rate_limit_per_hour: int = 100,
        max_history_size: int = 1000
    ):
        """
        Initialize alert manager.

        Args:
            deduplication_window_minutes: Window for deduplicating identical alerts
            rate_limit_per_hour: Maximum alerts per hour to prevent storms
            max_history_size: Maximum alerts to keep in history
        """
        self.deduplication_window = timedelta(minutes=deduplication_window_minutes)
        self.rate_limit = rate_limit_per_hour
        self.max_history_size = max_history_size

        self._notifiers: Dict[str, Any] = {}
        self._active_alerts: Dict[str, Alert] = {}  # fingerprint -> Alert
        self._alert_history: List[Alert] = []
        self._alert_counts: Dict[str, List[datetime]] = defaultdict(list)

    def add_notifier(self, name: str, notifier: Any) -> None:
        """
        Register a notifier for sending alerts.

        Args:
            name: Notifier identifier (e.g., "slack", "email")
            notifier: Notifier instance implementing notify() method
        """
        self._notifiers[name] = notifier
        logger.info(f"Added notifier: {name}")

    def send_alert(
        self,
        alert: Alert,
        notifiers: Optional[List[str]] = None
    ) -> bool:
        """
        Send an alert through configured notifiers.

        Applies deduplication and rate limiting before sending.

        Args:
            alert: Alert to send
            notifiers: Optional list of notifier names to use. If None, uses all.

        Returns:
            True if alert was sent, False if suppressed
        """
        # Check rate limit
        if not self._check_rate_limit():
            logger.warning("Alert rate limit exceeded, suppressing alert")
            alert.status = AlertStatus.SUPPRESSED
            self._add_to_history(alert)
            return False

        # Check for deduplication
        if alert.fingerprint in self._active_alerts:
            # Update existing alert
            existing = self._active_alerts[alert.fingerprint]
            if (alert.created_at - existing.updated_at) < self.deduplication_window:
                # Within deduplication window, merge
                existing.count += 1
                existing.updated_at = alert.created_at
                logger.debug(
                    f"Deduplicated alert {alert.fingerprint}, count: {existing.count}"
                )
                return False

        # Add to active alerts
        self._active_alerts[alert.fingerprint] = alert

        # Send through notifiers
        target_notifiers = notifiers or list(self._notifiers.keys())
        success = False

        for notifier_name in target_notifiers:
            if notifier_name in self._notifiers:
                try:
                    self._notifiers[notifier_name].notify(alert)
                    success = True
                except Exception as e:
                    logger.error(f"Failed to send alert via {notifier_name}: {e}")

        # Add to history
        self._add_to_history(alert)

        # Record for rate limiting
        self._alert_counts[alert.source].append(alert.created_at)

        return success

    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Mark an alert as acknowledged.

        Args:
            alert_id: Alert ID to acknowledge

        Returns:
            True if alert was found and updated
        """
        for alert in self._active_alerts.values():
            if alert.alert_id == alert_id:
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.updated_at = datetime.now()
                logger.info(f"Alert {alert_id} acknowledged")
                return True

        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """
        Mark an alert as resolved.

        Args:
            alert_id: Alert ID to resolve

        Returns:
            True if alert was found and updated
        """
        for fingerprint, alert in list(self._active_alerts.items()):
            if alert.alert_id == alert_id:
                alert.status = AlertStatus.RESOLVED
                alert.updated_at = datetime.now()
                # Remove from active alerts
                del self._active_alerts[fingerprint]
                logger.info(f"Alert {alert_id} resolved")
                return True

        return False

    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        source: Optional[str] = None
    ) -> List[Alert]:
        """
        Get currently active alerts.

        Args:
            severity: Optional filter by severity
            source: Optional filter by source

        Returns:
            List of active alerts
        """
        alerts = list(self._active_alerts.values())

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if source:
            alerts = [a for a in alerts if a.source == source]

        return sorted(alerts, key=lambda a: a.created_at, reverse=True)

    def get_alert_history(
        self,
        hours: int = 24,
        severity: Optional[AlertSeverity] = None
    ) -> List[Alert]:
        """
        Get alert history.

        Args:
            hours: How many hours of history
            severity: Optional filter by severity

        Returns:
            List of historical alerts
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        alerts = [a for a in self._alert_history if a.created_at >= cutoff]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return sorted(alerts, key=lambda a: a.created_at, reverse=True)

    def get_alert_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get alert statistics.

        Args:
            hours: Time window for stats

        Returns:
            Dictionary with alert statistics
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_alerts = [a for a in self._alert_history if a.created_at >= cutoff]

        severity_counts = defaultdict(int)
        source_counts = defaultdict(int)

        for alert in recent_alerts:
            severity_counts[alert.severity.value] += 1
            source_counts[alert.source] += 1

        return {
            "total_alerts": len(recent_alerts),
            "active_alerts": len(self._active_alerts),
            "by_severity": dict(severity_counts),
            "by_source": dict(source_counts),
            "time_window_hours": hours
        }

    def _check_rate_limit(self) -> bool:
        """
        Check if we're within rate limits.

        Returns:
            True if within limits, False if exceeded
        """
        cutoff = datetime.now() - timedelta(hours=1)

        # Clean old timestamps
        for source in list(self._alert_counts.keys()):
            self._alert_counts[source] = [
                ts for ts in self._alert_counts[source]
                if ts >= cutoff
            ]

        # Count recent alerts across all sources
        total_recent = sum(len(timestamps) for timestamps in self._alert_counts.values())

        return total_recent < self.rate_limit

    def _add_to_history(self, alert: Alert) -> None:
        """Add alert to history with size limit."""
        self._alert_history.append(alert)

        # Trim history if too large
        if len(self._alert_history) > self.max_history_size:
            # Remove oldest 10%
            remove_count = self.max_history_size // 10
            self._alert_history = self._alert_history[remove_count:]

    def cleanup_old_alerts(self, hours: int = 24) -> int:
        """
        Remove resolved alerts older than specified hours.

        Args:
            hours: Age threshold

        Returns:
            Number of alerts cleaned up
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        initial_count = len(self._active_alerts)

        # Remove old resolved alerts
        self._active_alerts = {
            fp: alert for fp, alert in self._active_alerts.items()
            if not (alert.status == AlertStatus.RESOLVED and alert.updated_at < cutoff)
        }

        cleaned = initial_count - len(self._active_alerts)
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old alerts")

        return cleaned
