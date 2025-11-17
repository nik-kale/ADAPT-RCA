"""
Real-time webhook receiver for streaming event ingestion.

Provides HTTP endpoint for receiving events from external systems,
webhooks, and push-based integrations.
"""
import logging
import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class WebhookEvent:
    """Represents an event received via webhook."""
    event_id: str
    source: str
    payload: Dict[str, Any]
    headers: Dict[str, str]
    received_at: datetime = field(default_factory=datetime.now)
    verified: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class WebhookReceiver:
    """
    Webhook receiver for real-time event ingestion.

    Handles webhook validation, signature verification, and event processing.
    Supports multiple webhook sources with different authentication methods.

    Example:
        >>> receiver = WebhookReceiver()
        >>>
        >>> # Register event handler
        >>> @receiver.on_event("github")
        >>> def handle_github(event):
        ...     print(f"GitHub event: {event.payload['action']}")
        >>>
        >>> # Process webhook
        >>> event = receiver.receive(
        ...     source="github",
        ...     payload=request.json,
        ...     headers=request.headers,
        ...     signature=request.headers.get("X-Hub-Signature-256")
        ... )
    """

    def __init__(self):
        """Initialize webhook receiver."""
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._secrets: Dict[str, str] = {}
        self._event_history: List[WebhookEvent] = []
        self._max_history = 1000

    def register_secret(self, source: str, secret: str) -> None:
        """
        Register webhook secret for signature verification.

        Args:
            source: Webhook source identifier
            secret: Shared secret for HMAC verification
        """
        self._secrets[source] = secret
        logger.info(f"Registered webhook secret for: {source}")

    def on_event(self, source: str):
        """
        Decorator to register event handler.

        Args:
            source: Webhook source to handle

        Example:
            >>> @receiver.on_event("slack")
            >>> def handle_slack_event(event):
            ...     process_slack(event.payload)
        """
        def decorator(func: Callable):
            self._handlers[source].append(func)
            logger.debug(f"Registered handler for {source}: {func.__name__}")
            return func
        return decorator

    def receive(
        self,
        source: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        signature: Optional[str] = None
    ) -> WebhookEvent:
        """
        Process incoming webhook.

        Args:
            source: Webhook source identifier
            payload: Webhook payload data
            headers: HTTP headers
            signature: Optional signature for verification

        Returns:
            WebhookEvent object

        Raises:
            ValueError: If signature verification fails
        """
        # Generate event ID
        event_id = self._generate_event_id(source, payload)

        # Create event
        event = WebhookEvent(
            event_id=event_id,
            source=source,
            payload=payload,
            headers=headers
        )

        # Verify signature if secret is configured
        if source in self._secrets:
            if not signature:
                raise ValueError(f"Signature required for {source}")

            if not self._verify_signature(source, payload, signature):
                raise ValueError(f"Invalid signature for {source}")

            event.verified = True

        # Add to history
        self._add_to_history(event)

        # Call handlers
        if source in self._handlers:
            for handler in self._handlers[source]:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Handler error for {source}: {e}")

        logger.info(f"Processed webhook from {source}: {event_id}")
        return event

    def _generate_event_id(self, source: str, payload: Dict[str, Any]) -> str:
        """Generate unique event ID."""
        import json
        payload_str = json.dumps(payload, sort_keys=True)
        timestamp = datetime.now().isoformat()
        combined = f"{source}:{timestamp}:{payload_str}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _verify_signature(
        self,
        source: str,
        payload: Dict[str, Any],
        signature: str
    ) -> bool:
        """
        Verify webhook signature using HMAC.

        Args:
            source: Webhook source
            payload: Payload data
            signature: Signature to verify

        Returns:
            True if signature is valid
        """
        import json

        secret = self._secrets.get(source)
        if not secret:
            return False

        # Compute expected signature
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        expected = hmac.new(
            secret.encode(),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

        # Handle different signature formats
        # GitHub: "sha256=<signature>"
        if signature.startswith("sha256="):
            signature = signature[7:]

        # Constant-time comparison
        return hmac.compare_digest(expected, signature)

    def _add_to_history(self, event: WebhookEvent) -> None:
        """Add event to history with size limit."""
        self._event_history.append(event)

        if len(self._event_history) > self._max_history:
            # Remove oldest 10%
            remove_count = self._max_history // 10
            self._event_history = self._event_history[remove_count:]

    def get_history(
        self,
        source: Optional[str] = None,
        limit: int = 100
    ) -> List[WebhookEvent]:
        """
        Get webhook event history.

        Args:
            source: Optional source filter
            limit: Maximum number of events to return

        Returns:
            List of webhook events
        """
        events = self._event_history

        if source:
            events = [e for e in events if e.source == source]

        return sorted(events, key=lambda e: e.received_at, reverse=True)[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get webhook statistics.

        Returns:
            Dictionary with webhook stats
        """
        source_counts = defaultdict(int)
        verified_count = 0

        for event in self._event_history:
            source_counts[event.source] += 1
            if event.verified:
                verified_count += 1

        return {
            "total_events": len(self._event_history),
            "verified_events": verified_count,
            "by_source": dict(source_counts),
            "registered_sources": list(self._secrets.keys())
        }


# Flask integration helper
def create_webhook_app(receiver: WebhookReceiver, secret_key: str = None):
    """
    Create Flask app with webhook endpoints.

    Args:
        receiver: WebhookReceiver instance
        secret_key: Optional Flask secret key

    Returns:
        Flask app with webhook routes
    """
    try:
        from flask import Flask, request, jsonify
    except ImportError:
        raise ImportError("Flask required for webhook app. Install with: pip install flask")

    app = Flask(__name__)
    if secret_key:
        app.config['SECRET_KEY'] = secret_key

    @app.route('/webhook/<source>', methods=['POST'])
    def handle_webhook(source):
        """Handle incoming webhook."""
        try:
            payload = request.get_json()
            headers = dict(request.headers)

            # Get signature from various header names
            signature = (
                headers.get('X-Hub-Signature-256') or  # GitHub
                headers.get('X-Slack-Signature') or  # Slack
                headers.get('X-Webhook-Signature')  # Generic
            )

            event = receiver.receive(
                source=source,
                payload=payload,
                headers=headers,
                signature=signature
            )

            return jsonify({
                'status': 'success',
                'event_id': event.event_id,
                'verified': event.verified
            }), 200

        except ValueError as e:
            logger.warning(f"Webhook validation failed: {e}")
            return jsonify({'error': str(e)}), 401

        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return jsonify({'error': 'Internal server error'}), 500

    @app.route('/webhook/stats', methods=['GET'])
    def get_stats():
        """Get webhook statistics."""
        return jsonify(receiver.get_stats())

    @app.route('/webhook/history/<source>', methods=['GET'])
    def get_history(source):
        """Get webhook history for source."""
        limit = request.args.get('limit', 100, type=int)
        events = receiver.get_history(source=source, limit=limit)

        return jsonify({
            'source': source,
            'count': len(events),
            'events': [
                {
                    'event_id': e.event_id,
                    'received_at': e.received_at.isoformat(),
                    'verified': e.verified
                }
                for e in events
            ]
        })

    @app.route('/health', methods=['GET'])
    def health():
        """Health check."""
        return jsonify({'status': 'ok'})

    return app
