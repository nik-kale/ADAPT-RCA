# ADAPT-RCA V3.0 Features Guide

## Overview

Version 3.0 introduces real-time data ingestion capabilities and cloud platform integrations, transforming ADAPT-RCA from a batch-processing tool into a production-ready, real-time incident analysis system.

## What's New in V3.0

### Real-Time Capabilities
- **Webhook Receiver**: Secure HMAC-verified webhook ingestion for streaming events
- **Event History**: In-memory event storage with configurable retention
- **Multi-Source Support**: Unified interface for webhooks from different sources

### Cloud Platform Integrations
- **AWS CloudWatch**: Native integration with CloudWatch Logs using boto3
- **GCP Cloud Logging**: Google Cloud Platform logging integration
- **Azure Monitor**: Azure Monitor Logs with KQL query support
- **Unified Interface**: CloudLogEntry model for consistent processing

### Distributed Tracing
- **OpenTelemetry Support**: OTLP format trace analysis
- **Critical Path Detection**: Identify performance bottlenecks in distributed systems
- **Error Propagation**: Track how errors cascade across microservices
- **Service Dependency Mapping**: Automatic discovery of service relationships

---

## Webhook Receiver

### Quick Start

```python
from adapt_rca.integrations import WebhookReceiver

# Initialize with HMAC secrets for verification
receiver = WebhookReceiver(secrets={
    "github": "your-webhook-secret",
    "datadog": "dd-webhook-secret"
})

# Receive and verify webhook
event = receiver.receive(
    source="github",
    payload={"action": "push", "repository": "myapp"},
    headers={"X-Hub-Signature-256": "sha256=..."},
    signature="sha256=abc123..."
)

print(f"Received {event.event_type} from {event.source}")
print(f"Processed at: {event.received_at}")
```

### Security Features

**HMAC Signature Verification**:
- SHA-256 based signatures
- Constant-time comparison to prevent timing attacks
- Per-source secret configuration

**Event Validation**:
- Schema validation for known sources
- Automatic timestamp normalization
- Payload size limits

### Event History

```python
# Get recent events from a source
recent_events = receiver.get_events(source="datadog", limit=50)

# Get events within time range
from datetime import datetime, timedelta
start_time = datetime.now() - timedelta(hours=1)
events = receiver.get_events(since=start_time)

# Clear old events
receiver.clear_events(older_than=timedelta(days=7))
```

### Integration with ADAPT-RCA Analysis

```python
from adapt_rca import RCAEngine

engine = RCAEngine()

# Convert webhook events to ADAPT-RCA format
for webhook_event in receiver.get_events(source="monitoring"):
    adapted_event = {
        "timestamp": webhook_event.received_at.isoformat(),
        "service": webhook_event.payload.get("service"),
        "level": webhook_event.payload.get("severity", "INFO"),
        "message": webhook_event.payload.get("message")
    }

    engine.add_event(adapted_event)

# Run analysis on real-time data
result = engine.analyze()
```

---

## AWS CloudWatch Integration

### Prerequisites

```bash
pip install boto3
```

### Authentication Setup

```bash
# Option 1: Environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=us-east-1

# Option 2: AWS credentials file (~/.aws/credentials)
[default]
aws_access_key_id = your_access_key
aws_secret_access_key = your_secret_key
region = us-east-1

# Option 3: IAM role (when running on EC2/ECS)
# No configuration needed - uses instance metadata
```

### Basic Usage

```python
from adapt_rca.integrations import AWSCloudWatchIntegration
from datetime import datetime, timedelta

# Initialize integration
cw = AWSCloudWatchIntegration(
    log_group_name="/aws/lambda/my-function",
    region_name="us-east-1"
)

# Fetch logs from last hour
start_time = datetime.now() - timedelta(hours=1)
logs = list(cw.fetch_logs(start_time=start_time))

print(f"Retrieved {len(logs)} log entries")
for log in logs[:5]:
    print(f"[{log.timestamp}] {log.service}: {log.message}")
```

### Advanced Filtering

