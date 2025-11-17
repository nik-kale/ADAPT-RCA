"""
Alert correlation engine for reducing noise and identifying related alerts.

Implements correlation rules and grouping to reduce alert fatigue by
identifying related alerts that likely stem from the same root cause.
"""
import logging
from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class CorrelationRule:
    """
    Rule for correlating related alerts.

    Attributes:
        name: Rule identifier
        time_window_minutes: Time window for correlation
        group_by_tags: List of tag keys to group by
        group_by_source: Whether to group by source
        min_alerts: Minimum alerts to trigger correlation
    """
    name: str
    time_window_minutes: int = 5
    group_by_tags: List[str] = None
    group_by_source: bool = True
    min_alerts: int = 2

    def __post_init__(self):
        if self.group_by_tags is None:
            self.group_by_tags = []


class AlertCorrelator:
    """
    Correlates related alerts to reduce noise.

    Uses time-based and tag-based grouping to identify alerts that are likely
    related to the same underlying issue. Implements best practices from
    Datadog, PagerDuty, and Google SRE principles.

    Example:
        >>> correlator = AlertCorrelator()
        >>> correlator.add_rule(CorrelationRule(
        ...     name="service_correlation",
        ...     group_by_tags=["service", "region"],
        ...     time_window_minutes=10
        ... ))
        >>> groups = correlator.correlate_alerts(alerts)
    """

    def __init__(self):
        """Initialize alert correlator."""
        self._rules: List[CorrelationRule] = []
        self._correlated_groups: Dict[str, List[Any]] = {}

    def add_rule(self, rule: CorrelationRule) -> None:
        """
        Add a correlation rule.

        Args:
            rule: Correlation rule to add
        """
        self._rules.append(rule)
        logger.info(f"Added correlation rule: {rule.name}")

    def correlate_alerts(
        self,
        alerts: List[Any],
        rule_name: Optional[str] = None
    ) -> Dict[str, List[Any]]:
        """
        Correlate alerts into groups.

        Args:
            alerts: List of alerts to correlate
            rule_name: Optional specific rule to use (uses all if None)

        Returns:
            Dictionary mapping group keys to lists of correlated alerts
        """
        if not alerts:
            return {}

        # Filter rules
        rules = self._rules if rule_name is None else [
            r for r in self._rules if r.name == rule_name
        ]

        if not rules:
            logger.warning("No correlation rules configured")
            return {}

        # Apply each rule
        all_groups = {}
        for rule in rules:
            groups = self._apply_rule(alerts, rule)
            # Merge with existing groups
            for key, group_alerts in groups.items():
                if key in all_groups:
                    # Merge and deduplicate
                    existing_ids = {a.alert_id for a in all_groups[key]}
                    for alert in group_alerts:
                        if alert.alert_id not in existing_ids:
                            all_groups[key].append(alert)
                else:
                    all_groups[key] = group_alerts

        # Filter groups that don't meet minimum
        filtered_groups = {}
        for key, group_alerts in all_groups.items():
            if len(group_alerts) >= min(r.min_alerts for r in rules):
                filtered_groups[key] = group_alerts
                logger.debug(f"Correlated group '{key}': {len(group_alerts)} alerts")

        return filtered_groups

    def _apply_rule(
        self,
        alerts: List[Any],
        rule: CorrelationRule
    ) -> Dict[str, List[Any]]:
        """
        Apply a single correlation rule.

        Args:
            alerts: List of alerts
            rule: Rule to apply

        Returns:
            Dictionary of grouped alerts
        """
        groups = defaultdict(list)
        time_window = timedelta(minutes=rule.time_window_minutes)

        # Sort alerts by time
        sorted_alerts = sorted(alerts, key=lambda a: a.created_at)

        for alert in sorted_alerts:
            # Generate group key based on rule
            group_key = self._generate_group_key(alert, rule)

            # Check if alert fits within time window of group
            if group_key in groups:
                # Check time window against most recent alert in group
                most_recent = max(groups[group_key], key=lambda a: a.created_at)
                if (alert.created_at - most_recent.created_at) <= time_window:
                    groups[group_key].append(alert)
                else:
                    # Start new group with timestamp suffix
                    new_key = f"{group_key}:{alert.created_at.isoformat()}"
                    groups[new_key].append(alert)
            else:
                groups[group_key].append(alert)

        return dict(groups)

    def _generate_group_key(self, alert: Any, rule: CorrelationRule) -> str:
        """
        Generate grouping key for an alert based on rule.

        Args:
            alert: Alert to generate key for
            rule: Rule defining grouping criteria

        Returns:
            Group key string
        """
        key_parts = []

        # Add source if rule specifies
        if rule.group_by_source:
            key_parts.append(f"source:{alert.source}")

        # Add specified tags
        for tag_key in rule.group_by_tags:
            tag_value = alert.tags.get(tag_key, "unknown")
            key_parts.append(f"{tag_key}:{tag_value}")

        # Add severity (always group by severity for simplicity)
        key_parts.append(f"severity:{alert.severity.value}")

        return "|".join(key_parts) if key_parts else "default"

    def get_correlated_summary(
        self,
        groups: Dict[str, List[Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate summary of correlated alert groups.

        Args:
            groups: Dictionary of correlated groups

        Returns:
            List of summary dictionaries
        """
        summaries = []

        for group_key, alerts in groups.items():
            if not alerts:
                continue

            # Find dominant properties
            sources = defaultdict(int)
            severities = defaultdict(int)
            earliest = min(a.created_at for a in alerts)
            latest = max(a.created_at for a in alerts)

            for alert in alerts:
                sources[alert.source] += 1
                severities[alert.severity.value] += 1

            dominant_source = max(sources.items(), key=lambda x: x[1])[0]
            dominant_severity = max(severities.items(), key=lambda x: x[1])[0]

            summaries.append({
                "group_key": group_key,
                "alert_count": len(alerts),
                "dominant_source": dominant_source,
                "dominant_severity": dominant_severity,
                "earliest_alert": earliest.isoformat(),
                "latest_alert": latest.isoformat(),
                "duration_minutes": (latest - earliest).seconds / 60,
                "sources": dict(sources),
                "severities": dict(severities)
            })

        return sorted(summaries, key=lambda s: s["alert_count"], reverse=True)

    def suppress_correlated_alerts(
        self,
        groups: Dict[str, List[Any]],
        keep_first: bool = True
    ) -> Set[str]:
        """
        Mark correlated alerts for suppression.

        Args:
            groups: Dictionary of correlated groups
            keep_first: If True, keep first alert in each group

        Returns:
            Set of alert IDs to suppress
        """
        suppress_ids = set()

        for alerts in groups.values():
            if len(alerts) < 2:
                continue

            # Sort by timestamp
            sorted_alerts = sorted(alerts, key=lambda a: a.created_at)

            if keep_first:
                # Suppress all but first
                for alert in sorted_alerts[1:]:
                    suppress_ids.add(alert.alert_id)
            else:
                # Suppress all in group
                for alert in sorted_alerts:
                    suppress_ids.add(alert.alert_id)

        logger.info(f"Identified {len(suppress_ids)} alerts for suppression")
        return suppress_ids

    def find_similar_alerts(
        self,
        alert: Any,
        candidate_alerts: List[Any],
        similarity_threshold: float = 0.7
    ) -> List[Any]:
        """
        Find alerts similar to a given alert.

        Uses tag overlap and source matching to determine similarity.

        Args:
            alert: Reference alert
            candidate_alerts: List of alerts to compare
            similarity_threshold: Minimum similarity score (0.0-1.0)

        Returns:
            List of similar alerts
        """
        similar = []

        for candidate in candidate_alerts:
            if candidate.alert_id == alert.alert_id:
                continue

            score = self._calculate_similarity(alert, candidate)
            if score >= similarity_threshold:
                similar.append(candidate)

        return similar

    def _calculate_similarity(self, alert1: Any, alert2: Any) -> float:
        """
        Calculate similarity score between two alerts.

        Args:
            alert1: First alert
            alert2: Second alert

        Returns:
            Similarity score (0.0 to 1.0)
        """
        score = 0.0
        factors = 0

        # Source match
        if alert1.source == alert2.source:
            score += 0.3
        factors += 0.3

        # Severity match
        if alert1.severity == alert2.severity:
            score += 0.2
        factors += 0.2

        # Tag overlap
        if alert1.tags and alert2.tags:
            common_tags = set(alert1.tags.keys()) & set(alert2.tags.keys())
            matching_tags = sum(
                1 for tag in common_tags
                if alert1.tags[tag] == alert2.tags[tag]
            )
            tag_score = matching_tags / max(len(alert1.tags), len(alert2.tags))
            score += tag_score * 0.5
        factors += 0.5

        return score / factors if factors > 0 else 0.0
