"""
Session Repository — All session lifecycle operations.

Handles creation, lookup, activity tracking, device binding,
assurance level upgrades, and session termination.
"""

import logging
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from app.api.helpers import resolve_query

logger = logging.getLogger(__name__)


class SessionRepository:
    """Data-access layer for the `sessions` table."""

    def __init__(self, db):
        self.db = db

    def create(self, user_id: int, ip_address: str, user_agent: str) -> str:
        """Create a new session and return the session_id."""
        session_id = str(uuid.uuid4())
        context_hash = hashlib.sha256(
            f"{ip_address}|{user_agent}".encode("utf-8")
        ).hexdigest()

        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    """INSERT INTO sessions
                       (session_id, user_id, ip_address, user_agent, context_hash,
                        created_at, last_activity, is_active, assurance_level)
                       VALUES (:param, :param, :param, :param, :param,
                               :param, :param, 1, 'pwd')""")
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(query, (
                    session_id, user_id, ip_address, user_agent,
                    context_hash, now, now
                ))
                conn.commit()
        except Exception:
            logger.exception("SessionRepository.create failed")
            raise
        return session_id

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Fetch active session by ID."""
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    """SELECT * FROM sessions
                       WHERE session_id = :param AND is_active = TRUE""")
                return conn.execute(query, (session_id,)).fetchone()
        except Exception:
            logger.exception("SessionRepository.get failed for session_id=%s", session_id)
            return None

    def update_activity(self, session_id: str):
        """Touch session last_activity timestamp."""
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    "UPDATE sessions SET last_activity = :param WHERE session_id = :param")
                conn.execute(query, (datetime.now(timezone.utc).isoformat(), session_id))
                conn.commit()
        except Exception:
            logger.exception("SessionRepository.update_activity failed")

    def update_assurance(self, session_id: str, assurance_level: str):
        """Upgrade session assurance level (pwd → mfa)."""
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    "UPDATE sessions SET assurance_level = :param WHERE session_id = :param")
                conn.execute(query, (assurance_level, session_id))
                conn.commit()
        except Exception:
            logger.exception("SessionRepository.update_assurance failed")

    def set_device_id(self, session_id: str, device_id: str):
        """Bind a device ID to the session."""
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    "UPDATE sessions SET device_id = :param WHERE session_id = :param")
                conn.execute(query, (device_id, session_id))
                conn.commit()
        except Exception:
            logger.exception("SessionRepository.set_device_id failed")

    def end(self, session_id: str):
        """Terminate a session (logout / expiry)."""
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    """UPDATE sessions SET is_active = FALSE, ended_at = :param
                       WHERE session_id = :param""")
                conn.execute(query, (datetime.now(timezone.utc).isoformat(), session_id))
                conn.commit()
        except Exception:
            logger.exception("SessionRepository.end failed")

    def cleanup_expired(self, timeout_hours: int = 24):
        """Bulk-close sessions older than timeout_hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=timeout_hours)
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    """UPDATE sessions SET is_active = FALSE, ended_at = :param
                       WHERE is_active = TRUE AND last_activity < :param""")
                conn.execute(query, (
                    datetime.now(timezone.utc).isoformat(),
                    cutoff.isoformat()
                ))
                conn.commit()
            logger.info("Cleaned up sessions older than %d hours", timeout_hours)
        except Exception:
            logger.exception("SessionRepository.cleanup_expired failed")

    def get_active_by_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all active sessions for a user (for admin/security dashboard)."""
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    """SELECT session_id, created_at, last_activity, ip_address,
                              user_agent, device_id, assurance_level
                       FROM sessions
                       WHERE user_id = :param AND is_active = TRUE
                       ORDER BY last_activity DESC""")
                return conn.execute(query, (user_id,)).fetchall()
        except Exception:
            logger.exception("SessionRepository.get_active_by_user failed")
            return []