```python
# Filter by log level
error_logs = list(cw.fetch_logs(
    start_time=start_time,
    filter_pattern="ERROR"
))

# Filter by custom pattern
auth_failures = list(cw.fetch_logs(
    start_time=start_time,
    filter_pattern="[timestamp, request_id, level=ERROR, msg=\"Authentication failed\"]"
))

# Multiple log streams
logs_from_streams = list(cw.fetch_logs(
    start_time=start_time,
    log_stream_names=["stream-1", "stream-2", "stream-3"]
))
```

### Integration with RCA Engine

```python
from adapt_rca import RCAEngine

engine = RCAEngine()

# Load CloudWatch logs for analysis
for log_entry in cw.fetch_logs(start_time=start_time):
    event = {
        "timestamp": log_entry.timestamp.isoformat(),
        "service": log_entry.service or "unknown",
        "level": log_entry.severity,
        "message": log_entry.message,
        "metadata": log_entry.metadata
    }
    engine.add_event(event)

# Analyze incidents from CloudWatch logs
result = engine.analyze()
print(f"Root causes: {result.root_causes}")
```

### Error Handling

```python
from botocore.exceptions import ClientError, NoCredentialsError

try:
    logs = list(cw.fetch_logs(start_time=start_time))
except NoCredentialsError:
    print("AWS credentials not configured")
except ClientError as e:
    if e.response['Error']['Code'] == 'ResourceNotFoundException':
        print(f"Log group not found: {cw.log_group_name}")
    else:
        print(f"AWS error: {e}")
```

---

## GCP Cloud Logging Integration

### Prerequisites

```bash
pip install google-cloud-logging
```

### Authentication Setup

```bash
# Download service account key from GCP Console
# Set environment variable
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

### Basic Usage

```python
from adapt_rca.integrations import GCPLoggingIntegration
from datetime import datetime, timedelta

# Initialize integration
gcp = GCPLoggingIntegration(
    project_id="my-gcp-project",
    log_filter='resource.type="gce_instance"'
)

# Fetch logs from last 6 hours
start_time = datetime.now() - timedelta(hours=6)
logs = list(gcp.fetch_logs(start_time=start_time))

print(f"Retrieved {len(logs)} log entries from GCP")
```

### Advanced Filtering

```python
# Filter by severity
error_logs = GCPLoggingIntegration(
    project_id="my-project",
    log_filter='severity>=ERROR'
)

# Filter by resource and time
app_logs = GCPLoggingIntegration(
    project_id="my-project",
    log_filter='''
        resource.type="k8s_container"
        AND resource.labels.namespace_name="production"
        AND jsonPayload.service="api-gateway"
    '''
)

# Complex filter with multiple conditions
critical_logs = GCPLoggingIntegration(
    project_id="my-project",
    log_filter='''
        (severity=ERROR OR severity=CRITICAL)
        AND timestamp>="2024-01-01T00:00:00Z"
        AND NOT jsonPayload.user_id=""
    '''
)

logs = list(critical_logs.fetch_logs(start_time=start_time))
```

### Structured Logging

```python
# GCP logs often contain structured JSON payloads
for log_entry in gcp.fetch_logs(start_time=start_time):
    print(f"Service: {log_entry.service}")
    print(f"Severity: {log_entry.severity}")

    # Access structured metadata
    if 'trace_id' in log_entry.metadata:
        print(f"Trace ID: {log_entry.metadata['trace_id']}")

    if 'http_request' in log_entry.metadata:
        http = log_entry.metadata['http_request']
        print(f"HTTP {http.get('request_method')} {http.get('request_url')}")
```

---

## Azure Monitor Integration

### Prerequisites

```bash
pip install azure-monitor-query azure-identity
```

### Authentication Setup

```bash
# Option 1: Service Principal
export AZURE_TENANT_ID=your_tenant_id
export AZURE_CLIENT_ID=your_client_id
export AZURE_CLIENT_SECRET=your_client_secret

# Option 2: Azure CLI (for development)
az login
```

### Basic Usage

```python
from adapt_rca.integrations import AzureMonitorIntegration
from datetime import datetime, timedelta

# Initialize integration
azure = AzureMonitorIntegration(
    workspace_id="your-workspace-id",
    query="AppTraces | where TimeGenerated > ago(1h)"
)

# Fetch logs
start_time = datetime.now() - timedelta(hours=1)
logs = list(azure.fetch_logs(start_time=start_time))

