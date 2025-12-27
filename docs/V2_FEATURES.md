# ADAPT-RCA V2.0 Features

## Overview

Version 2.0 introduces advanced analytics, alerting, and historical tracking capabilities based on industry best practices from Datadog, New Relic, PagerDuty, and open-source observability tools.

## New Features

### 1. Anomaly Detection Engine

Statistical anomaly detection to automatically identify unusual patterns in events, error rates, and service metrics.

**Location**: `src/adapt_rca/analytics/anomaly_detector.py`

**Features**:
- Multiple statistical methods:
  - **Z-Score**: Standard deviation-based detection
  - **IQR**: Interquartile range (robust to outliers)
  - **Moving Average**: Deviation from recent trends
- Configurable sensitivity thresholds
- Confidence scoring for each detection
- Service-level and event-level anomaly detection

**Example**:
```python
from adapt_rca.analytics import AnomalyDetector, StatisticalMethod

# Initialize detector
detector = AnomalyDetector(
    method=StatisticalMethod.ZSCORE,
    sensitivity=2.0  # 2 standard deviations
)

# Detect anomaly in error rate
result = detector.detect_error_rate_anomaly(
    current_rate=150,  # Current: 150 errors/min
    historical_rates=[50, 55, 48, 52, 49]  # Historical baseline
)

if result.is_anomaly:
    print(f"Anomaly detected!")
    print(f"Score: {result.score:.2f}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Baseline: {result.baseline_value}")
```

### 2. Multi-Channel Alerting System

Comprehensive alerting with deduplication, rate limiting, and multi-channel notification support.

**Location**: `src/adapt_rca/alerting/`

**Features**:
- Alert manager with lifecycle management
- Alert deduplication (merge identical alerts within time window)
- Rate limiting to prevent alert storms
- Multiple notification channels:
  - Console (colored output)
  - Slack (via webhooks)
  - Email (SMTP with HTML formatting)
  - Generic webhooks (custom integrations)

**Example**:
```python
from adapt_rca.alerting import (
    AlertManager, Alert, AlertSeverity,
    SlackNotifier, EmailNotifier, ConsoleNotifier
)

# Initialize manager
manager = AlertManager(
    deduplication_window_minutes=60,
    rate_limit_per_hour=100
)

# Add notifiers
manager.add_notifier("console", ConsoleNotifier())
manager.add_notifier("slack", SlackNotifier(
    webhook_url="https://hooks.slack.com/services/YOUR/WEBHOOK"
))

# Create and send alert
alert = Alert(
    title="High Error Rate Detected",
    message="API service error rate: 150 errors/min (baseline: 50)",
    severity=AlertSeverity.CRITICAL,
    source="api-service",
    tags={"region": "us-west", "environment": "production"}
)

manager.send_alert(alert)
```

### 3. Alert Correlation

Intelligent grouping of related alerts to reduce noise and identify incident patterns.

**Location**: `src/adapt_rca/alerting/correlation.py`

**Features**:
- Time-window based correlation
- Tag-based grouping (service, region, etc.)
- Configurable correlation rules
- Similarity detection between alerts
- Automatic suppression of duplicate alerts

**Example**:
```python
from adapt_rca.alerting import AlertCorrelator, CorrelationRule

# Initialize correlator
correlator = AlertCorrelator()

# Add correlation rule
correlator.add_rule(CorrelationRule(
    name="service_correlation",
    group_by_tags=["service", "region"],
    group_by_source=True,
    time_window_minutes=10,
    min_alerts=2
))

# Correlate alerts
groups = correlator.correlate_alerts(alerts)

# Get summary
summaries = correlator.get_correlated_summary(groups)
for summary in summaries:
    print(f"Group: {summary['group_key']}")
    print(f"  Alerts: {summary['alert_count']}")
    print(f"  Duration: {summary['duration_minutes']:.1f} min")
```

### 4. Metrics Tracking

Time-series metrics collection for performance analysis and anomaly detection.

**Location**: `src/adapt_rca/analytics/metrics_tracker.py`

