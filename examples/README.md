# ADAPT-RCA Examples

This directory contains comprehensive examples demonstrating all features of ADAPT-RCA across all versions (V1.0-V4.0).

---

## 📁 Directory Structure

```
examples/
├── basic_logs/              # V1.0: Core RCA examples
│   └── sample_logs.jsonl
├── data/                    # Sample log files
│   ├── sample_csv.csv
│   ├── sample_syslog.log
│   └── sample_multi_service.jsonl
├── scripts/                 # V1.0: Example scripts
│   ├── analyze_csv.py
│   ├── analyze_with_llm.py
│   └── visualize_graph.py
├── v3_integrations/         # V3.0: Real-time & cloud examples
│   ├── webhook_example.py
│   ├── aws_cloudwatch_example.py
│   ├── multi_cloud_example.py
│   ├── opentelemetry_example.py
│   └── README.md
├── config_demo.py           # Configuration examples
└── README.md                # This file
```

---

## 🚀 Quick Start by Version

### V1.0 - Core RCA Analysis

#### Basic CSV Analysis
```bash
python examples/scripts/analyze_csv.py
```

**Features:**
- Root cause analysis
- Causal graph generation
- Multiple export formats (JSON, Markdown, Mermaid)

#### LLM-Powered Analysis
```bash
export OPENAI_API_KEY="your-api-key"
python examples/scripts/analyze_with_llm.py
```

**Features:**
- AI-powered reasoning with GPT-4/Claude
- Token usage tracking
- Comparative analysis (LLM vs heuristic)

### V2.0 - Analytics & Alerting

#### Anomaly Detection
```python
from adapt_rca.analytics import AnomalyDetector, MetricsTracker

# Statistical anomaly detection
detector = AnomalyDetector()
tracker = MetricsTracker()

# Track metrics
tracker.record("error_rate", 0.15, tags={"service": "api"})

# Detect anomalies (Z-score, IQR, Moving Average)
result = detector.detect_error_rate_anomaly(
    current_rate=0.15,
    historical_rates=[0.01, 0.02, 0.01, 0.015]
)

if result.is_anomaly:
    print(f"Anomaly detected! Confidence: {result.confidence:.1%}")
```

#### Multi-Channel Alerting
```python
from adapt_rca.alerting import AlertManager, Alert, AlertSeverity
from adapt_rca.alerting import SlackNotifier, EmailNotifier

# Configure alerting
manager = AlertManager()
manager.add_notifier(SlackNotifier(webhook_url="https://hooks.slack.com/..."))
manager.add_notifier(EmailNotifier(smtp_server="smtp.gmail.com"))

# Send alert
alert = Alert(
    title="High error rate detected",
    severity=AlertSeverity.HIGH,
    description="API error rate exceeded 10%",
    tags={"service": "api-gateway"}
)

manager.send_alert(alert)
```

#### Incident Storage
```python
from adapt_rca.storage import IncidentStore

store = IncidentStore()

# Store incident
store.store_incident(
    incident_id="inc-123",
    created_at=datetime.now(),
    severity="high",
    affected_services=["api-gateway"],
    root_causes=[...],
    recommended_actions=[...]
)

# Query incidents
incidents = store.search_incidents(
    start_time=datetime.now() - timedelta(days=7),
    severity="high"
)

# Get statistics
stats = store.get_incident_stats(days=30)
```

### V3.0 - Real-Time & Cloud Integration

See **[v3_integrations/README.md](v3_integrations/README.md)** for detailed documentation.

#### Real-Time Webhook Ingestion
```bash
# Start webhook receiver
python examples/v3_integrations/webhook_example.py

# Test mode (sends sample webhooks)
python examples/v3_integrations/webhook_example.py --test
```

**Features:**
- HMAC-verified webhooks from Datadog, GitHub, PagerDuty
- Real-time RCA analysis
- Flask web server with endpoints

#### AWS CloudWatch Integration
```bash
# Run all AWS examples
python examples/v3_integrations/aws_cloudwatch_example.py

# Run specific example (1-6)
python examples/v3_integrations/aws_cloudwatch_example.py 3
```

**Examples:**
1. Basic log fetching
2. Filtered log queries
3. RCA integration
4. Anomaly detection on CloudWatch logs
5. Multi-log group monitoring
6. Error handling best practices