print(f"Retrieved {len(logs)} log entries from Azure Monitor")
```

### KQL Query Examples

```python
# Application errors
error_query = """
AppExceptions
| where TimeGenerated > ago(6h)
| where SeverityLevel >= 3
| project TimeGenerated, AppRoleName, Message, Properties
| order by TimeGenerated desc
"""

azure_errors = AzureMonitorIntegration(
    workspace_id="workspace-id",
    query=error_query
)

# Performance issues
perf_query = """
AppRequests
| where TimeGenerated > ago(1h)
| where DurationMs > 1000
| summarize
    Count=count(),
    AvgDuration=avg(DurationMs),
    MaxDuration=max(DurationMs)
    by Name, AppRoleName
| order by Count desc
"""

# Custom metrics
metrics_query = """
customMetrics
| where name == "error_rate"
| where value > 0.05
| project timestamp, service=customDimensions.service, value
"""
```

### Integration with Alerting

```python
from adapt_rca.alerting import AlertManager, Alert, AlertSeverity
from adapt_rca.integrations import AzureMonitorIntegration

alert_manager = AlertManager()

# Query for critical errors
azure = AzureMonitorIntegration(
    workspace_id="workspace-id",
    query="AppExceptions | where SeverityLevel == 4"
)

for log_entry in azure.fetch_logs(start_time=start_time):
    # Create alert for each critical error
    alert = Alert(
        title=f"Critical error in {log_entry.service}",
        severity=AlertSeverity.CRITICAL,
        description=log_entry.message,
        tags={"source": "azure", "service": log_entry.service}
    )

    alert_manager.send_alert(alert)
```

---

## OpenTelemetry Support

### Overview

ADAPT-RCA can analyze OpenTelemetry distributed traces to identify:
- Performance bottlenecks (slow spans)
- Error propagation across services
- Critical path through distributed operations
- Service dependency issues

### Data Format

```python
from adapt_rca.integrations import OpenTelemetryAnalyzer, Trace, Span

# Create trace with spans
trace = Trace(
    trace_id="abc123",
    root_span_id="span-1"
)

# Add spans
trace.add_span(Span(
    span_id="span-1",
    parent_span_id=None,
    service_name="api-gateway",
    operation_name="POST /checkout",
    start_time=1234567890.0,
    end_time=1234567895.5,
    status="OK",
    attributes={"http.method": "POST", "http.status_code": 200}
))

trace.add_span(Span(
    span_id="span-2",
    parent_span_id="span-1",
    service_name="payment-service",
    operation_name="process_payment",
    start_time=1234567891.0,
    end_time=1234567894.0,
    status="ERROR",
    attributes={"error": "Payment gateway timeout"}
))
```

### Trace Analysis

```python
analyzer = OpenTelemetryAnalyzer()

# Analyze for issues
issues = analyzer.analyze_trace(trace)

for issue in issues:
    print(f"Issue: {issue['issue']}")
    print(f"Severity: {issue['severity']}")
    print(f"Service: {issue['service']}")
    print(f"Details: {issue['details']}")
    print("---")
```

### Loading OTLP Data

```python
import json

# Load OTLP JSON export
with open('traces.json', 'r') as f:
    otlp_data = json.load(f)

traces = []
for resource_span in otlp_data['resourceSpans']:
    for scope_span in resource_span['scopeSpans']:
        for span_data in scope_span['spans']:
            # Convert OTLP format to ADAPT-RCA format
            span = Span(
                span_id=span_data['spanId'],
                parent_span_id=span_data.get('parentSpanId'),
                service_name=resource_span['resource']['attributes'].get('service.name', 'unknown'),
                operation_name=span_data['name'],
                start_time=span_data['startTimeUnixNano'] / 1e9,
                end_time=span_data['endTimeUnixNano'] / 1e9,
                status=span_data['status']['code'],
                attributes=span_data.get('attributes', {})
            )

            # Group by trace_id
            trace_id = span_data['traceId']
            # ... (add to appropriate trace)

# Analyze all traces
for trace in traces:
    issues = analyzer.analyze_trace(trace)
    if issues:
        print(f"Trace {trace.trace_id} has {len(issues)} issues")
```

### Critical Path Analysis

```python
# Get critical path (slowest route through trace)
critical_path = trace.get_critical_path()

total_duration = sum(span.duration for span in critical_path)
print(f"Critical path duration: {total_duration:.2f}s")

