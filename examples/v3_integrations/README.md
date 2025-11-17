# ADAPT-RCA V3.0 Integration Examples

This directory contains comprehensive examples demonstrating ADAPT-RCA's V3.0 real-time and cloud integration features.

## Examples Overview

### 1. Webhook Receiver (`webhook_example.py`)

Demonstrates real-time webhook ingestion with HMAC verification.

**Features:**
- Webhook endpoints for multiple sources (Datadog, GitHub, PagerDuty)
- HMAC-SHA256 signature verification
- Flask application with webhook processing
- Integration with RCA analysis
- Real-time alerting

**Usage:**
```bash
# Start webhook receiver
python webhook_example.py

# Test mode (sends sample webhooks)
python webhook_example.py --test
```

**Prerequisites:**
```bash
# Optional: Configure webhook secrets
export DATADOG_WEBHOOK_SECRET=your-secret
export GITHUB_WEBHOOK_SECRET=your-secret
export PAGERDUTY_WEBHOOK_SECRET=your-secret

# Optional: Slack notifications
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

**Endpoints:**
- `POST /webhook/<source>` - Receive webhooks from any source
- `POST /analyze` - Trigger RCA analysis
- `GET /events` - View recent webhook events
- `GET /health` - Health check

**Example webhook:**
```bash
curl -X POST http://localhost:5001/webhook/datadog \
  -H "Content-Type: application/json" \
  -H "X-Datadog-Signature: sha256=..." \
  -d '{
    "alert_type": "error",
    "service": "api-gateway",
    "message": "High error rate detected"
  }'
```

---

### 2. AWS CloudWatch Integration (`aws_cloudwatch_example.py`)

Demonstrates fetching and analyzing logs from AWS CloudWatch.

**Features:**
- Basic log fetching
- Advanced filtering (patterns, time ranges)
- RCA integration
- Anomaly detection
- Multi-log group monitoring
- Comprehensive error handling

**Usage:**
```bash
# Run all examples
python aws_cloudwatch_example.py

# Run specific example (1-6)
python aws_cloudwatch_example.py 3
```

**Prerequisites:**
```bash
pip install boto3

# Configure AWS credentials
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=us-east-1
export AWS_LOG_GROUP=/aws/lambda/my-function

# OR use AWS CLI
aws configure
```

**Examples included:**
1. Basic log fetching from CloudWatch
2. Filtered log queries (ERROR only, custom patterns)
3. RCA integration with CloudWatch logs
4. Anomaly detection on error rates
5. Multi-log group monitoring
6. Error handling best practices

---

### 3. Multi-Cloud Integration (`multi_cloud_example.py`)

Demonstrates unified monitoring across AWS, GCP, and Azure.

**Features:**
- Simultaneous log collection from multiple cloud providers
- Unified log normalization
- Cross-cloud incident detection
- Multi-cloud RCA analysis
- Incident correlation across cloud boundaries

**Usage:**
```bash
# Run all examples
python multi_cloud_example.py

# Run specific example (1-2)
python multi_cloud_example.py 1
```

**Prerequisites:**
```bash
pip install boto3 google-cloud-logging azure-monitor-query azure-identity

# AWS
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1
export AWS_LOG_GROUP=/aws/lambda/my-function

# GCP
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export GCP_PROJECT_ID=my-project

# Azure
export AZURE_TENANT_ID=...
export AZURE_CLIENT_ID=...
export AZURE_CLIENT_SECRET=...
export AZURE_WORKSPACE_ID=...
```

**Examples included:**
1. Basic multi-cloud monitoring with unified analysis
2. Cross-cloud incident detection (simulated cascade failure)

**Use Cases:**
- Monitor microservices deployed across multiple clouds
- Detect incidents that span cloud boundaries
- Unified incident response for hybrid cloud architectures

---

### 4. OpenTelemetry Support (`opentelemetry_example.py`)

Demonstrates distributed tracing analysis with OpenTelemetry.

**Features:**
- Trace parsing and analysis
- Critical path detection
- Error propagation tracking
- Service dependency mapping
- Performance bottleneck identification
- OTLP JSON format support

**Usage:**
```bash
# Run all examples
python opentelemetry_example.py