#### Multi-Cloud Monitoring
```bash
# Unified AWS + GCP + Azure monitoring
python examples/v3_integrations/multi_cloud_example.py
```

**Features:**
- Simultaneous log collection from all clouds
- Cross-cloud incident detection
- Normalized log processing

#### OpenTelemetry Distributed Tracing
```bash
# Analyze distributed traces
python examples/v3_integrations/opentelemetry_example.py

# Run specific example
python examples/v3_integrations/opentelemetry_example.py 2
```

**Examples:**
1. Basic trace analysis
2. Critical path detection
3. Error propagation tracking
4. Service dependency mapping
5. Performance bottleneck identification
6. OTLP JSON format loading

### V4.0 - ML & Automated Remediation

#### ML-Based Anomaly Detection

**Isolation Forest (Multivariate Anomalies):**
```python
from adapt_rca.ml import IsolationForestDetector, MLModelManager

# Train detector
detector = IsolationForestDetector(contamination=0.1)

historical_metrics = [
    {"error_rate": 0.01, "latency_p95": 150, "cpu_usage": 45},
    {"error_rate": 0.02, "latency_p95": 160, "cpu_usage": 50},
    # ... 100+ samples for good training
]

detector.train(
    data=historical_metrics,
    features=["error_rate", "latency_p95", "cpu_usage"]
)

# Detect anomalies
current_metrics = {"error_rate": 0.15, "latency_p95": 500, "cpu_usage": 90}
result = detector.detect(current_metrics)

if result.is_anomaly:
    print(f"Anomaly detected!")
    print(f"  Score: {result.score:.3f}")
    print(f"  Confidence: {result.confidence:.1%}")
    print(f"  Features: {result.feature_values}")

# Save model
detector.save("models/api-anomaly.pkl")

# Load later
detector2 = IsolationForestDetector()
detector2.load("models/api-anomaly.pkl")
```

**LSTM Time-Series (Temporal Anomalies):**
```python
from adapt_rca.ml import LSTMTimeSeriesDetector

# Train LSTM autoencoder
detector = LSTMTimeSeriesDetector(sequence_length=24)

# Historical hourly error rates (need 100+ hours for training)
historical_error_rates = [0.01, 0.02, 0.015, ...]  # 1000+ points

detector.train(
    data=historical_error_rates,
    epochs=50,
    batch_size=32
)

# Detect anomalies in new sequence
recent_24_hours = [0.01, 0.02, 0.15, 0.20, ...]  # 24 points
result = detector.detect(recent_24_hours)

if result.is_anomaly:
    print(f"Time-series anomaly!")
    print(f"  Reconstruction error: {result.reconstruction_error:.4f}")
    print(f"  Threshold: {result.threshold:.4f}")

# Online detection (streaming mode)
result = detector.detect_online(
    new_value=0.15,
    historical_sequence=recent_data[-23:]  # Last 23 values
)

# Save model (saves to directory with model.h5 + metadata)
detector.save("models/lstm-detector")
```

**Model Management:**
```python
from adapt_rca.ml import MLModelManager

manager = MLModelManager(models_dir="models/")

# Register model
metadata = manager.register_model(
    name="api-anomaly-v1",
    model=detector,
    metadata={"service": "api-gateway", "features": ["error_rate", "latency"]}
)

# Load model
detector = manager.load_model("api-anomaly-v1")

# List all models
models = manager.list_models()

# Get model info
versions = manager.get_model_info("api-anomaly-v1")

# Update performance metrics
manager.update_performance_metrics(
    "api-anomaly-v1",
    {"precision": 0.92, "recall": 0.88, "f1": 0.90}
)

# Get statistics
stats = manager.get_summary()
print(f"Total models: {stats['total_models']}")
print(f"By type: {stats['models_by_type']}")
```

#### Automated Remediation

