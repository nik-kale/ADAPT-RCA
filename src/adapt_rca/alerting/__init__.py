"""
Alerting and notification system for ADAPT-RCA.

This module provides multi-channel alerting capabilities including
Slack, Email, Webhooks, and PagerDuty integration.
"""

from .alert_manager import AlertManager, Alert, AlertSeverity, AlertStatus
from .notifiers import (
    Notifier,
    SlackNotifier,
    EmailNotifier,
    WebhookNotifier,
    ConsoleNotifier
)
from .correlation import AlertCorrelator, CorrelationRule

__all__ = [
    "AlertManager",
    "Alert",
    "AlertSeverity",
    "AlertStatus",
    "Notifier",
    "SlackNotifier",
    "EmailNotifier",
    "WebhookNotifier",
    "ConsoleNotifier",
    "AlertCorrelator",
    "CorrelationRule",
]