for span in critical_path:
    print(f"  {span.service_name}.{span.operation_name}: {span.duration:.2f}s")
```

### Error Propagation

```python
# Detect how errors cascade through services
propagation = analyzer._detect_error_propagation(trace)

if propagation:
    print(f"Error originated in: {propagation['origin_service']}")
    print(f"Propagated to {len(propagation['affected_services'])} services:")
    for service in propagation['affected_services']:
        print(f"  - {service}")
```

### Service Dependencies

```python
# Analyze service call patterns
dependencies = analyzer._analyze_dependencies(trace)

print("Service dependencies:")
for dep in dependencies:
    print(f"  {dep['caller']} -> {dep['callee']}")
    print(f"    Calls: {dep['call_count']}")
    print(f"    Avg latency: {dep['avg_latency']:.2f}ms")
    if dep['error_rate'] > 0:
        print(f"    Error rate: {dep['error_rate']:.1%}")
```

---

## Complete Example: Multi-Cloud RCA Pipeline

```python
from adapt_rca import RCAEngine
from adapt_rca.integrations import (
    WebhookReceiver,
    AWSCloudWatchIntegration,
    GCPLoggingIntegration,
    AzureMonitorIntegration,
    OpenTelemetryAnalyzer
)
from adapt_rca.alerting import AlertManager, SlackNotifier
from datetime import datetime, timedelta

# Initialize components
engine = RCAEngine()
alert_manager = AlertManager()
alert_manager.add_notifier(SlackNotifier(webhook_url="https://hooks.slack.com/..."))

# 1. Collect logs from AWS
aws_cw = AWSCloudWatchIntegration(
    log_group_name="/aws/lambda/checkout-service",
    region_name="us-east-1"
)

start_time = datetime.now() - timedelta(hours=1)
for log_entry in aws_cw.fetch_logs(start_time=start_time):
    engine.add_event({
        "timestamp": log_entry.timestamp.isoformat(),
        "service": "checkout-lambda",
        "level": log_entry.severity,
        "message": log_entry.message
    })

# 2. Collect logs from GCP
gcp_logging = GCPLoggingIntegration(
    project_id="my-project",
    log_filter='resource.type="k8s_container" AND severity>=WARNING'
)

for log_entry in gcp_logging.fetch_logs(start_time=start_time):
    engine.add_event({
        "timestamp": log_entry.timestamp.isoformat(),
        "service": log_entry.service or "k8s",
        "level": log_entry.severity,
        "message": log_entry.message
    })

# 3. Collect logs from Azure
azure_monitor = AzureMonitorIntegration(
    workspace_id="workspace-id",
    query="AppExceptions | where TimeGenerated > ago(1h)"
)

for log_entry in azure_monitor.fetch_logs(start_time=start_time):
    engine.add_event({
        "timestamp": log_entry.timestamp.isoformat(),
        "service": log_entry.service or "azure-app",
        "level": log_entry.severity,
        "message": log_entry.message
    })

# 4. Real-time webhook events
webhook_receiver = WebhookReceiver(secrets={"monitoring": "secret"})
for webhook_event in webhook_receiver.get_events(source="monitoring"):
    engine.add_event({
        "timestamp": webhook_event.received_at.isoformat(),
        "service": webhook_event.payload.get("service"),
        "level": "ERROR",
        "message": webhook_event.payload.get("alert_message")
    })

# 5. Run RCA analysis
result = engine.analyze()

# 6. Send alerts for root causes
for root_cause in result.root_causes:
    from adapt_rca.alerting import Alert, AlertSeverity

    alert = Alert(
        title=f"Root cause detected: {root_cause.get('service')}",
        severity=AlertSeverity.HIGH,
        description=f"Analysis identified root cause in {root_cause.get('service')}: {root_cause.get('reason')}",
        tags={"source": "rca-engine", "service": root_cause.get('service')}
    )

    alert_manager.send_alert(alert)