**Define Runbooks:**
```python
from adapt_rca.remediation import (
    RemediationEngine,
    Runbook,
    RunbookStep,
    RunbookCondition,
    RestartServiceAction,
    ScaleServiceAction,
    RollbackDeploymentAction
)

# Create runbook for high error rate
runbook = Runbook(
    name="high-error-rate-remediation",
    description="Restart service when error rate is high",
    require_approval=False  # Set True for production
)

# Add trigger condition
runbook.add_condition(
    field="error_rate",
    operator=">",
    value=0.1,
    description="Error rate above 10%"
)

# Add remediation steps
runbook.add_step(RunbookStep(
    name="restart-service",
    action=RestartServiceAction(
        service_name="api-gateway",
        platform="kubernetes",
        namespace="production"
    ),
    timeout=120,
    retry_count=2,
    retry_delay=10
))

runbook.add_step(RunbookStep(
    name="scale-up",
    action=ScaleServiceAction(
        service_name="api-gateway",
        target_replicas=10,
        platform="kubernetes"
    ),
    conditions=[
        RunbookCondition(
            field="cpu_usage",
            operator=">",
            value=80
        )
    ]
))
```

**Execute Remediation:**
```python
# Initialize engine
engine = RemediationEngine(
    dry_run=False,  # Set True for testing
    enable_rollback=True
)

# Register runbooks
engine.register_runbook(runbook)

# Manual execution
incident_context = {
    "service": "api-gateway",
    "error_rate": 0.15,
    "cpu_usage": 85,
    "severity": "high"
}

result = engine.remediate(
    incident_context=incident_context,
    auto_approve=True  # Set False to require approval
)

# Check result
if result.status == ExecutionStatus.SUCCESS:
    print("Remediation successful!")
    print(f"  Steps executed: {len(result.steps_executed)}")
    print(f"  Duration: {result.total_duration_seconds:.2f}s")
elif result.status == ExecutionStatus.PENDING_APPROVAL:
    print("Remediation pending approval")
    # Later: engine.approve_remediation(result.execution_id)
elif result.status == ExecutionStatus.ROLLED_BACK:
    print("Remediation failed and was rolled back")

# View history
history = engine.get_execution_history(limit=10)
for exec_result in history:
    print(f"{exec_result.execution_id}: {exec_result.status.value}")

# Get statistics
stats = engine.get_statistics()
print(f"Success rate: {stats['success_rate']:.1%}")
print(f"Average duration: {stats['avg_duration_seconds']:.2f}s")
```

**Available Actions:**
1. **RestartServiceAction** - Restart Docker/Kubernetes/Systemd services
2. **ScaleServiceAction** - Scale replicas (Kubernetes, Docker Swarm)
3. **RollbackDeploymentAction** - Rollback to previous deployment
4. **RunCommandAction** - Execute custom shell commands
5. **WebhookAction** - Call external APIs for remediation

**Safety Features:**
- Dry-run mode for testing
- Approval workflows for sensitive actions
- Automatic rollback on failure
- Retry logic with exponential backoff
- Complete execution history and auditing

---

## 📚 Sample Data Descriptions

### basic_logs/sample_logs.jsonl
Simple multi-service incident for basic RCA testing:
- Services: api-gateway, user-service, postgres
- Issue: Database connection pool exhaustion
- Duration: ~5 seconds

### data/sample_csv.csv
Database connection pool exhaustion (CSV format):
- **Root cause:** Database connection limit reached
- **Impact:** API gateway timeouts, frontend errors
- **Duration:** ~40 seconds
- **Services:** database, api-gateway, web-frontend, cache-service

### data/sample_syslog.log
Same incident as CSV but in syslog format - demonstrates format flexibility.

### data/sample_multi_service.jsonl
Complex e-commerce system with cascading failures:
- **Root cause:** Payment service database deadlock
- **Impact:** Order processing, inventory, notifications
- **Services affected:** 10+ microservices
- **Demonstrates:**
  - Temporal causality detection
  - Circuit breaker patterns
  - Service dependency chains

---

## 🔧 Configuration Examples

### Environment Variables
```bash
# LLM Configuration
export OPENAI_API_KEY=your-key
export ANTHROPIC_API_KEY=your-key
export GEMINI_API_KEY=your-key

# V1.5: Security
export ADAPT_RCA_API_KEY_HASH=<hashed-key>

# V2.0: Alerting
export SLACK_WEBHOOK_URL=https://hooks.slack.com/...
export SMTP_SERVER=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=your@email.com
export SMTP_PASSWORD=your-password

# V3.0: Cloud Integrations
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
export AZURE_TENANT_ID=...
export AZURE_CLIENT_ID=...
export AZURE_CLIENT_SECRET=...

# V3.0: Webhook Security
export DATADOG_WEBHOOK_SECRET=your-secret
export GITHUB_WEBHOOK_SECRET=your-secret
export PAGERDUTY_WEBHOOK_SECRET=your-secret

# Processing Limits
export ADAPT_RCA_MAX_EVENTS=5000
export ADAPT_RCA_MAX_FILE_SIZE_MB=100
export ADAPT_RCA_TIME_WINDOW=15
```

