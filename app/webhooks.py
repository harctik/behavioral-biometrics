"""
Webhook system for Behavior-Based Authentication API.

This module provides a webhook system for sending real-time notifications about
authentication events, risk assessments, and system activities to external services.

Note: All delivery is synchronous (via ThreadPoolExecutor) because Flask runs
under WSGI — there is no asyncio event loop. The async methods have been removed.
"""

import hashlib
import hmac
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlparse

import requests

from .error_handling import ExternalServiceError

logger = logging.getLogger(__name__)


class WebhookEventType(Enum):
    """Types of events that can trigger webhooks."""

    USER_REGISTERED = "user.registered"
    USER_LOGIN_SUCCESS = "user.login.success"
    USER_LOGIN_FAILED = "user.login.failed"
    USER_LOGOUT = "user.logout"
    MFA_VERIFIED = "mfa.verified"
    MFA_FAILED = "mfa.failed"
    PASSWORD_RESET_REQUESTED = "password_reset.requested"
    PASSWORD_RESET_COMPLETED = "password_reset.completed"
    RISK_ASSESSMENT_HIGH = "risk_assessment.high"
    RISK_ASSESSMENT_MEDIUM = "risk_assessment.medium"
    RISK_ASSESSMENT_LOW = "risk_assessment.low"
    SESSION_CREATED = "session.created"
    SESSION_TERMINATED = "session.terminated"
    SESSION_EXPIRED = "session.expired"
    BEHAVIORAL_ANOMALY_DETECTED = "behavioral.anomaly_detected"
    TRANSACTION_APPROVED = "transaction.approved"
    TRANSACTION_DENIED = "transaction.denied"
    TRANSACTION_REVIEW_REQUIRED = "transaction.review_required"
    ADMIN_ACTION_PERFORMED = "admin.action_performed"
    COMPLIANCE_DATA_ACCESSED = "compliance.data_accessed"
    COMPLIANCE_DATA_ANONYMIZED = "compliance.data_anonymized"
    SYSTEM_HEALTH_CHANGED = "system.health_changed"
    API_KEY_CREATED = "api_key.created"
    API_KEY_REVOKED = "api_key.revoked"


