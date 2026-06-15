"""
User Repository — Single Responsibility for all user-related DB operations.

Implements the Repository Pattern to decouple data access from business logic.
All user CRUD, authentication checks, and profile queries live here.
"""

import logging
import bcrypt
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app.api.helpers import resolve_query

logger = logging.getLogger(__name__)

_DUMMY_HASH = bcrypt.hashpw(b"dummy-constant-time-padding", bcrypt.gensalt())


class UserRepository:
    """Data-access layer for the `users` table.
    
    Accepts a `db` (DatabaseManager) instance via constructor injection
    so it can be unit-tested with a mock or in-memory DB.
    """

    def __init__(self, db):
        self.db = db

    # ── Lookups ───────────────────────────────────────────────────────────

    def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Fetch user by primary key."""
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    "SELECT * FROM users WHERE user_id = :param")
                return conn.execute(query, (user_id,)).fetchone()
        except Exception:
            logger.exception("UserRepository.get_by_id failed for user_id=%s", user_id)
            return None

    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch user by unique username."""
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    "SELECT * FROM users WHERE username = :param")
                return conn.execute(query, (username,)).fetchone()
        except Exception:
            logger.exception("UserRepository.get_by_username failed for username=%s", username)
            return None

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Fetch user by unique email address."""
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    "SELECT * FROM users WHERE email = :param")
                return conn.execute(query, (email,)).fetchone()
        except Exception:
            logger.exception("UserRepository.get_by_email failed for email=%s", email)
            return None

    def get_for_auth(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch minimal user record needed for authentication (password hash + status)."""
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    """SELECT user_id, username, email, password_hash, mfa_secret,
                              is_active, email_verified, mfa_enabled, role,
                              failed_attempts, locked_until
                       FROM users WHERE username = :param""")
                return conn.execute(query, (username,)).fetchone()
        except Exception:
            logger.exception("UserRepository.get_for_auth failed")
            return None

    def get_for_mfa(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Fetch minimal record needed for MFA verification."""
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    """SELECT user_id, username, mfa_secret, mfa_enabled
                       FROM users WHERE user_id = :param""")
                return conn.execute(query, (user_id,)).fetchone()
        except Exception:
            logger.exception("UserRepository.get_for_mfa failed")
            return None

    # ── Mutations ─────────────────────────────────────────────────────────

    def create(self, username: str, email: str, password: str,
               mfa_secret: Optional[str] = None) -> Optional[int]:
        """Create a new user and return their user_id. Returns None on conflict."""
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    """INSERT INTO users (username, email, password_hash, mfa_secret)
                       VALUES (:param, :param, :param, :param)""")
                cursor = conn.execute(query, (username, email, password_hash, mfa_secret))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            if "UNIQUE" in str(e).upper() or "unique" in str(e).lower():
                return None
            logger.exception("UserRepository.create failed")
            raise

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Verify credentials. Returns user dict on success, None on failure.
        
        Uses constant-time comparison against a dummy hash to prevent
        timing-based user enumeration.
        """
        user = self.get_for_auth(username)
        if not user:
            # Constant-time: compare against dummy hash to prevent timing attacks
            bcrypt.checkpw(b"dummy-password", _DUMMY_HASH)
            return None

        stored_hash = user.get("password_hash", "")
        if not bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
            return None

        if not user.get("is_active", True):
            return None

        # Update last_login timestamp
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    "UPDATE users SET last_login = :param WHERE user_id = :param")
                conn.execute(query, (datetime.now(timezone.utc).isoformat(), user["user_id"]))
                conn.commit()
        except Exception:
            pass  # Non-critical — login still succeeds

        return user

    def update_password(self, user_id: int, new_password: str) -> bool:
        """Hash and update user password."""
        password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    "UPDATE users SET password_hash = :param WHERE user_id = :param")
                conn.execute(query, (password_hash, user_id))
                conn.commit()
            return True
        except Exception:
            logger.exception("UserRepository.update_password failed for user_id=%s", user_id)
            return False

    def set_email_verified(self, user_id: int):
        """Mark user email as verified."""
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    "UPDATE users SET email_verified = 1 WHERE user_id = :param")
                conn.execute(query, (user_id,))
                conn.commit()
        except Exception:
            logger.exception("UserRepository.set_email_verified failed")

    def update_role(self, user_id: int, role: str):
        """Update user role (user/analyst/admin)."""
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    "UPDATE users SET role = :param WHERE user_id = :param")
                conn.execute(query, (role, user_id))
                conn.commit()
        except Exception:
            logger.exception("UserRepository.update_role failed")

    def update_calibration_status(self, user_id: int, is_complete: bool):
        """Update behavioral calibration status."""
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    "UPDATE users SET calibration_complete = :param WHERE user_id = :param")
                conn.execute(query, (1 if is_complete else 0, user_id))
                conn.commit()
        except Exception:
            logger.exception("UserRepository.update_calibration_status failed")

    def anonymize(self, user_id: int):
        """GDPR/DPDP Act anonymization — scrub PII but keep behavioral data for model integrity."""
        anon_user = f"anon_{secrets.token_hex(8)}"
        anon_email = f"{anon_user}@redacted.local"
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    """UPDATE users SET username = :param, email = :param,
                       password_hash = :param, mfa_secret = NULL,
                       is_active = 0 WHERE user_id = :param""")
                conn.execute(query, (anon_user, anon_email, "REDACTED", user_id))
                conn.commit()
            logger.info("User %d anonymized successfully", user_id)
        except Exception:
            logger.exception("UserRepository.anonymize failed for user_id=%s", user_id)