# Run specific example (1-6)
python opentelemetry_example.py 2
```

**No external dependencies** - uses simulated traces for demonstration.

**Examples included:**
1. Basic trace analysis
2. Critical path analysis (slowest execution path)
3. Error propagation detection
4. Service dependency mapping
5. Performance analysis by service
6. Loading OTLP JSON format

**Real-world usage:**
```python
from adapt_rca.integrations import OpenTelemetryAnalyzer, Trace, Span

# Load your OTLP traces
with open('traces.json', 'r') as f:
    otlp_data = json.load(f)

# Convert and analyze
analyzer = OpenTelemetryAnalyzer()
issues = analyzer.analyze_trace(trace)

for issue in issues:
    print(f"{issue['severity']}: {issue['issue']} in {issue['service']}")
```

---

## Quick Start Guide

### 1. Install Dependencies

```bash
# Core dependencies (included with ADAPT-RCA)
pip install adapt-rca

# Optional: Cloud provider SDKs
pip install boto3                    # AWS
pip install google-cloud-logging     # GCP
pip install azure-monitor-query azure-identity  # Azure

# Optional: Web framework for webhooks
pip install flask
```

### 2. Configure Credentials

**AWS:**
```bash
aws configure
# OR
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
```

**GCP:**
```bash
# Create service account in GCP Console
# Download JSON key
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

**Azure:**
```bash
export AZURE_TENANT_ID=...
export AZURE_CLIENT_ID=...
export AZURE_CLIENT_SECRET=...
```

### 3. Run Examples

```bash
# Start with webhook example (no cloud credentials needed)
cd examples/v3_integrations
python webhook_example.py --test

# Try AWS CloudWatch (if configured)
python aws_cloudwatch_example.py 1

# Try multi-cloud (if multiple providers configured)
python multi_cloud_example.py

# Try OpenTelemetry (no credentials needed)
python opentelemetry_example.py
```

---

## Integration Patterns

### Pattern 1: Real-Time Monitoring

```python
from adapt_rca.integrations import WebhookReceiver
from adapt_rca import RCAEngine

receiver = WebhookReceiver(secrets={"source": "secret"})
engine = RCAEngine()

# Receive webhook
event = receiver.receive(source="source", payload=data, ...)

# Convert to RCA event
rca_event = {
    "timestamp": event.received_at.isoformat(),
    "service": event.payload.get("service"),
    "level": "ERROR",
    "message": event.payload.get("message")
}

engine.add_event(rca_event)
result = engine.analyze()
```

### Pattern 2: Cloud Log Analysis

```python
from adapt_rca.integrations import AWSCloudWatchIntegration
from adapt_rca import RCAEngine
from datetime import datetime, timedelta

cw = AWSCloudWatchIntegration(log_group_name="/aws/app")
engine = RCAEngine()

# Fetch logs
start_time = datetime.now() - timedelta(hours=1)
for log_entry in cw.fetch_logs(start_time=start_time):
    engine.add_event({
        "timestamp": log_entry.timestamp.isoformat(),
        "service": log_entry.service,
        "level": log_entry.severity,
        "message": log_entry.message
    })

result = engine.analyze()
```

### Pattern 3: Multi-Cloud Aggregation

```python
from adapt_rca.integrations import (
    AWSCloudWatchIntegration,
    GCPLoggingIntegration,
    AzureMonitorIntegration
)

# Fetch from all clouds
aws_logs = list(aws_integration.fetch_logs(start_time))
gcp_logs = list(gcp_integration.fetch_logs(start_time))
azure_logs = list(azure_integration.fetch_logs(start_time))

# Combine and analyze
all_logs = aws_logs + gcp_logs + azure_logs
all_logs.sort(key=lambda log: log.timestamp)

for log in all_logs:
    engine.add_event(...)
```