class WebhookDeliveryStatus(Enum):
    """Delivery status of webhook events."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class Webhook:
    """Represents a webhook configuration."""

    def __init__(
        self,
        url: str,
        secret: Optional[str] = None,
        events: Optional[List[WebhookEventType]] = None,
        enabled: bool = True,
        max_retries: int = 3,
        timeout: int = 10,
        verify_ssl: bool = True,
        custom_headers: Optional[Dict[str, str]] = None,
    ):
        self.url = url
        self.secret = secret
        self.events = events or []
        self.enabled = enabled
        self.max_retries = max_retries
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.custom_headers = custom_headers or {}
        self.created_at = datetime.utcnow()
        self.last_delivery_attempt = None
        self.delivery_stats = {
            "total_attempts": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "last_error": None,
        }

    def should_deliver(self, event_type: WebhookEventType) -> bool:
        """Check if this webhook should receive the given event."""
        if not self.enabled:
            return False
        if not self.events:  # Empty list means all events
            return True
        return event_type in self.events

    def generate_signature(self, payload: str, timestamp: int) -> str:
        """Generate HMAC signature for webhook payload."""
        if not self.secret:
            return ""

        message = f"{timestamp}.{payload}"
        signature = hmac.new(
            self.secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"

    def validate_url(self) -> bool:
        """Validate the webhook URL against SSRF attacks."""
        try:
            import socket
            import ipaddress
            result = urlparse(self.url)
            if result.scheme not in ('http', 'https'):
                return False
            if not result.netloc:
                return False
            hostname = result.hostname
            if not hostname:
                return False
            try:
                ip = socket.gethostbyname(hostname)
                ip_obj = ipaddress.ip_address(ip)
                if (
                    ip_obj.is_private
                    or ip_obj.is_loopback
                    or ip_obj.is_link_local
                    or ip_obj.is_multicast
                    or ip_obj.is_reserved
                    or ip_obj.is_unspecified
                    or str(ip_obj).startswith("169.254.")
                    or str(ip_obj) == "0.0.0.0"
                ):
                    return False
            except socket.gaierror:
                return False
            return True
        except Exception:
            return False


class WebhookPayload:
    """Represents a webhook payload."""

    def __init__(
        self,
        event_type: WebhookEventType,
        data: Dict[str, Any],
        webhook_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ):
        self.event_type = event_type
        self.data = data
        self.webhook_id = (
            webhook_id
            or f"wh_{int(time.time())}_{hashlib.md5(str(data).encode()).hexdigest()[:8]}"
        )
        self.timestamp = timestamp or datetime.utcnow()
        self.attempts = 0
        self.status = WebhookDeliveryStatus.PENDING
        self.last_attempt_time = None
        self.error_message = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert payload to dictionary."""
        return {
            "id": self.webhook_id,
            "event": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "attempt": self.attempts,
        }

    def to_json(self) -> str:
        """Convert payload to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class WebhookManager:
    """Manages webhook registration, delivery, and retries."""

    def __init__(self, max_workers: int = 5, retry_delay: int = 5):
        self.webhooks: List[Webhook] = []
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.retry_delay = retry_delay
        self._running = False

    def register_webhook(self, webhook: Webhook) -> str:
        """Register a new webhook."""
        if not webhook.validate_url():
            raise ValueError(f"Invalid webhook URL: {webhook.url}")

        # Generate unique ID for the webhook
        webhook_id = hashlib.sha256(
            f"{webhook.url}:{webhook.secret or ''}:{time.time()}".encode()
        ).hexdigest()[:16]

        self.webhooks.append(webhook)
        return webhook_id

    def unregister_webhook(self, url: str) -> bool:
        """Unregister a webhook by URL."""
        initial_count = len(self.webhooks)
        self.webhooks = [wh for wh in self.webhooks if wh.url != url]
        return len(self.webhooks) < initial_count

    def get_webhooks_for_event(self, event_type: WebhookEventType) -> List[Webhook]:
        """Get all webhooks that should receive the given event."""
        return [wh for wh in self.webhooks if wh.should_deliver(event_type)]

    def deliver(self, webhook: Webhook, payload: WebhookPayload) -> bool:
        """Deliver a webhook payload synchronously (via requests)."""
        payload.attempts += 1
        payload.last_attempt_time = datetime.utcnow()
        webhook.last_delivery_attempt = payload.last_attempt_time
        webhook.delivery_stats["total_attempts"] += 1

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "BehaviorAuth-Webhook/1.0",
            "X-Webhook-Event": payload.event_type.value,
            "X-Webhook-ID": payload.webhook_id,
            "X-Webhook-Timestamp": str(int(payload.timestamp.timestamp())),
        }

        if webhook.custom_headers:
            headers.update(webhook.custom_headers)

        if webhook.secret:
            timestamp = int(time.time())
            signature = webhook.generate_signature(payload.to_json(), timestamp)
            headers["X-Webhook-Signature"] = signature
            headers["X-Webhook-Timestamp"] = str(timestamp)

        try:
            response = requests.post(
                webhook.url,
                data=payload.to_json(),
                headers=headers,
                timeout=webhook.timeout,
                verify=webhook.verify_ssl,
            )

            if 200 <= response.status_code < 300:
                payload.status = WebhookDeliveryStatus.DELIVERED
                webhook.delivery_stats["successful_deliveries"] += 1
                return True
            else:
                payload.status = WebhookDeliveryStatus.FAILED
                payload.error_message = (
                    f"HTTP {response.status_code}: {response.text[:200]}"
                )
                webhook.delivery_stats["failed_deliveries"] += 1
                webhook.delivery_stats["last_error"] = payload.error_message
                return False

        except Exception as e:
            payload.status = WebhookDeliveryStatus.FAILED
            payload.error_message = str(e)
            webhook.delivery_stats["failed_deliveries"] += 1
            webhook.delivery_stats["last_error"] = payload.error_message
            return False

    def deliver_with_retry(self, webhook: Webhook, payload: WebhookPayload) -> bool:
        """Deliver with exponential backoff retries."""
        for attempt in range(webhook.max_retries):
            if attempt > 0:
                time.sleep(self.retry_delay * attempt)

            success = self.deliver(webhook, payload)
            if success:
                return True
            payload.status = WebhookDeliveryStatus.RETRYING

        return False

    def trigger_event(
        self, event_type: WebhookEventType, data: Dict[str, Any]
    ) -> List[str]:
        """
        Trigger a webhook event and deliver to all registered webhooks.

        Delivery is offloaded to a ThreadPoolExecutor so the main request
        thread is not blocked.
        """
        webhooks = self.get_webhooks_for_event(event_type)
        if not webhooks:
            return []

        payload = WebhookPayload(event_type, data)
        webhook_ids = []

        for webhook in webhooks:
            self.executor.submit(self.deliver_with_retry, webhook, payload)
            webhook_ids.append(payload.webhook_id)

        return webhook_ids

    def get_stats(self) -> Dict[str, Any]:
        """Get webhook delivery statistics."""
        total_webhooks = len(self.webhooks)
        enabled_webhooks = len([wh for wh in self.webhooks if wh.enabled])

        total_attempts = sum(
            wh.delivery_stats["total_attempts"] for wh in self.webhooks
        )
        successful = sum(
            wh.delivery_stats["successful_deliveries"] for wh in self.webhooks
        )
        failed = sum(wh.delivery_stats["failed_deliveries"] for wh in self.webhooks)

        success_rate = (successful / total_attempts * 100) if total_attempts > 0 else 0

        return {
            "total_webhooks": total_webhooks,
            "enabled_webhooks": enabled_webhooks,
            "delivery_stats": {
                "total_attempts": total_attempts,
                "successful_deliveries": successful,
                "failed_deliveries": failed,
                "success_rate": round(success_rate, 2),
            },
        }


# Global webhook manager instance
_webhook_manager = None


def get_webhook_manager() -> WebhookManager:
    """Get or create the global webhook manager instance."""
    global _webhook_manager
    if _webhook_manager is None:
        _webhook_manager = WebhookManager()
    return _webhook_manager


def trigger_webhook(
    event_type: Union[WebhookEventType, str], data: Dict[str, Any]
) -> List[str]:
    """
    Trigger a webhook event (convenience function).

    Args:
        event_type: WebhookEventType or string event type
        data: Event data

    Returns:
        List of webhook IDs that were triggered
    """
    if isinstance(event_type, str):
        try:
            event_type = WebhookEventType(event_type)
        except ValueError:
            raise ValueError(f"Invalid event type: {event_type}")

    manager = get_webhook_manager()
    return manager.trigger_event(event_type, data)


# trigger_webhook_async removed — Flask/WSGI has no event loop.
# Use trigger_webhook() which offloads to a thread pool automatically.


def register_webhook_from_config(config: Dict[str, Any]) -> str:
    """
    Register a webhook from configuration dictionary.

    Args:
        config: Webhook configuration

    Returns:
        Webhook ID
    """
    webhook = Webhook(
        url=config["url"],
        secret=config.get("secret"),
        events=[WebhookEventType(event) for event in config.get("events", [])],
        enabled=config.get("enabled", True),
        max_retries=config.get("max_retries", 3),
        timeout=config.get("timeout", 10),
        verify_ssl=config.get("verify_ssl", True),
        custom_headers=config.get("custom_headers", {}),
    )

    manager = get_webhook_manager()
    return manager.register_webhook(webhook)


# Flask integration
def init_webhooks(app):
    """Initialize webhooks with Flask app configuration."""
    webhook_configs = app.config.get("WEBHOOKS", [])

    for config in webhook_configs:
        try:
            webhook_id = register_webhook_from_config(config)
            app.logger.info(f"Registered webhook {webhook_id} for URL: {config['url']}")
        except Exception as e:
            app.logger.error(f"Failed to register webhook: {e}")
