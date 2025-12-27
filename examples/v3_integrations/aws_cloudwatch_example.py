#!/usr/bin/env python3
"""
AWS CloudWatch Integration Example for ADAPT-RCA

This example demonstrates how to:
1. Fetch logs from AWS CloudWatch
2. Filter logs by patterns and time ranges
3. Process CloudWatch logs for RCA analysis
4. Integrate with alerting system

Prerequisites:
    pip install boto3

    # Configure AWS credentials (choose one):
    export AWS_ACCESS_KEY_ID=your_access_key
    export AWS_SECRET_ACCESS_KEY=your_secret_key
    export AWS_REGION=us-east-1

    # OR use AWS CLI:
    aws configure

Usage:
    python aws_cloudwatch_example.py
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any

from adapt_rca.integrations import AWSCloudWatchIntegration, CloudLogEntry
from adapt_rca import RCAEngine
from adapt_rca.alerting import AlertManager, Alert, AlertSeverity, ConsoleNotifier
from adapt_rca.analytics import AnomalyDetector, MetricsTracker


def example_basic_usage():
    """Basic CloudWatch log fetching."""
    print("=" * 60)
    print("Example 1: Basic CloudWatch Log Fetching")
    print("=" * 60)

    # Initialize integration
    log_group = os.getenv("AWS_LOG_GROUP", "/aws/lambda/my-function")
    region = os.getenv("AWS_REGION", "us-east-1")

    print(f"Log Group: {log_group}")
    print(f"Region: {region}\n")

    cw = AWSCloudWatchIntegration(
        log_group_name=log_group,
        region_name=region
    )

    # Fetch logs from last hour
    start_time = datetime.now() - timedelta(hours=1)
    print(f"Fetching logs since {start_time.strftime('%Y-%m-%d %H:%M:%S')}...\n")

    logs: List[CloudLogEntry] = list(cw.fetch_logs(start_time=start_time))

    print(f"✅ Retrieved {len(logs)} log entries\n")

    # Display first 5 logs
    for i, log in enumerate(logs[:5], 1):
        print(f"Log {i}:")
        print(f"  Timestamp: {log.timestamp}")
        print(f"  Service: {log.service}")
        print(f"  Severity: {log.severity}")
        print(f"  Message: {log.message[:100]}...")
        print()


def example_filtered_logs():
    """Fetch logs with filtering."""
    print("=" * 60)
    print("Example 2: Filtered Log Fetching")
    print("=" * 60)

    log_group = os.getenv("AWS_LOG_GROUP", "/aws/lambda/my-function")
    cw = AWSCloudWatchIntegration(
        log_group_name=log_group,
        region_name=os.getenv("AWS_REGION", "us-east-1")
    )

    start_time = datetime.now() - timedelta(hours=6)

    # Filter 1: Only ERROR logs
    print("Fetching ERROR logs only...\n")
    error_logs = list(cw.fetch_logs(
        start_time=start_time,
        filter_pattern="ERROR"
    ))
    print(f"Found {len(error_logs)} error logs\n")

    # Filter 2: Custom pattern (CloudWatch Logs Insights syntax)
    print("Fetching logs with custom pattern...\n")
    custom_logs = list(cw.fetch_logs(
        start_time=start_time,
        filter_pattern='[timestamp, request_id, level=ERROR, msg]'
    ))
    print(f"Found {len(custom_logs)} logs matching pattern\n")

    # Filter 3: Specific log streams
    print("Fetching from specific log streams...\n")
    stream_logs = list(cw.fetch_logs(
        start_time=start_time,
        log_stream_names=["2024/01/01/[$LATEST]abc123"]
    ))
    print(f"Found {len(stream_logs)} logs from specific streams\n")


def example_rca_integration():
    """Integrate CloudWatch logs with RCA engine."""
    print("=" * 60)
    print("Example 3: RCA Integration")
    print("=" * 60)

    # Initialize components
    log_group = os.getenv("AWS_LOG_GROUP", "/aws/lambda/my-function")
    cw = AWSCloudWatchIntegration(
        log_group_name=log_group,
        region_name=os.getenv("AWS_REGION", "us-east-1")
    )

    rca_engine = RCAEngine()
    alert_manager = AlertManager()
    alert_manager.add_notifier(ConsoleNotifier())

    # Fetch recent logs
    start_time = datetime.now() - timedelta(hours=2)
    print(f"Fetching logs for RCA analysis...\n")

    event_count = 0
    for log_entry in cw.fetch_logs(start_time=start_time):
        # Convert CloudWatch log to RCA event
        event = {
            "timestamp": log_entry.timestamp.isoformat(),
            "service": log_entry.service or "lambda",
            "level": log_entry.severity,
            "message": log_entry.message,
            "metadata": log_entry.metadata
        }

        rca_engine.add_event(event)
        event_count += 1

        # Limit for demo purposes
        if event_count >= 100:
            break

    print(f"Added {event_count} events to RCA engine\n")

    # Run RCA analysis
    print("Running RCA analysis...\n")
    result = rca_engine.analyze()

    # Display results
    print(f"Root Causes Found: {len(result.root_causes)}\n")
    for i, root_cause in enumerate(result.root_causes, 1):
        print(f"Root Cause {i}:")
        print(f"  Service: {root_cause.get('service')}")
        print(f"  Reason: {root_cause.get('reason')}")
        print()

        # Create alert for each root cause
        alert = Alert(
            title=f"Root cause detected in {root_cause.get('service')}",
            severity=AlertSeverity.HIGH,
            description=root_cause.get('reason', 'Unknown'),
            tags={"source": "cloudwatch", "service": root_cause.get('service')}
        )
        alert_manager.send_alert(alert)

    print(f"\nRecommendations: {len(result.recommendations)}")
    for i, rec in enumerate(result.recommendations, 1):
        print(f"  {i}. {rec.get('action')}")


def example_anomaly_detection():
    """Detect anomalies in CloudWatch metrics."""
    print("=" * 60)
    print("Example 4: Anomaly Detection on CloudWatch Logs")
    print("=" * 60)

    log_group = os.getenv("AWS_LOG_GROUP", "/aws/lambda/my-function")
    cw = AWSCloudWatchIntegration(
        log_group_name=log_group,
        region_name=os.getenv("AWS_REGION", "us-east-1")
    )

    metrics_tracker = MetricsTracker()
    anomaly_detector = AnomalyDetector()

    # Track error rates over time
    start_time = datetime.now() - timedelta(hours=24)
    print("Analyzing error rates over last 24 hours...\n")

    # Process logs in hourly buckets
    hourly_stats: Dict[int, Dict[str, int]] = {}

    for log_entry in cw.fetch_logs(start_time=start_time):
        hour = log_entry.timestamp.hour

        if hour not in hourly_stats:
            hourly_stats[hour] = {"total": 0, "errors": 0}

        hourly_stats[hour]["total"] += 1
        if log_entry.severity in ["ERROR", "CRITICAL"]:
            hourly_stats[hour]["errors"] += 1

    # Calculate error rates
    error_rates = []
    for hour in sorted(hourly_stats.keys()):
        stats = hourly_stats[hour]
        if stats["total"] > 0:
            error_rate = stats["errors"] / stats["total"]
            error_rates.append(error_rate)
            metrics_tracker.record(
                "error_rate",
                error_rate,
                tags={"hour": str(hour)}
            )
            print(f"Hour {hour:02d}: {stats['errors']}/{stats['total']} errors ({error_rate:.2%})")

    # Detect anomalies
    if len(error_rates) >= 3:
        current_rate = error_rates[-1]
        historical_rates = error_rates[:-1]

        print(f"\nDetecting anomalies...")
        print(f"Current error rate: {current_rate:.2%}")
        print(f"Historical average: {sum(historical_rates)/len(historical_rates):.2%}\n")

        anomaly_result = anomaly_detector.detect_error_rate_anomaly(
            current_rate=current_rate,
            historical_rates=historical_rates
        )

        if anomaly_result.is_anomaly:
            print(f"⚠️  ANOMALY DETECTED!")
            print(f"  Confidence: {anomaly_result.confidence:.1%}")
            print(f"  Reason: {anomaly_result.reason}")
        else:
            print("✅ No anomaly detected")
    else:
        print("\nNot enough data for anomaly detection")


def example_multi_log_group():
    """Monitor multiple log groups simultaneously."""
    print("=" * 60)
    print("Example 5: Multi-Log Group Monitoring")
    print("=" * 60)

    # Define multiple log groups to monitor
    log_groups = [
        "/aws/lambda/api-gateway",
        "/aws/lambda/auth-service",
        "/aws/lambda/payment-service"
    ]

    region = os.getenv("AWS_REGION", "us-east-1")
    start_time = datetime.now() - timedelta(hours=1)

    all_logs: List[CloudLogEntry] = []

    # Fetch from each log group
    for log_group in log_groups:
        print(f"Fetching from {log_group}...")

        try:
            cw = AWSCloudWatchIntegration(
                log_group_name=log_group,
                region_name=region
            )

            logs = list(cw.fetch_logs(start_time=start_time))
            all_logs.extend(logs)
            print(f"  ✅ Found {len(logs)} logs\n")

        except Exception as e:
            print(f"  ❌ Error: {e}\n")
            continue

    # Aggregate statistics
    print(f"Total logs collected: {len(all_logs)}")

    # Group by service
    by_service: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}

    for log in all_logs:
        service = log.service or "unknown"
        by_service[service] = by_service.get(service, 0) + 1
        by_severity[log.severity] = by_severity.get(log.severity, 0) + 1

    print("\nBy Service:")
    for service, count in sorted(by_service.items(), key=lambda x: -x[1]):
        print(f"  {service}: {count}")

    print("\nBy Severity:")
    for severity, count in sorted(by_severity.items()):
        print(f"  {severity}: {count}")


def example_error_handling():
    """Demonstrate proper error handling."""
    print("=" * 60)
    print("Example 6: Error Handling")
    print("=" * 60)

    from botocore.exceptions import ClientError, NoCredentialsError

    log_group = "/aws/lambda/nonexistent"
    region = "us-east-1"

    print(f"Attempting to fetch from non-existent log group: {log_group}\n")

    try:
        cw = AWSCloudWatchIntegration(
            log_group_name=log_group,
            region_name=region
        )

        start_time = datetime.now() - timedelta(hours=1)
        logs = list(cw.fetch_logs(start_time=start_time))

        print(f"Retrieved {len(logs)} logs")

    except NoCredentialsError:
        print("❌ Error: AWS credentials not configured")
        print("\nPlease configure credentials using one of these methods:")
        print("  1. Environment variables:")
        print("     export AWS_ACCESS_KEY_ID=...")
        print("     export AWS_SECRET_ACCESS_KEY=...")
        print("  2. AWS CLI: aws configure")
        print("  3. IAM role (when running on EC2/ECS)")

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']

        if error_code == 'ResourceNotFoundException':
            print(f"❌ Error: Log group not found: {log_group}")
            print("\nTo list available log groups, run:")
            print(f"  aws logs describe-log-groups --region {region}")

        elif error_code == 'AccessDeniedException':
            print("❌ Error: Access denied")
            print("\nEnsure your AWS credentials have the following permissions:")
            print("  - logs:FilterLogEvents")
            print("  - logs:DescribeLogGroups")

        else:
            print(f"❌ AWS Error [{error_code}]: {error_msg}")

    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("ADAPT-RCA AWS CloudWatch Integration Examples")
    print("=" * 60 + "\n")

    # Check if AWS credentials are configured
    try:
        import boto3
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"✅ AWS credentials configured")
        print(f"Account: {identity['Account']}")
        print(f"ARN: {identity['Arn']}\n")
    except Exception as e:
        print(f"⚠️  Warning: Could not verify AWS credentials: {e}")
        print("Some examples may not work without proper AWS configuration\n")

    # Run examples
    examples = [
        ("Basic Usage", example_basic_usage),
        ("Filtered Logs", example_filtered_logs),
        ("RCA Integration", example_rca_integration),
        ("Anomaly Detection", example_anomaly_detection),
        ("Multi-Log Group", example_multi_log_group),
        ("Error Handling", example_error_handling),
    ]

    if len(sys.argv) > 1:
        # Run specific example by number
        try:
            example_num = int(sys.argv[1]) - 1
            if 0 <= example_num < len(examples):
                name, func = examples[example_num]
                print(f"\nRunning Example: {name}\n")
                func()
            else:
                print(f"Invalid example number. Choose 1-{len(examples)}")
        except ValueError:
            print("Usage: python aws_cloudwatch_example.py [example_number]")
    else:
        # Run all examples
        for i, (name, func) in enumerate(examples, 1):
            try:
                func()
                print()
            except KeyboardInterrupt:
                print("\n\nExamples interrupted by user")
                break
            except Exception as e:
                print(f"\n❌ Example {i} failed: {e}\n")
                continue


if __name__ == "__main__":
    main()
