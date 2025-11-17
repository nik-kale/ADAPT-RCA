#!/usr/bin/env python3
"""
Multi-Cloud Integration Example for ADAPT-RCA

This example demonstrates how to:
1. Collect logs from AWS, GCP, and Azure simultaneously
2. Normalize logs from different cloud providers
3. Run unified RCA analysis across multi-cloud infrastructure
4. Generate alerts for cross-cloud incidents

Prerequisites:
    pip install boto3 google-cloud-logging azure-monitor-query azure-identity

    # AWS credentials
    export AWS_ACCESS_KEY_ID=...
    export AWS_SECRET_ACCESS_KEY=...
    export AWS_REGION=us-east-1

    # GCP credentials
    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
    export GCP_PROJECT_ID=my-project

    # Azure credentials
    export AZURE_TENANT_ID=...
    export AZURE_CLIENT_ID=...
    export AZURE_CLIENT_SECRET=...
    export AZURE_WORKSPACE_ID=...

Usage:
    python multi_cloud_example.py
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import defaultdict

from adapt_rca.integrations import (
    AWSCloudWatchIntegration,
    GCPLoggingIntegration,
    AzureMonitorIntegration,
    CloudLogEntry
)
from adapt_rca import RCAEngine
from adapt_rca.alerting import AlertManager, Alert, AlertSeverity, ConsoleNotifier
from adapt_rca.analytics import MetricsTracker, AnomalyDetector
from adapt_rca.storage import IncidentStore


class MultiCloudMonitor:
    """Unified monitoring across AWS, GCP, and Azure."""

    def __init__(self):
        """Initialize multi-cloud integrations."""
        self.aws_integrations: List[AWSCloudWatchIntegration] = []
        self.gcp_integrations: List[GCPLoggingIntegration] = []
        self.azure_integrations: List[AzureMonitorIntegration] = []

        self.rca_engine = RCAEngine()
        self.alert_manager = AlertManager()
        self.metrics_tracker = MetricsTracker()
        self.anomaly_detector = AnomalyDetector()
        self.incident_store = IncidentStore()

        # Add console notifier
        self.alert_manager.add_notifier(ConsoleNotifier())

    def add_aws_source(self, log_group: str, region: str = "us-east-1"):
        """Add AWS CloudWatch log group to monitor."""
        integration = AWSCloudWatchIntegration(
            log_group_name=log_group,
            region_name=region
        )
        self.aws_integrations.append(integration)
        print(f"✅ Added AWS source: {log_group} ({region})")

    def add_gcp_source(self, project_id: str, log_filter: str):
        """Add GCP Cloud Logging source to monitor."""
        integration = GCPLoggingIntegration(
            project_id=project_id,
            log_filter=log_filter
        )
        self.gcp_integrations.append(integration)
        print(f"✅ Added GCP source: {project_id}")

    def add_azure_source(self, workspace_id: str, query: str):
        """Add Azure Monitor source to monitor."""
        integration = AzureMonitorIntegration(
            workspace_id=workspace_id,
            query=query
        )
        self.azure_integrations.append(integration)
        print(f"✅ Added Azure source: {workspace_id}")

    def fetch_all_logs(
        self,
        start_time: datetime,
        end_time: datetime | None = None
    ) -> List[CloudLogEntry]:
        """Fetch logs from all configured cloud sources."""
        all_logs: List[CloudLogEntry] = []

        # Fetch from AWS
        print(f"\n📥 Fetching from {len(self.aws_integrations)} AWS sources...")
        for i, integration in enumerate(self.aws_integrations, 1):
            try:
                logs = list(integration.fetch_logs(
                    start_time=start_time,
                    end_time=end_time
                ))
                all_logs.extend(logs)
                print(f"  AWS {i}: {len(logs)} logs")
            except Exception as e:
                print(f"  AWS {i}: Error - {e}")

        # Fetch from GCP
        print(f"\n📥 Fetching from {len(self.gcp_integrations)} GCP sources...")
        for i, integration in enumerate(self.gcp_integrations, 1):
            try:
                logs = list(integration.fetch_logs(
                    start_time=start_time,
                    end_time=end_time
                ))
                all_logs.extend(logs)
                print(f"  GCP {i}: {len(logs)} logs")
            except Exception as e:
                print(f"  GCP {i}: Error - {e}")

        # Fetch from Azure
        print(f"\n📥 Fetching from {len(self.azure_integrations)} Azure sources...")
        for i, integration in enumerate(self.azure_integrations, 1):
            try:
                logs = list(integration.fetch_logs(
                    start_time=start_time,
                    end_time=end_time
                ))
                all_logs.extend(logs)
                print(f"  Azure {i}: {len(logs)} logs")
            except Exception as e:
                print(f"  Azure {i}: Error - {e}")

        # Sort by timestamp
        all_logs.sort(key=lambda log: log.timestamp)

        print(f"\n✅ Total logs collected: {len(all_logs)}")
        return all_logs

    def analyze_logs(self, logs: List[CloudLogEntry]):
        """Run RCA analysis on collected logs."""
        print("\n🔍 Running RCA analysis...")

        # Convert to RCA event format
        for log_entry in logs:
            event = {
                "timestamp": log_entry.timestamp.isoformat(),
                "service": log_entry.service or "unknown",
                "level": log_entry.severity,
                "message": log_entry.message,
                "metadata": {
                    **log_entry.metadata,
                    "cloud_provider": log_entry.metadata.get("source", "unknown")
                }
            }
            self.rca_engine.add_event(event)

        # Run analysis
        result = self.rca_engine.analyze()

        # Display results
        print(f"\n📊 Analysis Results:")
        print(f"  Root Causes: {len(result.root_causes)}")
        print(f"  Recommendations: {len(result.recommendations)}")

        # Create alerts for root causes
        for root_cause in result.root_causes:
            alert = Alert(
                title=f"[Multi-Cloud] Root cause in {root_cause.get('service')}",
                severity=AlertSeverity.HIGH,
                description=root_cause.get('reason', 'Unknown'),
                tags={
                    "source": "multi-cloud-rca",
                    "service": root_cause.get('service')
                }
            )
            self.alert_manager.send_alert(alert)

            # Store incident
            self.incident_store.store_incident(
                incident_id=f"incident-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                created_at=datetime.now(),
                severity="high",
                affected_services=[root_cause.get('service')],
                root_causes=[root_cause],
                recommended_actions=result.recommendations
            )

        return result

    def generate_statistics(self, logs: List[CloudLogEntry]):
        """Generate statistics from logs."""
        print("\n📈 Statistics:")

        # By cloud provider
        by_provider: Dict[str, int] = defaultdict(int)
        # By service
        by_service: Dict[str, int] = defaultdict(int)
        # By severity
        by_severity: Dict[str, int] = defaultdict(int)

        for log in logs:
            provider = log.metadata.get("source", "unknown")
            by_provider[provider] += 1
            by_service[log.service or "unknown"] += 1
            by_severity[log.severity] += 1

        print("\n  By Cloud Provider:")
        for provider, count in sorted(by_provider.items(), key=lambda x: -x[1]):
            percentage = (count / len(logs) * 100) if logs else 0
            print(f"    {provider}: {count} ({percentage:.1f}%)")

        print("\n  By Service (Top 10):")
        for service, count in sorted(by_service.items(), key=lambda x: -x[1])[:10]:
            print(f"    {service}: {count}")

        print("\n  By Severity:")
        for severity, count in sorted(by_severity.items()):
            print(f"    {severity}: {count}")

    def detect_anomalies(self, logs: List[CloudLogEntry]):
        """Detect anomalies in error rates by service."""
        print("\n🔎 Anomaly Detection:")

        # Track error rates by service
        service_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"total": 0, "errors": 0}
        )

        for log in logs:
            service = log.service or "unknown"
            service_stats[service]["total"] += 1
            if log.severity in ["ERROR", "CRITICAL"]:
                service_stats[service]["errors"] += 1

        # Check each service for anomalies
        anomalies_found = 0
        for service, stats in service_stats.items():
            if stats["total"] < 10:  # Skip services with too few logs
                continue

            error_rate = stats["errors"] / stats["total"]

            # Record metric
            self.metrics_tracker.record(
                "error_rate",
                error_rate,
                tags={"service": service}
            )

            # Simple threshold-based detection (can be enhanced with ML)
            if error_rate > 0.1:  # 10% error threshold
                print(f"\n  ⚠️  Anomaly in {service}:")
                print(f"    Error rate: {error_rate:.1%}")
                print(f"    Errors: {stats['errors']}/{stats['total']}")

                # Send alert
                alert = Alert(
                    title=f"High error rate in {service}",
                    severity=AlertSeverity.WARNING,
                    description=f"Error rate of {error_rate:.1%} detected in {service}",
                    tags={"service": service, "type": "anomaly"}
                )
                self.alert_manager.send_alert(alert)
                anomalies_found += 1

        if anomalies_found == 0:
            print("\n  ✅ No anomalies detected")


def example_basic_multi_cloud():
    """Basic multi-cloud monitoring example."""
    print("=" * 70)
    print("Example 1: Basic Multi-Cloud Monitoring")
    print("=" * 70)

    monitor = MultiCloudMonitor()

    # Add sources from each cloud provider
    # AWS
    if os.getenv("AWS_ACCESS_KEY_ID"):
        monitor.add_aws_source(
            log_group=os.getenv("AWS_LOG_GROUP", "/aws/lambda/my-function"),
            region=os.getenv("AWS_REGION", "us-east-1")
        )

    # GCP
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        monitor.add_gcp_source(
            project_id=os.getenv("GCP_PROJECT_ID", "my-project"),
            log_filter='severity>=WARNING'
        )

    # Azure
    if os.getenv("AZURE_WORKSPACE_ID"):
        monitor.add_azure_source(
            workspace_id=os.getenv("AZURE_WORKSPACE_ID"),
            query="AppExceptions | where TimeGenerated > ago(1h)"
        )

    # Fetch logs from last hour
    start_time = datetime.now() - timedelta(hours=1)
    logs = monitor.fetch_all_logs(start_time=start_time)

    if logs:
        # Generate statistics
        monitor.generate_statistics(logs)

        # Run RCA analysis
        monitor.analyze_logs(logs)

        # Detect anomalies
        monitor.detect_anomalies(logs)
    else:
        print("\n⚠️  No logs found. Check your cloud provider credentials and configuration.")


def example_cross_cloud_incident():
    """Simulate cross-cloud incident detection."""
    print("=" * 70)
    print("Example 2: Cross-Cloud Incident Detection")
    print("=" * 70)

    monitor = MultiCloudMonitor()

    # Simulate logs from multiple clouds
    # In production, these would come from actual cloud sources

    from adapt_rca.integrations import CloudLogEntry

    # AWS: API Gateway errors
    aws_logs = [
        CloudLogEntry(
            timestamp=datetime.now() - timedelta(minutes=5),
            service="api-gateway",
            severity="ERROR",
            message="503 Service Unavailable from backend",
            metadata={"source": "aws", "status_code": 503}
        ),
        CloudLogEntry(
            timestamp=datetime.now() - timedelta(minutes=4),
            service="api-gateway",
            severity="ERROR",
            message="Timeout calling payment service",
            metadata={"source": "aws", "timeout_ms": 5000}
        )
    ]

    # GCP: Payment service errors
    gcp_logs = [
        CloudLogEntry(
            timestamp=datetime.now() - timedelta(minutes=5),
            service="payment-service",
            severity="ERROR",
            message="Database connection pool exhausted",
            metadata={"source": "gcp", "pool_size": 10}
        ),
        CloudLogEntry(
            timestamp=datetime.now() - timedelta(minutes=3),
            service="payment-service",
            severity="CRITICAL",
            message="Circuit breaker opened for database",
            metadata={"source": "gcp"}
        )
    ]

    # Azure: Database alerts
    azure_logs = [
        CloudLogEntry(
            timestamp=datetime.now() - timedelta(minutes=6),
            service="postgres-db",
            severity="WARNING",
            message="High connection count: 95/100",
            metadata={"source": "azure", "connections": 95}
        ),
        CloudLogEntry(
            timestamp=datetime.now() - timedelta(minutes=5),
            service="postgres-db",
            severity="ERROR",
            message="Max connections reached",
            metadata={"source": "azure", "connections": 100}
        )
    ]

    all_logs = aws_logs + gcp_logs + azure_logs
    all_logs.sort(key=lambda log: log.timestamp)

    print(f"\nSimulated {len(all_logs)} logs from 3 cloud providers\n")

    # Display timeline
    print("Timeline of events:")
    for log in all_logs:
        provider = log.metadata.get("source", "unknown").upper()
        print(f"  [{log.timestamp.strftime('%H:%M:%S')}] {provider:5} | {log.service:20} | {log.severity:8} | {log.message}")

    # Analyze
    print("\n" + "=" * 70)
    result = monitor.analyze_logs(all_logs)

    print("\n📊 Cross-Cloud Incident Analysis:")
    print("\nRoot Causes:")
    for i, rc in enumerate(result.root_causes, 1):
        print(f"  {i}. {rc.get('service')}: {rc.get('reason')}")

    print("\nImpact Chain:")
    print("  Azure DB → GCP Payment Service → AWS API Gateway")
    print("\nConclusion:")
    print("  Database connection exhaustion in Azure cascaded to")
    print("  payment service failures in GCP, which caused API")
    print("  gateway timeouts in AWS.")


def main():
    """Run examples."""
    print("\n" + "=" * 70)
    print("ADAPT-RCA Multi-Cloud Integration Examples")
    print("=" * 70 + "\n")

    # Check cloud provider credentials
    print("Cloud Provider Configuration:")
    print(f"  AWS: {'✅ Configured' if os.getenv('AWS_ACCESS_KEY_ID') else '❌ Not configured'}")
    print(f"  GCP: {'✅ Configured' if os.getenv('GOOGLE_APPLICATION_CREDENTIALS') else '❌ Not configured'}")
    print(f"  Azure: {'✅ Configured' if os.getenv('AZURE_WORKSPACE_ID') else '❌ Not configured'}")
    print()

    examples = [
        ("Basic Multi-Cloud Monitoring", example_basic_multi_cloud),
        ("Cross-Cloud Incident", example_cross_cloud_incident),
    ]

    if len(sys.argv) > 1:
        try:
            example_num = int(sys.argv[1]) - 1
            if 0 <= example_num < len(examples):
                name, func = examples[example_num]
                print(f"\nRunning Example: {name}\n")
                func()
            else:
                print(f"Invalid example number. Choose 1-{len(examples)}")
        except ValueError:
            print("Usage: python multi_cloud_example.py [example_number]")
    else:
        for i, (name, func) in enumerate(examples, 1):
            try:
                func()
                print("\n")
            except KeyboardInterrupt:
                print("\n\nExamples interrupted by user")
                break
            except Exception as e:
                print(f"\n❌ Example {i} failed: {e}\n")
                import traceback
                traceback.print_exc()
                continue


if __name__ == "__main__":
    main()
