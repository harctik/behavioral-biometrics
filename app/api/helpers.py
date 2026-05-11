"""Shared helpers used across API blueprints.

Centralises session caching, role checking, AAL enforcement and session context
validation so each blueprint imports a single canonical implementation.
"""
from typing import Optional, Dict, Any, Set
from functools import wraps
from flask import request, current_app
from flask_jwt_extended import get_jwt_identity, get_jwt
import hashlib
import logging

from app.extensions import get_db, get_redis
from app.error_handling import make_error_response
from app.redis_store import (
    get_session as cache_get_session,
    set_session as cache_set_session,
)

logger = logging.getLogger(__name__)

# ── AAL ordering ─────────────────────────────────────────────────────────────
_AAL_ORDER = {"pwd": 1, "mfa": 2}


def require_mfa(fn):
    """Decorator: reject the request unless the JWT carries ``aal == 'mfa'``.

    Apply to any endpoint that must be protected by completed MFA
    (transactions, admin, banking, etc.).  Must be placed *after*
    ``@jwt_required()`` in the decorator stack so the JWT is available.

    Example::

        @jwt_required()
        @require_mfa
        def post(self): ...
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        aal = claims.get("aal", "pwd")
        if aal != "mfa":
            return make_error_response(
                "MFA_REQUIRED",
                "Multi-factor authentication required for this operation",
                status=403,
            )
        return fn(*args, **kwargs)

    return wrapper


def get_session_cached(session_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a session, checking Redis cache first then SQLite.

    Transparently populates the cache on miss so subsequent lookups within
    the same request or neighbouring requests benefit.
    """
    if not session_id:
        return None
    db = get_db()
    redis_client = get_redis()
    cached = cache_get_session(redis_client, session_id) if redis_client else None
    if cached:
        return cached
    session = db.get_session(session_id)
    if session and redis_client:
        ttl = int(current_app.config.get("SESSION_CACHE_TTL_SECONDS", 28800))
        cache_set_session(redis_client, session_id, session, ttl_seconds=ttl)
    return session


def validate_session_context(session: Dict[str, Any]) -> bool:
    """Validate that the request context (IP + UA) matches the session origin.

    Compares the SHA-256 fingerprint of the current request's IP + User-Agent
    against the ``context_hash`` stored when the session was created.

    Handles proxy setups (Next.js dev proxy) by treating all localhost/loopback
    variants (127.0.0.1, ::1, localhost) as equivalent.

    Returns ``False`` when the context diverges, signalling that step-up
    authentication should be triggered by the caller.
    """
    stored_hash = session.get("context_hash")
    if not stored_hash:
        # Legacy session without a context_hash — skip validation in dev
        if current_app.debug:
            return True
        logger.warning(
            "Session %s has no context_hash; failing context validation",
            session.get("session_id", "?"),
        )
        return False

    strict = current_app.config.get("SESSION_CONTEXT_STRICT", not current_app.debug)

    # In non-strict mode (default for development), skip context binding entirely
    if not strict:
        return True

    current_fp = request_context_fingerprint()

    if current_fp != stored_hash:
        # Before failing, check if both are localhost variants
        # (Next.js proxy sends from 127.0.0.1, Flask may have stored ::1 or vice versa)
        current_ip = _get_real_ip()
        stored_ip = session.get("ip_address", "")
        if _is_localhost(current_ip) and _is_localhost(stored_ip):
            return True  # Both are localhost — proxy scenario

        logger.warning(
            "Session context mismatch for session %s (expected=%s, got=%s)",
            session.get("session_id", "?"),
            stored_hash[:12],
            current_fp[:12],
        )
        return False

    return True


_LOCALHOST_IPS = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}


def _is_localhost(ip: str) -> bool:
    """Check if an IP is a localhost/loopback variant."""
    return (ip or "").strip().lower() in _LOCALHOST_IPS


def _get_real_ip() -> str:
    """Get the real client IP, respecting X-Forwarded-For headers."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def request_context_fingerprint() -> str:
    """Build stable request context fingerprint from client IP + user-agent."""
    raw = f"{request.remote_addr or 'unknown'}|{request.headers.get('User-Agent', '')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def require_role(*allowed: str) -> bool:
    """Check whether the JWT-identified user holds one of *allowed* roles.

    Performs auto-promotion from the ``ADMIN_USERNAMES`` / ``ANALYST_USERNAMES``
    config lists so that operators added via environment variables are
    immediately effective without a manual DB migration.
    """
    db = get_db()
    user_id = int(get_jwt_identity())
    user = db.get_user_by_id(user_id)
    if not user:
        return False

    username = (user.get("username") or "").lower()
    admins: Set[str] = {
        u.strip().lower()
        for u in (current_app.config.get("ADMIN_USERNAMES") or "").split(",")
        if u.strip()
    }
    analysts: Set[str] = {
        u.strip().lower()
        for u in (current_app.config.get("ANALYST_USERNAMES") or "").split(",")
        if u.strip()
    }

    # Apply roles from config dynamically (no DB write on the hot path)
    if username in admins:
        user["role"] = "admin"
    elif username in analysts and user.get("role") != "admin":
        user["role"] = "analyst"

    return user.get("role") in set(allowed)


def require_aal(session: Dict[str, Any], min_level: str) -> bool:
    """Return ``True`` if the session's assurance level meets *min_level*.

    AAL hierarchy: ``pwd`` (1) → ``mfa`` (2).
    """
    current = session.get("assurance_level", "pwd")
    return _AAL_ORDER.get(current, 1) >= _AAL_ORDER.get(min_level, 2)


def get_current_user_id() -> int:
    """Convenience wrapper: return JWT identity as ``int``."""
    return int(get_jwt_identity())


def validate_session_ownership(session: Dict[str, Any]) -> Optional[tuple]:
    """If the JWT user does not own *session*, return an error tuple; else ``None``."""
    user_id = get_current_user_id()
    if user_id != session.get("user_id"):
        return {"error": "Token does not match session user"}, 403
    return None
