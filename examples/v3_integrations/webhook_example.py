#!/usr/bin/env python3
"""
Webhook Receiver Example for ADAPT-RCA

This example demonstrates how to:
1. Set up a webhook receiver with HMAC verification
2. Receive webhooks from multiple sources
3. Process events and integrate with RCA analysis
4. Create a simple Flask endpoint for webhooks

Usage:
    python webhook_example.py

Then send test webhooks:
    curl -X POST http://localhost:5001/webhook/datadog \
        -H "Content-Type: application/json" \
        -H "X-Datadog-Signature: sha256=..." \
        -d '{"alert_type": "error", "service": "api", "message": "High error rate"}'
"""

import os
import json
import hmac
import hashlib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

from adapt_rca.integrations import WebhookReceiver
from adapt_rca import RCAEngine
from adapt_rca.alerting import AlertManager, Alert, AlertSeverity, SlackNotifier

# Configuration
WEBHOOK_SECRETS = {
    "datadog": os.getenv("DATADOG_WEBHOOK_SECRET", "test-secret-datadog"),
    "github": os.getenv("GITHUB_WEBHOOK_SECRET", "test-secret-github"),
    "pagerduty": os.getenv("PAGERDUTY_WEBHOOK_SECRET", "test-secret-pd"),
}

# Initialize components
webhook_receiver = WebhookReceiver(secrets=WEBHOOK_SECRETS)
rca_engine = RCAEngine()
alert_manager = AlertManager()

# Optional: Configure Slack notifications
if os.getenv("SLACK_WEBHOOK_URL"):
    slack_notifier = SlackNotifier(webhook_url=os.getenv("SLACK_WEBHOOK_URL"))
    alert_manager.add_notifier(slack_notifier)

# Flask app for webhook endpoints
app = Flask(__name__)


@app.route('/webhook/<source>', methods=['POST'])
def receive_webhook(source):
    """
    Generic webhook endpoint for any source.

    Security: Validates HMAC signature if secret is configured.
    """
    try:
        # Get payload
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "Invalid JSON payload"}), 400

        # Get signature from headers (different sources use different headers)
        signature = None
        if source == "github":
            signature = request.headers.get("X-Hub-Signature-256", "").replace("sha256=", "")
        elif source == "datadog":
            signature = request.headers.get("X-Datadog-Signature", "").replace("sha256=", "")
        elif source == "pagerduty":
            signature = request.headers.get("X-PagerDuty-Signature", "")

        # Receive and verify webhook
        event = webhook_receiver.receive(
            source=source,
            payload=payload,
            headers=dict(request.headers),
            signature=signature
        )

        # Process event based on source
        process_webhook_event(source, event)

        return jsonify({
            "status": "success",
            "event_id": event.event_id,
            "source": event.source,
            "received_at": event.received_at.isoformat()
        }), 200

    except ValueError as e:
        # Invalid signature or validation error
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        # Other errors
        return jsonify({"error": f"Internal error: {str(e)}"}), 500


def process_webhook_event(source: str, event):
    """Process webhook event and integrate with RCA."""

    # Convert webhook to RCA event format
    rca_event = None

    if source == "datadog":
        # Datadog alert format
        rca_event = {
            "timestamp": datetime.now().isoformat(),
            "service": event.payload.get("service", "unknown"),
            "level": event.payload.get("alert_type", "INFO").upper(),
            "message": event.payload.get("message", ""),
            "metadata": {
                "source": "datadog",
                "event_id": event.event_id,
                "metric": event.payload.get("metric"),
                "value": event.payload.get("value")
            }
        }

    elif source == "github":
        # GitHub webhook (e.g., deployment, issue)
        action = event.payload.get("action", "")
        if action in ["deployment_failure", "deployment_status"]:
            rca_event = {
                "timestamp": datetime.now().isoformat(),
                "service": event.payload.get("repository", {}).get("name", "unknown"),
                "level": "ERROR" if "failure" in action else "INFO",
                "message": f"GitHub deployment {action}",
                "metadata": {
                    "source": "github",
                    "event_id": event.event_id,
                    "repository": event.payload.get("repository", {}).get("full_name")
                }
            }

    elif source == "pagerduty":
        # PagerDuty incident webhook
        messages = event.payload.get("messages", [])
        if messages:
            msg = messages[0]
            incident = msg.get("incident", {})
            rca_event = {
                "timestamp": datetime.now().isoformat(),
                "service": incident.get("service", {}).get("name", "unknown"),
                "level": "CRITICAL" if incident.get("urgency") == "high" else "WARNING",
                "message": incident.get("title", "PagerDuty incident"),
                "metadata": {
                    "source": "pagerduty",
                    "event_id": event.event_id,
                    "incident_key": incident.get("incident_key"),
                    "urgency": incident.get("urgency")
                }
            }

    # Add to RCA engine if we created an event
    if rca_event:
        rca_engine.add_event(rca_event)
        print(f"[{source}] Added event to RCA engine: {rca_event['message']}")

        # If it's an error/critical event, trigger immediate alert
        if rca_event["level"] in ["ERROR", "CRITICAL"]:
            alert = Alert(
                title=f"[{source.upper()}] {rca_event['message']}",
                severity=AlertSeverity.HIGH if rca_event["level"] == "ERROR" else AlertSeverity.CRITICAL,
                description=f"Webhook received from {source} indicating an issue with {rca_event['service']}",
                tags={"source": source, "service": rca_event["service"]}
            )
            alert_manager.send_alert(alert)