print(f"Analysis complete. Found {len(result.root_causes)} root causes.")
print(f"Sent {alert_manager.get_stats()['total_sent']} alerts")
```

---

## Best Practices

### Security

1. **Webhook Secrets**: Always use HMAC verification for webhooks
   ```python
   # Good
   receiver = WebhookReceiver(secrets={"source": os.getenv("WEBHOOK_SECRET")})

   # Bad
   receiver = WebhookReceiver()  # No verification
   ```

2. **Cloud Credentials**: Never hardcode credentials
   ```python
   # Good - use environment variables or IAM roles
   cw = AWSCloudWatchIntegration(log_group_name="/aws/app")

   # Bad
   cw = AWSCloudWatchIntegration(
       log_group_name="/aws/app",
       aws_access_key_id="AKIA...",  # Don't do this!
   )
   ```

3. **Rate Limiting**: Configure appropriate limits for cloud API calls
   ```python
   # Fetch with time limits to avoid excessive API costs
   logs = list(cw.fetch_logs(
       start_time=start_time,
       end_time=datetime.now(),
       limit=10000  # Cap at 10k logs
   ))
   ```

### Performance

1. **Batch Processing**: Process logs in batches
   ```python
   batch = []
   for log_entry in cw.fetch_logs(start_time=start_time):
       batch.append(log_entry)
       if len(batch) >= 100:
           # Process batch
           process_batch(batch)
           batch = []
   ```

2. **Time Windows**: Use appropriate time ranges
   ```python
   # Good - specific time window
   start_time = datetime.now() - timedelta(hours=1)

   # Bad - too broad, expensive query
   start_time = datetime.now() - timedelta(days=365)
   ```

3. **Filtering**: Push filtering to cloud provider
   ```python
   # Good - filter at source
   cw.fetch_logs(start_time=start_time, filter_pattern="ERROR")

   # Bad - fetch everything, filter locally
   all_logs = cw.fetch_logs(start_time=start_time)
   errors = [log for log in all_logs if "ERROR" in log.message]
   ```

### Error Handling

```python
from botocore.exceptions import ClientError
from google.api_core.exceptions import GoogleAPIError
from azure.core.exceptions import AzureError

def safe_fetch_logs(integration, start_time):
    """Fetch logs with proper error handling."""
    try:
        return list(integration.fetch_logs(start_time=start_time))
    except (ClientError, GoogleAPIError, AzureError) as e:
        logger.error(f"Failed to fetch logs from {integration.__class__.__name__}: {e}")
        return []
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return []

# Use in production
aws_logs = safe_fetch_logs(aws_integration, start_time)
gcp_logs = safe_fetch_logs(gcp_integration, start_time)
```

---

## Troubleshooting

### Webhook Issues

**Problem**: Webhooks failing signature verification

**Solution**: Verify secret configuration and signature format
```python
# Debug signature verification
import hmac
import hashlib

payload_bytes = json.dumps(payload).encode()
expected_sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
print(f"Expected: {expected_sig}")
print(f"Received: {signature}")
```

### AWS CloudWatch Issues

**Problem**: `NoCredentialsError`

**Solution**: Configure AWS credentials properly
```bash
aws configure
# or
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
```

**Problem**: `ResourceNotFoundException` for log group

**Solution**: Verify log group exists
```bash
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/
```

### GCP Logging Issues

**Problem**: `PermissionDenied` error

**Solution**: Ensure service account has required roles
```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:SA_EMAIL" \
    --role="roles/logging.viewer"
```

### Azure Monitor Issues

**Problem**: Authentication failures

**Solution**: Verify environment variables
```bash
echo $AZURE_TENANT_ID
echo $AZURE_CLIENT_ID
# Ensure these are set correctly
```

**Problem**: Invalid KQL query

**Solution**: Test query in Azure Portal Log Analytics first
```
# Test in portal, then copy to code
AppTraces
| where TimeGenerated > ago(1h)
| limit 10
```

---

## Migration from V2.0

V3.0 is fully backward compatible with V2.0. Existing code continues to work unchanged.

**New capabilities added**:
- Real-time ingestion via webhooks
- Cloud platform data sources
- Distributed tracing analysis

**No breaking changes** to existing APIs.

---

## What's Next

**Planned for V4.0**:
- Machine learning-based anomaly detection (Isolation Forest, LSTM)
- Automated remediation engine with runbook execution
- Enhanced predictive capabilities

**Planned for V5.0**:
- Multi-tenancy support
- Role-based access control (RBAC)
- High availability features

See [ROADMAP_PROGRESS.md](../ROADMAP_PROGRESS.md) for complete roadmap.