### Python Configuration
```python
from adapt_rca.config import RCAConfig

config = RCAConfig()
config.max_events = 10000
config.time_window_minutes = 30
config.llm_timeout = 60
config.validate()
```

---

## 🎯 End-to-End Workflows

### Workflow 1: Real-Time Incident Detection & Auto-Remediation
```python
from adapt_rca.integrations import WebhookReceiver
from adapt_rca import RCAEngine
from adapt_rca.remediation import RemediationEngine
from adapt_rca.alerting import AlertManager, SlackNotifier

# 1. Set up webhook receiver
webhook_receiver = WebhookReceiver(secrets={"datadog": "secret"})

# 2. Set up RCA engine
rca_engine = RCAEngine()

# 3. Set up alerting
alert_manager = AlertManager()
alert_manager.add_notifier(SlackNotifier(webhook_url=slack_url))

# 4. Set up remediation
remediation_engine = RemediationEngine()
remediation_engine.register_runbook(high_error_rate_runbook)

# 5. Process incoming webhooks
def process_webhook(request):
    # Receive webhook
    event = webhook_receiver.receive(
        source="datadog",
        payload=request.json,
        headers=request.headers,
        signature=request.headers.get("X-Datadog-Signature")
    )

    # Add to RCA engine
    rca_engine.add_event({
        "timestamp": event.received_at.isoformat(),
        "service": event.payload.get("service"),
        "level": "ERROR",
        "message": event.payload.get("message")
    })

    # Run RCA
    result = rca_engine.analyze()

    # Send alert
    for root_cause in result.root_causes:
        alert_manager.send_alert(Alert(
            title=f"Root cause: {root_cause['service']}",
            severity=AlertSeverity.HIGH,
            description=root_cause['reason']
        ))

    # Auto-remediate
    incident_context = {
        "service": event.payload.get("service"),
        "error_rate": event.payload.get("error_rate")
    }
    remediation_result = remediation_engine.remediate(
        incident_context,
        auto_approve=True
    )
```

### Workflow 2: ML-Based Proactive Monitoring
```python
from adapt_rca.ml import IsolationForestDetector
from adapt_rca.analytics import MetricsTracker
from adapt_rca.alerting import AlertManager

# 1. Train ML model on historical data
detector = IsolationForestDetector()
detector.train(historical_metrics, features=["error_rate", "latency", "cpu"])

# 2. Set up real-time tracking
tracker = MetricsTracker()
alert_manager = AlertManager()

# 3. Monitor in real-time
import time
while True:
    # Collect current metrics
    current_metrics = {
        "error_rate": tracker.get_current("error_rate"),
        "latency": tracker.get_percentile("latency_ms", 95),
        "cpu": get_cpu_usage()
    }

    # Detect anomalies with ML
    result = detector.detect(current_metrics)

    if result.is_anomaly:
        # Trigger RCA analysis
        rca_result = rca_engine.analyze()

        # Alert team
        alert_manager.send_alert(Alert(
            title="ML-Detected Anomaly",
            severity=AlertSeverity.WARNING,
            description=f"Anomaly score: {result.score:.3f}"
        ))

    time.sleep(60)  # Check every minute
```

### Workflow 3: Multi-Cloud Unified Monitoring
```python
from adapt_rca.integrations import (
    AWSCloudWatchIntegration,
    GCPLoggingIntegration,
    AzureMonitorIntegration
)

# 1. Configure all cloud providers
aws = AWSCloudWatchIntegration(log_group="/aws/lambda/app")
gcp = GCPLoggingIntegration(project_id="my-project", log_filter='severity>=ERROR')
azure = AzureMonitorIntegration(workspace_id="workspace", query="AppExceptions")

# 2. Fetch logs from all clouds
from datetime import datetime, timedelta
start_time = datetime.now() - timedelta(hours=1)

aws_logs = list(aws.fetch_logs(start_time=start_time))
gcp_logs = list(gcp.fetch_logs(start_time=start_time))
azure_logs = list(azure.fetch_logs(start_time=start_time))

# 3. Unified analysis
all_logs = aws_logs + gcp_logs + azure_logs
all_logs.sort(key=lambda log: log.timestamp)

# 4. RCA across all clouds
for log in all_logs:
    rca_engine.add_event({
        "timestamp": log.timestamp.isoformat(),
        "service": log.service,
        "level": log.severity,
        "message": log.message,
        "cloud": log.metadata.get("source")
    })

result = rca_engine.analyze()

# Identify cross-cloud issues
print("Cross-cloud incident analysis:")
print(f"Root causes: {result.root_causes}")
print(f"Affected clouds: {set(log.metadata.get('source') for log in all_logs)}")
```

