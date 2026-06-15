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
    """Fetch a session, checking Redis cache first then database.
    
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

    strict = current_app.config.get("SESSION_CONTEXT_STRICT", True)

    # In non-strict mode (explicitly configured), skip context binding
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


def check_session_inactivity(session: Dict[str, Any]) -> tuple:
    """Check if session has exceeded the inactivity timeout.
    Returns (True, "") if active, (False, "reason") if expired.
    Updates the last_activity in Redis to avoid DB writes on every request.
    """
    timeout_minutes = current_app.config.get("SESSION_INACTIVITY_TIMEOUT_MINUTES", 15)
    last_activity_str = session.get("last_activity")
    if not last_activity_str:
        return True, ""
        
    from datetime import datetime, timezone, timedelta
    try:
        if isinstance(last_activity_str, str):
            # Normalise naive DB strings to UTC
            if not last_activity_str.endswith('+00:00') and not last_activity_str.endswith('Z') and '+' not in last_activity_str:
                last_activity_str += '+00:00'
            last_activity = datetime.fromisoformat(last_activity_str.replace('Z', '+00:00'))
        else:
            last_activity = last_activity_str
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)
                
        now = datetime.now(timezone.utc)
        if (now - last_activity) > timedelta(minutes=timeout_minutes):
            return False, f"Session timed out due to {timeout_minutes} minutes of inactivity"
            
        # Optional: touch the session in Redis to update last_activity
        # We only touch it every minute to avoid spamming Redis
        rc = get_redis()
        if rc:
            cache_key = f"session_touch:{session.get('session_id')}"
            if not rc.exists(cache_key):
                rc.setex(cache_key, 60, "1")
                session["last_activity"] = now.isoformat()
                cache_set_session(rc, session["session_id"], session, int(current_app.config.get("SESSION_CACHE_TTL_SECONDS", 28800)))
    except Exception as e:
        logger.warning(f"Error checking session inactivity: {e}")
        
    return True, ""


_LOCALHOST_IPS = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}


def _is_localhost(ip: str) -> bool:
    """Check if an IP is a localhost/loopback variant."""
    return (ip or "").strip().lower() in _LOCALHOST_IPS


def _get_real_ip() -> str:
    """Get the real client IP (relies on ProxyFix middleware for proxy headers)."""
    return request.remote_addr or "unknown"


def request_context_fingerprint() -> str:
    """Build stable request context fingerprint from client IP + user-agent."""
    raw = f"{_get_real_ip()}|{request.headers.get('User-Agent', '')}"
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


def resolve_query(db, base_query: str) -> str:
    """Replaces :param indicators with ? for unified QueryAdapter."""
    return base_query.replace(":param", "?")


def verify_request_signature(fn):
    """Decorator: verify X-Request-Signature HMAC-SHA256 header.

    The signature is computed as ``HMAC-SHA256(signing_key, request_body)``.
    Validates against both current and previous signing keys for
    zero-downtime key rotation.

    Applied to sensitive endpoints (transfers, password changes, etc.).
    Skipped if ``TRANSACTION_SIGNING_REQUIRED`` is False.
    """
    import hmac

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_app.config.get("TRANSACTION_SIGNING_REQUIRED", False):
            return fn(*args, **kwargs)

        signature = request.headers.get("X-Request-Signature", "")
        if not signature:
            return make_error_response(
                "MISSING_SIGNATURE",
                "X-Request-Signature header is required for this endpoint",
                status=400,
            )

        body = request.get_data(as_text=True) or ""
        signing_key = current_app.config.get("TXN_SIGNING_KEY", "")
        prev_key = current_app.config.get("TXN_SIGNING_PREVIOUS_KEY", "")

        keys_to_try = [k for k in [signing_key, prev_key] if k]
        if not keys_to_try:
            logger.warning(
                "TXN_SIGNING_KEY not configured but TRANSACTION_SIGNING_REQUIRED=True"
            )
            return fn(*args, **kwargs)

        for key in keys_to_try:
            expected = hmac.new(
                key.encode("utf-8"),
                body.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if hmac.compare_digest(signature, expected):
                return fn(*args, **kwargs)

        logger.warning(
            "Invalid request signature from user=%s on %s",
            get_jwt_identity(),
            request.path,
        )
        return make_error_response(
            "INVALID_SIGNATURE",
            "Request signature verification failed",
            status=403,
        )

    return wrapper