**Features**:
- In-memory time-series storage with automatic cleanup
- Configurable retention period
- Tag-based filtering
- Statistical aggregations (average, percentile, rate)
- Efficient storage using deques

**Example**:
```python
from adapt_rca.analytics import MetricsTracker

# Initialize tracker
tracker = MetricsTracker(
    retention_hours=168,  # 7 days
    max_points_per_metric=10000
)

# Record metrics
tracker.record("error_rate", 15.5, tags={"service": "api"})
tracker.record("response_time", 250, tags={"service": "api"})

# Query metrics
recent_errors = tracker.get_recent("error_rate", hours=1)
avg_response = tracker.get_average("response_time", hours=6)
p95_response = tracker.get_percentile("response_time", 95, hours=24)

# Get rate
error_rate = tracker.get_rate("error_count", hours=1)
print(f"Error rate: {error_rate:.2f} errors/hour")
```

### 5. Incident Database

SQLite-based persistent storage for incidents, alerts, and historical analysis.

**Location**: `src/adapt_rca/storage/incident_store.py`

**Features**:
- Full incident history with root causes and actions
- Service-level tracking
- Statistical reporting and trend analysis
- Automatic cleanup of old data
- Metrics storage for time-series analysis

**Example**:
```python
from adapt_rca.storage import IncidentStore

# Initialize store
store = IncidentStore("adapt_rca.db")

# Store incident
store.store_incident(
    incident_id="INC-2024-001",
    created_at=datetime.now(),
    severity="critical",
    status="open",
    affected_services=["api-service", "database"],
    event_count=156,
    root_causes=[{
        "description": "Database connection pool exhausted",
        "confidence": 0.85,
        "evidence": ["Connection timeout errors", "Pool size: 100/100"]
    }],
    recommended_actions=[{
        "description": "Increase database connection pool size",
        "priority": 1,
        "category": "fix"
    }]
)

# Query incidents
recent = store.get_recent_incidents(hours=24, severity="critical")
stats = store.get_incident_stats(days=7)

print(f"Total incidents (7 days): {stats['total_incidents']}")
print(f"By severity: {stats['by_severity']}")
print(f"Top services: {stats['top_services']}")
```

## Integration Example

Complete example integrating all V2.0 features:

```python
from datetime import datetime
from adapt_rca.analytics import AnomalyDetector, MetricsTracker, StatisticalMethod
from adapt_rca.alerting import AlertManager, Alert, AlertSeverity, ConsoleNotifier
from adapt_rca.storage import IncidentStore

# Initialize components
detector = AnomalyDetector(method=StatisticalMethod.ZSCORE, sensitivity=2.0)
tracker = MetricsTracker(retention_hours=168)
alert_manager = AlertManager()
store = IncidentStore()

# Add notifier
alert_manager.add_notifier("console", ConsoleNotifier())

# Simulate error rate monitoring
def check_error_rate(service: str, current_rate: float):
    # Record metric
    tracker.record("error_rate", current_rate, tags={"service": service})

    # Get historical data
    historical = tracker.get_values("error_rate", hours=24, tags={"service": service})

    if len(historical) < 10:
        return  # Need baseline

    # Detect anomaly
    result = detector.detect_error_rate_anomaly(current_rate, historical)

    if result.is_anomaly:
        # Create alert
        alert = Alert(
            title=f"Anomalous Error Rate: {service}",
            message=f"Current: {current_rate:.1f} errors/min (baseline: {result.baseline_value:.1f})",
            severity=AlertSeverity.HIGH if result.score > 0.7 else AlertSeverity.MEDIUM,
            source=service,
            tags={"service": service, "anomaly_score": str(result.score)}
        )

        # Send alert
        alert_manager.send_alert(alert)

        # Store in database
        store.store_incident(
            incident_id=f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            created_at=datetime.now(),
            severity=alert.severity.value,
            status="open",
            affected_services=[service],
            event_count=1,
            root_causes=[{
                "description": f"Anomalous error rate detected",
                "confidence": result.confidence,
                "evidence": [f"Z-score: {result.details['zscore']:.2f}"]
            }],
            recommended_actions=[{
                "description": f"Investigate {service} for increased errors",
                "priority": 1,
                "category": "investigate"
            }]
        )

# Use it
check_error_rate("api-service", 150.0)
```