@app.route('/analyze', methods=['POST'])
def run_analysis():
    """
    Endpoint to trigger RCA analysis on collected events.

    Returns root causes and recommended actions.
    """
    try:
        # Run RCA analysis
        result = rca_engine.analyze()

        # Send alerts for root causes
        for root_cause in result.root_causes:
            alert = Alert(
                title=f"Root Cause Identified: {root_cause.get('service')}",
                severity=AlertSeverity.HIGH,
                description=root_cause.get("reason", "Unknown reason"),
                tags={"source": "rca-analysis", "service": root_cause.get("service")}
            )
            alert_manager.send_alert(alert)

        return jsonify({
            "status": "success",
            "root_causes": result.root_causes,
            "recommendations": result.recommendations,
            "graph_summary": {
                "nodes": len(result.causal_graph.get_nodes()) if result.causal_graph else 0,
                "edges": len(result.causal_graph.get_edges()) if result.causal_graph else 0
            }
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/events', methods=['GET'])
def get_events():
    """Get recent webhook events."""
    source = request.args.get('source')
    limit = int(request.args.get('limit', 50))

    events = webhook_receiver.get_events(source=source, limit=limit)

    return jsonify({
        "count": len(events),
        "events": [
            {
                "event_id": e.event_id,
                "source": e.source,
                "event_type": e.event_type,
                "received_at": e.received_at.isoformat(),
                "payload": e.payload
            }
            for e in events
        ]
    }), 200


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "webhook_sources": list(WEBHOOK_SECRETS.keys()),
        "events_stored": len(webhook_receiver.get_events()),
        "rca_engine_ready": True
    }), 200


def generate_test_signature(payload: dict, secret: str) -> str:
    """Generate HMAC signature for testing."""
    payload_bytes = json.dumps(payload, sort_keys=True).encode()
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


def send_test_webhooks():
    """Send test webhooks for demonstration."""
    import requests

    base_url = "http://localhost:5001"

    # Test Datadog webhook
    datadog_payload = {
        "alert_type": "error",
        "service": "api-gateway",
        "message": "High error rate detected: 15% of requests failing",
        "metric": "error_rate",
        "value": 0.15
    }
    datadog_sig = generate_test_signature(datadog_payload, WEBHOOK_SECRETS["datadog"])

    print("\n📨 Sending test Datadog webhook...")
    response = requests.post(
        f"{base_url}/webhook/datadog",
        json=datadog_payload,
        headers={"X-Datadog-Signature": f"sha256={datadog_sig}"}
    )
    print(f"Response: {response.status_code} - {response.json()}")

    # Test GitHub webhook
    github_payload = {
        "action": "deployment_failure",
        "repository": {"name": "backend-service", "full_name": "myorg/backend-service"},
        "deployment": {"environment": "production"}
    }
    github_sig = generate_test_signature(github_payload, WEBHOOK_SECRETS["github"])

    print("\n📨 Sending test GitHub webhook...")
    response = requests.post(
        f"{base_url}/webhook/github",
        json=github_payload,
        headers={"X-Hub-Signature-256": f"sha256={github_sig}"}
    )
    print(f"Response: {response.status_code} - {response.json()}")

    # Run analysis
    print("\n🔍 Running RCA analysis...")
    response = requests.post(f"{base_url}/analyze")
    print(f"Analysis result: {response.json()}")


if __name__ == "__main__":
    import sys

    print("🚀 Starting ADAPT-RCA Webhook Receiver")
    print(f"📡 Configured sources: {', '.join(WEBHOOK_SECRETS.keys())}")
    print(f"🔐 HMAC verification: {'enabled' if WEBHOOK_SECRETS else 'disabled'}")
    print()

    if "--test" in sys.argv:
        # Run test mode: start server in background and send test webhooks
        import threading
        import time

        # Start server in background thread
        server_thread = threading.Thread(
            target=lambda: app.run(host="0.0.0.0", port=5001, debug=False)
        )
        server_thread.daemon = True
        server_thread.start()

        # Wait for server to start
        time.sleep(2)

        # Send test webhooks
        send_test_webhooks()

    else:
        # Normal mode: just run the server
        print("Listening on http://0.0.0.0:5001")
        print()
        print("Endpoints:")
        print("  POST /webhook/<source> - Receive webhooks")
        print("  POST /analyze - Run RCA analysis")
        print("  GET /events - Get recent events")
        print("  GET /health - Health check")
        print()
        app.run(host="0.0.0.0", port=5001, debug=True)
