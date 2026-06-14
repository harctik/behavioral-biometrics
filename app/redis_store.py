from __future__ import annotations

import json
import hashlib
from typing import Any, Optional, List

from .logging_config import get_logger

logger = get_logger(__name__)


def get_redis_client(redis_url: str):
    try:
        import redis  # type: ignore

        return redis.Redis.from_url(redis_url, decode_responses=True)
    except Exception:
        logger.exception("Failed to initialize Redis client")
        return None


def session_key(session_id: str) -> str:
    return f"session:{session_id}"


def set_session(
    client,
    session_id: str,
    payload: dict[str, Any],
    ttl_seconds: int = 8 * 3600,
) -> bool:
    if not client:
        return False
    try:
        client.setex(session_key(session_id), ttl_seconds, json.dumps(payload))
        return True
    except Exception:
        logger.exception("Failed to set session cache")
        return False


def get_session(client, session_id: str) -> Optional[dict[str, Any]]:
    if not client:
        return None
    try:
        raw = client.get(session_key(session_id))
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        logger.exception("Failed to get session cache")
        return None


def delete_session(client, session_id: str) -> None:
    if not client:
        return
    try:
        client.delete(session_key(session_id))
    except Exception:
        logger.exception("Failed to delete session cache")


# ──────────────────────────────────────────────────────────
# Behavioral Feature Cache (Banking Performance Layer)
# ──────────────────────────────────────────────────────────

FEATURE_CACHE_PREFIX = "bfc:"
FEATURE_CACHE_MAX = 512  # Max feature vectors per user
FEATURE_CACHE_TTL = 300  # 5-minute TTL for feature cache (aligned with session activity)
BLOOM_PREFIX = "bloom:"


def _feature_key(user_id: int) -> str:
    return f"{FEATURE_CACHE_PREFIX}{user_id}"


def cache_behavioral_features(
    client,
    user_id: int,
    features: dict[str, Any],
    ttl_seconds: int = FEATURE_CACHE_TTL,
) -> bool:
    """Cache a behavioral feature vector (append-only, last 512 per user).

    Banking Performance: Eliminates redundant feature recomputation
    by caching recently extracted vectors. Append-only design ensures
    no recomputation — new vectors are pushed to a Redis list.
    """
    if not client:
        return False
    try:
        key = _feature_key(user_id)
        client.lpush(key, json.dumps(features))
        client.ltrim(key, 0, FEATURE_CACHE_MAX - 1)  # Keep last 512
        client.expire(key, ttl_seconds)
        return True
    except Exception:
        logger.exception("Failed to cache behavioral features for user %s", user_id)
        return False


def get_cached_features(client, user_id: int, count: int = 50) -> List[dict[str, Any]]:
    """Retrieve cached behavioral feature vectors for a user.

    Returns up to `count` most recent feature vectors.
    """
    if not client:
        return []
    try:
        key = _feature_key(user_id)
        raw_list = client.lrange(key, 0, count - 1)
        return [json.loads(item) for item in raw_list]
    except Exception:
        logger.exception("Failed to get cached features for user %s", user_id)
        return []


def invalidate_feature_cache(client, user_id: int) -> None:
    """Invalidate all cached features for a user (e.g., after recalibration)."""
    if not client:
        return
    try:
        client.delete(_feature_key(user_id))
    except Exception:
        logger.exception("Failed to invalidate feature cache for user %s", user_id)


# ──────────────────────────────────────────────────────────
# Event Deduplication (Bloom Filter Simulation)
# ──────────────────────────────────────────────────────────


def _bloom_key(session_id: str) -> str:
    return f"{BLOOM_PREFIX}{session_id}"


def _event_fingerprint(event_data: dict) -> str:
    """Generate a fingerprint for an event to detect duplicates."""
    serialized = json.dumps(event_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def check_event_duplicate(client, session_id: str, event_data: dict) -> bool:
    """Check if an event has already been processed (Bloom filter simulation).

    Uses Redis SET to track event fingerprints per session.
    Returns True if the event is a duplicate.
    """
    if not client:
        return False
    try:
        key = _bloom_key(session_id)
        fingerprint = _event_fingerprint(event_data)
        return bool(client.sismember(key, fingerprint))
    except Exception:
        return False


def mark_event_processed(
    client, session_id: str, event_data: dict, ttl_seconds: int = 3600
) -> bool:
    """Mark an event as processed to prevent duplicate handling."""
    if not client:
        return False
    try:
        key = _bloom_key(session_id)
        fingerprint = _event_fingerprint(event_data)
        client.sadd(key, fingerprint)
        client.expire(key, ttl_seconds)
        return True
    except Exception:
        logger.exception("Failed to mark event as processed")
        return False