### Pattern 4: Trace Analysis

```python
from adapt_rca.integrations import OpenTelemetryAnalyzer

analyzer = OpenTelemetryAnalyzer()

# Analyze trace
issues = analyzer.analyze_trace(trace)

# Check for specific issues
for issue in issues:
    if issue['issue'] == 'slow_span':
        print(f"Bottleneck in {issue['service']}: {issue['details']}")
    elif issue['issue'] == 'error_propagation':
        print(f"Error cascade from {issue['details']}")
```

---

## Best Practices

### Security

1. **Always use HMAC verification for webhooks**
   ```python
   receiver = WebhookReceiver(secrets={"source": os.getenv("WEBHOOK_SECRET")})
   ```

2. **Never hardcode credentials**
   ```python
   # Good
   cw = AWSCloudWatchIntegration(log_group_name="/aws/app")

   # Bad
   cw = AWSCloudWatchIntegration(
       log_group_name="/aws/app",
       aws_access_key_id="AKIA..."  # Don't do this!
   )
   ```

3. **Use environment variables for secrets**
   ```bash
   export WEBHOOK_SECRET=$(openssl rand -hex 32)
   ```

### Performance

1. **Use appropriate time windows**
   ```python
   # Good - specific 1-hour window
   start_time = datetime.now() - timedelta(hours=1)

   # Bad - entire year (expensive!)
   start_time = datetime.now() - timedelta(days=365)
   ```

2. **Filter at source, not locally**
   ```python
   # Good - CloudWatch does filtering
   logs = cw.fetch_logs(start_time=start_time, filter_pattern="ERROR")

   # Bad - fetch everything, filter locally
   all_logs = cw.fetch_logs(start_time=start_time)
   errors = [log for log in all_logs if "ERROR" in log.message]
   ```

3. **Process in batches**
   ```python
   batch = []
   for log_entry in cw.fetch_logs(start_time=start_time):
       batch.append(log_entry)
       if len(batch) >= 100:
           process_batch(batch)
           batch = []
   ```

### Error Handling

```python
from botocore.exceptions import ClientError, NoCredentialsError

try:
    logs = list(cw.fetch_logs(start_time=start_time))
except NoCredentialsError:
    logger.error("AWS credentials not configured")
except ClientError as e:
    if e.response['Error']['Code'] == 'ResourceNotFoundException':
        logger.error(f"Log group not found: {log_group}")
    else:
        logger.error(f"AWS error: {e}")
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
```

---

## Troubleshooting

### Webhook Issues

**Problem:** Signature verification failures

**Solution:**
- Verify webhook secret matches between sender and receiver
- Check signature header name (different sources use different headers)
- Ensure payload is serialized correctly (JSON with sorted keys)

### AWS CloudWatch Issues

**Problem:** `NoCredentialsError`

**Solution:**
```bash
aws configure
# OR
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
```

**Problem:** `ResourceNotFoundException`

**Solution:**
```bash
# List available log groups
aws logs describe-log-groups --region us-east-1
```

### GCP Logging Issues

**Problem:** `PermissionDenied`

**Solution:**
```bash
# Grant required roles
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:SA_EMAIL" \
    --role="roles/logging.viewer"
```

### Azure Monitor Issues

**Problem:** Authentication failures

**Solution:**
- Verify environment variables are set correctly
- Check service principal has required permissions
- Test query in Azure Portal Log Analytics first

---

## Next Steps

1. **Explore V2.0 Features:** Check `docs/V2_FEATURES.md` for alerting and analytics
2. **Read Full Documentation:** See `docs/V3_FEATURES.md` for comprehensive guide
3. **View Roadmap:** Check `ROADMAP_PROGRESS.md` for upcoming features
4. **Production Deployment:** See production best practices in main documentation

---

## Support

- **Documentation:** `docs/V3_FEATURES.md`
- **Troubleshooting:** `docs/TROUBLESHOOTING.md`
- **Architecture:** `docs/architecture.md`
- **Configuration:** `docs/configuration.md`
