"""
Notification channels for ADAPT-RCA alerts.

Supports multiple notification channels including Slack, Email, Webhooks,
and console output. Designed to be extensible for additional channels.
"""
import logging
import json
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class Notifier(ABC):
    """Abstract base class for alert notifiers."""

    @abstractmethod
    def notify(self, alert: Any) -> bool:
        """
        Send alert notification.

        Args:
            alert: Alert object to send

        Returns:
            True if notification sent successfully
        """
        pass


class ConsoleNotifier(Notifier):
    """
    Console/stdout notifier for development and testing.

    Simple notifier that prints alerts to console with color coding.
    """

    # ANSI color codes
    COLORS = {
        "critical": "\033[91m",  # Red
        "high": "\033[93m",  # Yellow
        "medium": "\033[94m",  # Blue
        "low": "\033[92m",  # Green
        "info": "\033[96m",  # Cyan
        "reset": "\033[0m"  # Reset
    }

    def __init__(self, use_colors: bool = True):
        """
        Initialize console notifier.

        Args:
            use_colors: Whether to use ANSI colors
        """
        self.use_colors = use_colors

    def notify(self, alert: Any) -> bool:
        """Print alert to console."""
        try:
            severity = alert.severity.value
            color = self.COLORS.get(severity, "") if self.use_colors else ""
            reset = self.COLORS["reset"] if self.use_colors else ""

            print(f"\n{color}{'='*60}{reset}")
            print(f"{color}[{severity.upper()}] {alert.title}{reset}")
            print(f"{color}{'='*60}{reset}")
            print(f"Source: {alert.source}")
            print(f"Time: {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"ID: {alert.alert_id}")
            if alert.count > 1:
                print(f"Count: {alert.count} (deduplicated)")
            print(f"\n{alert.message}\n")

            if alert.tags:
                print("Tags:")
                for key, value in alert.tags.items():
                    print(f"  {key}: {value}")

            print(f"{color}{'='*60}{reset}\n")
            return True

        except Exception as e:
            logger.error(f"Console notifier error: {e}")
            return False


class SlackNotifier(Notifier):
    """
    Slack webhook notifier.

    Sends alerts to Slack channels via incoming webhooks.
    Uses Slack's Block Kit for rich formatting.
    """

    def __init__(self, webhook_url: str, channel: Optional[str] = None):
        """
        Initialize Slack notifier.

        Args:
            webhook_url: Slack incoming webhook URL
            channel: Optional channel override
        """
        self.webhook_url = webhook_url
        self.channel = channel

    def notify(self, alert: Any) -> bool:
        """Send alert to Slack."""
        try:
            import requests

            # Map severity to Slack colors
            color_map = {
                "critical": "#FF0000",  # Red
                "high": "#FFA500",  # Orange
                "medium": "#FFD700",  # Gold
                "low": "#00FF00",  # Green
                "info": "#0000FF"  # Blue
            }

            color = color_map.get(alert.severity.value, "#808080")

            # Build Slack message payload
            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"[{alert.severity.value.upper()}] {alert.title}",
                        "text": alert.message,
                        "fields": [
                            {
                                "title": "Source",
                                "value": alert.source,
                                "short": True
                            },
                            {
                                "title": "Alert ID",
                                "value": alert.alert_id,
                                "short": True
                            },
                            {
                                "title": "Time",
                                "value": alert.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                                "short": True
                            },
                            {
                                "title": "Status",
                                "value": alert.status.value,
                                "short": True
                            }
                        ],
                        "footer": "ADAPT-RCA Alert System",
                        "ts": int(alert.created_at.timestamp())
                    }
                ]
            }

            # Add count if deduplicated
            if alert.count > 1:
                payload["attachments"][0]["fields"].append({
                    "title": "Occurrences",
                    "value": str(alert.count),
                    "short": True
                })

            # Add channel if specified
            if self.channel:
                payload["channel"] = self.channel

            # Add tags if present
            if alert.tags:
                tags_text = ", ".join(f"{k}={v}" for k, v in alert.tags.items())
                payload["attachments"][0]["fields"].append({
                    "title": "Tags",
                    "value": tags_text,
                    "short": False
                })

            # Send to Slack
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()

            logger.debug(f"Slack notification sent for alert {alert.alert_id}")
            return True

        except ImportError:
            logger.error("requests library not installed. Install with: pip install requests")
            return False
        except Exception as e:
            logger.error(f"Slack notifier error: {e}")
            return False


