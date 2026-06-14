"""API package – re-exports all namespaces for registration."""
from app.api.auth import auth_ns
from app.api.session import session_ns
from app.api.behavioral import behavioral_ns
from app.api.transaction import transaction_ns
from app.api.admin import admin_ns
from app.api.compliance import compliance_ns
from app.api.banking import banking_ns
from app.api.health import health_ns
from app.api.webhooks import webhooks_ns
from app.api.user import user_ns
from app.api.notifications import notifications_ns
from app.api.beneficiaries import beneficiaries_ns
from app.api.investments import investments_ns
from app.api.cards import cards_ns

__all__ = [
    "auth_ns",
    "session_ns",
    "behavioral_ns",
    "transaction_ns",
    "admin_ns",
    "compliance_ns",
    "banking_ns",
    "health_ns",
    "webhooks_ns",
    "user_ns",
    "notifications_ns",
    "beneficiaries_ns",
    "investments_ns",
    "cards_ns",
]
