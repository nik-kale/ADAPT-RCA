"""
Cloud and third-party integrations for ADAPT-RCA.

Supports real-time data ingestion from various cloud providers and observability platforms.
"""

from .webhook_receiver import WebhookReceiver, WebhookEvent
from .cloud_providers import (
    AWSCloudWatchIntegration,
    GCPLoggingIntegration,
    AzureMonitorIntegration,
    CloudLogEntry
)
from .opentelemetry_support import OpenTelemetryAnalyzer, Trace, Span

__all__ = [
    "WebhookReceiver",
    "WebhookEvent",
    "AWSCloudWatchIntegration",
    "GCPLoggingIntegration",
    "AzureMonitorIntegration",
    "CloudLogEntry",
    "OpenTelemetryAnalyzer",
    "Trace",
    "Span",
]