class EmailNotifier(Notifier):
    """
    Email notifier using SMTP.

    Sends alert notifications via email with HTML formatting.
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        from_addr: str,
        to_addrs: list,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True
    ):
        """
        Initialize email notifier.

        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            from_addr: Sender email address
            to_addrs: List of recipient email addresses
            username: Optional SMTP username
            password: Optional SMTP password
            use_tls: Whether to use TLS
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.username = username
        self.password = password
        self.use_tls = use_tls

    def notify(self, alert: Any) -> bool:
        """Send alert via email."""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"
            msg['From'] = self.from_addr
            msg['To'] = ', '.join(self.to_addrs)

            # Plain text version
            text_content = f"""
ADAPT-RCA Alert

Severity: {alert.severity.value.upper()}
Title: {alert.title}
Source: {alert.source}
Time: {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}
Alert ID: {alert.alert_id}
Status: {alert.status.value}

Message:
{alert.message}
"""

            if alert.tags:
                text_content += "\nTags:\n"
                for key, value in alert.tags.items():
                    text_content += f"  {key}: {value}\n"

            # HTML version
            severity_colors = {
                "critical": "#d32f2f",
                "high": "#f57c00",
                "medium": "#fbc02d",
                "low": "#388e3c",
                "info": "#1976d2"
            }
            color = severity_colors.get(alert.severity.value, "#757575")

            html_content = f"""
<html>
<body style="font-family: Arial, sans-serif; padding: 20px;">
    <div style="border-left: 4px solid {color}; padding-left: 16px;">
        <h2 style="color: {color}; margin-top: 0;">
            [{alert.severity.value.upper()}] {alert.title}
        </h2>
        <table style="border-collapse: collapse; margin: 16px 0;">
            <tr>
                <td style="padding: 8px; font-weight: bold;">Source:</td>
                <td style="padding: 8px;">{alert.source}</td>
            </tr>
            <tr>
                <td style="padding: 8px; font-weight: bold;">Time:</td>
                <td style="padding: 8px;">{alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}</td>
            </tr>
            <tr>
                <td style="padding: 8px; font-weight: bold;">Alert ID:</td>
                <td style="padding: 8px;"><code>{alert.alert_id}</code></td>
            </tr>
            <tr>
                <td style="padding: 8px; font-weight: bold;">Status:</td>
                <td style="padding: 8px;">{alert.status.value}</td>
            </tr>
        </table>
        <div style="background: #f5f5f5; padding: 12px; border-radius: 4px; margin: 16px 0;">
            <p style="margin: 0;"><strong>Message:</strong></p>
            <p style="margin: 8px 0 0 0;">{alert.message}</p>
        </div>
"""

            if alert.tags:
                html_content += """
        <div style="margin: 16px 0;">
            <p style="margin: 0;"><strong>Tags:</strong></p>
            <ul style="margin: 8px 0;">
"""
                for key, value in alert.tags.items():
                    html_content += f"                <li>{key}: {value}</li>\n"
                html_content += "            </ul>\n        </div>\n"

            html_content += """
    </div>
    <hr style="margin: 24px 0; border: none; border-top: 1px solid #e0e0e0;">
    <p style="color: #757575; font-size: 12px;">
        This alert was generated by ADAPT-RCA Alert System
    </p>
</body>
</html>
"""

            # Attach parts
            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.send_message(msg)

            logger.debug(f"Email notification sent for alert {alert.alert_id}")
            return True

        except Exception as e:
            logger.error(f"Email notifier error: {e}")
            return False


class WebhookNotifier(Notifier):
    """
    Generic webhook notifier.

    Sends alert data as JSON to a webhook endpoint. Can be used to
    integrate with custom systems, PagerDuty, etc.
    """

    def __init__(
        self,
        webhook_url: str,
        headers: Optional[Dict[str, str]] = None,
        auth_token: Optional[str] = None
    ):
        """
        Initialize webhook notifier.

        Args:
            webhook_url: Webhook URL to POST alerts to
            headers: Optional custom headers
            auth_token: Optional authorization token (added to headers)
        """
        self.webhook_url = webhook_url
        self.headers = headers or {}

        if auth_token:
            self.headers['Authorization'] = f'Bearer {auth_token}'

        self.headers['Content-Type'] = 'application/json'

    def notify(self, alert: Any) -> bool:
        """Send alert to webhook."""
        try:
            import requests

            # Convert alert to JSON
            payload = alert.to_dict()

            # Send POST request
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()

            logger.debug(f"Webhook notification sent for alert {alert.alert_id}")
            return True

        except ImportError:
            logger.error("requests library not installed. Install with: pip install requests")
            return False
        except Exception as e:
            logger.error(f"Webhook notifier error: {e}")
            return False
