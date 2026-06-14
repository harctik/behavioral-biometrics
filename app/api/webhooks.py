from flask import request, current_app
from flask_restx import Namespace, Resource
import hmac
import hashlib
import logging
from app.extensions import get_db

logger = logging.getLogger(__name__)

webhooks_ns = Namespace("webhooks", description="Inbound Webhook endpoints")

def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify the HMAC signature of an inbound webhook."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()
    # Support 'sha256=...' format commonly used in webhooks
    if signature.startswith("sha256="):
        signature = signature[7:]
    return hmac.compare_digest(expected, signature)

@webhooks_ns.route("/cbs/callback")
class CBSWebhookCallback(Resource):
    def post(self):
        """Receive callback from Core Banking System (CBS) or Payment Rail."""
        secret = current_app.config.get("WEBHOOK_INBOUND_SECRET")
        if not secret:
            logger.warning("Received inbound webhook but WEBHOOK_INBOUND_SECRET is not configured.")
            return {"error": "Webhook processing not configured"}, 500

        signature = request.headers.get("X-Webhook-Signature")
        if not signature:
            return {"error": "Missing signature"}, 401

        payload_bytes = request.get_data()
        
        if not verify_signature(payload_bytes, signature, secret):
            logger.warning("Invalid webhook signature received.")
            return {"error": "Invalid signature"}, 401

        # Process the valid webhook payload
        payload = request.get_json() or {}
        event_type = payload.get("event")
        
        logger.info(f"Successfully verified inbound webhook for event: {event_type}")
        
        # Log the verified event to audit evidence
        # In a real system, you would branch logic based on event_type
        # e.g., if event_type == "transaction.cleared": update_db()
        
        return {"success": True, "message": "Webhook received and verified"}, 200
