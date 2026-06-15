"""
Repository package — Data-access layer for the behavioral authentication system.

Each repository handles a single entity/aggregate, keeping SQL queries
isolated from business logic (Service Layer) and HTTP routing (API Layer).

Architecture:
    API Routes → Services → Repositories → Database (SQLAlchemy)
"""

from app.repositories.user_repository import UserRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.audit_repository import AuditRepository

__all__ = [
    "UserRepository",
    "SessionRepository",
    "AuditRepository",
]
