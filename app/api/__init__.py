"""API package – re-exports all namespaces for registration."""
from app.api.auth import auth_ns
from app.api.session import session_ns
from app.api.behavioral import behavioral_ns
from app.api.transaction import transaction_ns
from app.api.admin import admin_ns
from app.api.compliance import compliance_ns
from app.api.banking import banking_ns

__all__ = [
    "auth_ns",
    "session_ns",
    "behavioral_ns",
    "transaction_ns",
    "admin_ns",
    "compliance_ns",
    "banking_ns",
]
