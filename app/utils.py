"""
Common utility functions for the Behavior-Based Authentication system.

This module consolidates frequently used operations like JSON handling,
file operations, and other helper functions to avoid code duplication.
"""

import json
import logging
import hmac
import hashlib
import secrets
import time
from typing import Any, Dict, Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)
_NONCE_CACHE: Dict[str, float] = {}
_NONCE_REDIS_WARNED = False


def _get_nonce_redis():
    """Get Redis client for nonce storage, if available."""
    global _NONCE_REDIS_WARNED
    try:
        from flask import current_app

        client = current_app.extensions.get("redis_client")
        if client:
            return client
    except RuntimeError:
        # Outside Flask app context
        pass
    if not _NONCE_REDIS_WARNED:
        _NONCE_REDIS_WARNED = True
        logger.warning(
            "Nonce cache falling back to in-memory dict. "
            "In multi-worker deployments this breaks replay protection. "
            "Set REDIS_URL to enable shared nonce storage."
        )
    return None


def issue_nonce(ttl_seconds: int = 300) -> str:
    """Issue a short-lived nonce token.

    Uses Redis ``SET nonce:{token} EX {ttl} NX`` for atomic issuance when
    available, falling back to an in-process dict otherwise.
    """
    nonce = secrets.token_urlsafe(24)
    redis_client = _get_nonce_redis()
    if redis_client:
        redis_client.set(f"nonce:{nonce}", "1", ex=ttl_seconds, nx=True)
    else:
        _NONCE_CACHE[nonce] = time.time() + ttl_seconds
    return nonce


def consume_nonce(nonce: str) -> bool:
    """Consume a nonce once; returns False if missing/expired/reused.

    Uses Redis ``DEL`` and checks that the key existed before deletion.
    Falls back to the in-process dict when Redis is unavailable.
    """
    redis_client = _get_nonce_redis()
    if redis_client:
        # DEL returns the number of keys removed; 1 means it existed and is now consumed
        return redis_client.delete(f"nonce:{nonce}") == 1
    else:
        expires_at = _NONCE_CACHE.pop(nonce, None)
        if expires_at is None:
            return False
        return expires_at >= time.time()


def sign_operation(payload: Dict[str, Any], secret_key: str) -> str:
    """Sign operation payload with HMAC-SHA256."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(
        secret_key.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_operation_signature(
    payload: Dict[str, Any],
    signature: str,
    secret_key: str,
) -> bool:
    """Verify an HMAC operation signature."""
    expected = sign_operation(payload, secret_key)
    return hmac.compare_digest(expected, signature)