## Best Practices

### 1. Anomaly Detection
- Start with Z-score method (good balance of sensitivity and false positives)
- Tune sensitivity based on your environment (2.0-3.0 standard deviations is typical)
- Collect at least 10-20 historical data points for reliable detection
- Use IQR method for metrics with outliers

### 2. Alerting
- Set appropriate deduplication windows (5-60 minutes)
- Configure rate limits to prevent alert storms (50-100/hour)
- Use severity levels appropriately:
  - CRITICAL: Requires immediate action
  - HIGH: Urgent attention needed
  - MEDIUM: Address soon
  - LOW/INFO: Awareness only

### 3. Alert Correlation
- Group by service and region for distributed systems
- Use 5-10 minute time windows for correlation
- Require minimum 2-3 alerts before correlating
- Review correlation summaries regularly to tune rules

### 4. Metrics Tracking
- Choose appropriate retention periods (24 hours to 30 days)
- Use tags for filtering and aggregation
- Clean up old metrics to prevent memory issues
- Monitor tracker memory usage in production

### 5. Incident Database
- Run cleanup periodically (weekly/monthly)
- Keep 30-90 days of history for trend analysis
- Back up database before major cleanup operations
- Use indexes for performance with large datasets

## Migration Guide

### From V1.0 to V2.0

No breaking changes. V2.0 features are additive.

To use new features:

1. Import new modules:
```python
from adapt_rca.analytics import AnomalyDetector, MetricsTracker
from adapt_rca.alerting import AlertManager, Alert, AlertSeverity
from adapt_rca.storage import IncidentStore
```

2. Optional: Install additional dependencies for Slack/Email:
```bash
pip install requests  # For Slack and webhook notifiers
```

3. Initialize components as shown in examples above

## Performance Considerations

- **Anomaly Detector**: O(n) complexity, handles 10,000+ data points efficiently
- **Metrics Tracker**: Deque-based storage, O(1) append, automatic cleanup
- **Alert Manager**: In-memory deduplication, scales to 1000s of alerts
- **Incident Store**: SQLite with indexes, handles 100,000+ incidents

## Security Notes

- Alert notifiers (Slack, Email, Webhook) should use environment variables for credentials
- Database file should have appropriate file permissions (0600)
- Webhook URLs and API tokens should never be committed to version control
- Use TLS for email notifiers in production

## Troubleshooting

### Anomaly Detection Issues

**Problem**: Too many false positives
- **Solution**: Increase sensitivity threshold (2.5-3.0)
- **Solution**: Ensure sufficient historical data (20+ points)
- **Solution**: Try IQR method for metrics with outliers

**Problem**: Missing anomalies
- **Solution**: Decrease sensitivity threshold (1.5-2.0)
- **Solution**: Check if historical data is representative

### Alerting Issues

**Problem**: Alert storm
- **Solution**: Check rate limiting configuration
- **Solution**: Enable deduplication with longer window
- **Solution**: Use alert correlation to group related alerts

**Problem**: Slack notifications not working
- **Solution**: Verify webhook URL is correct
- **Solution**: Check network connectivity
- **Solution**: Install requests library: `pip install requests`

### Database Issues

**Problem**: Database file growing too large
- **Solution**: Run cleanup_old_data() regularly
- **Solution**: Reduce retention period
- **Solution**: Archive old data before cleanup

**Problem**: Slow queries
- **Solution**: Ensure indexes are created (automatic on init)
- **Solution**: Reduce query time windows
- **Solution**: Use SQLite VACUUM periodically

## What's Next?

Version 3.0 will add:
- Real-time streaming ingestion (Kafka, webhooks)
- Cloud provider integrations (AWS CloudWatch, GCP Logging, Azure Monitor)
- OpenTelemetry distributed tracing support
- Service dependency auto-discovery
- Enhanced web dashboard with real-time updates

Stay tuned!