---

## 🧪 Testing Examples

### Run Unit Tests
```bash
pytest tests/ -v
```

### Test with Sample Data
```bash
# Test all examples
python examples/scripts/analyze_csv.py
python examples/v3_integrations/webhook_example.py --test
python examples/v3_integrations/opentelemetry_example.py
```

### Dry-Run Remediation
```python
# Test remediation without actually executing
engine = RemediationEngine(dry_run=True)
engine.register_runbook(runbook)

result = engine.remediate(incident_context, auto_approve=True)
# Will log "[DRY RUN]" messages instead of executing
```

---

## 📖 Further Reading

### Core Documentation
- [Main README](../README.md) - Project overview and getting started
- [Architecture Guide](../docs/architecture.md) - System design deep dive
- [Configuration](../docs/configuration.md) - All configuration options

### Feature Documentation
- [V2.0 Features](../docs/V2_FEATURES.md) - Analytics and alerting
- [V3.0 Features](../docs/V3_FEATURES.md) - Cloud integrations and real-time
- [V3.0 Integration Examples](v3_integrations/README.md) - Detailed V3.0 examples

### Development
- [Roadmap](../ROADMAP_PROGRESS.md) - Development progress and plans
- [Contributing](../CONTRIBUTING.md) - How to contribute
- [Troubleshooting](../docs/TROUBLESHOOTING.md) - Common issues

---

## 💡 Pro Tips

1. **Start Small**: Begin with basic examples and gradually explore advanced features

2. **Use Dry-Run**: Always test remediation with `dry_run=True` before production

3. **Train ML Models Well**: Need 100+ samples for Isolation Forest, 1000+ for LSTM

4. **Monitor ML Performance**: Track precision/recall and retrain periodically

5. **Cloud Cost Control**: Use time windows and filters to limit API calls

6. **Security First**: Always use HMAC verification for webhooks

7. **Alert Correlation**: Use correlation rules to reduce alert noise by 50-85%

8. **Approval Workflows**: Require approval for destructive remediation actions

9. **Version Your Models**: Use MLModelManager to track model versions

10. **Test Rollbacks**: Verify rollback actions work before enabling auto-remediation

---

## ❓ Questions or Issues?

- **GitHub Issues**: https://github.com/your-org/ADAPT-RCA/issues
- **Discussions**: https://github.com/your-org/ADAPT-RCA/discussions
- **Documentation**: [docs/](../docs/)
- **Examples**: You're here! 📍

---

## 🎯 Quick Reference

| Feature | Version | Example Location |
|---------|---------|------------------|
| Basic RCA | V1.0 | `scripts/analyze_csv.py` |
| LLM Analysis | V1.0 | `scripts/analyze_with_llm.py` |
| Graph Visualization | V1.0 | `scripts/visualize_graph.py` |
| Statistical Anomaly Detection | V2.0 | See code examples above |
| Multi-Channel Alerting | V2.0 | See code examples above |
| Incident Storage | V2.0 | See code examples above |
| Webhook Ingestion | V3.0 | `v3_integrations/webhook_example.py` |
| AWS CloudWatch | V3.0 | `v3_integrations/aws_cloudwatch_example.py` |
| Multi-Cloud | V3.0 | `v3_integrations/multi_cloud_example.py` |
| OpenTelemetry | V3.0 | `v3_integrations/opentelemetry_example.py` |
| Isolation Forest ML | V4.0 | See code examples above |
| LSTM Time-Series | V4.0 | See code examples above |
| Automated Remediation | V4.0 | See code examples above |

---

<div align="center">

**Explore, Learn, Build! 🚀**

[Back to Main README](../README.md) • [View Documentation](../docs/) • [See Roadmap](../ROADMAP_PROGRESS.md)

</div>
