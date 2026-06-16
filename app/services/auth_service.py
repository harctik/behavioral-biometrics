import logging
from flask import current_app
from app.extensions import get_redis
from app.api.helpers import resolve_query

logger = logging.getLogger(__name__)

class AuthService:
    @staticmethod
    def check_credential_stuffing(ip_address: str) -> tuple:
        """Track failed attempts per IP. Block after CREDENTIAL_STUFFING_MAX_ATTEMPTS_PER_IP within window."""
        rc = get_redis()
        if not rc:
            return True, ""
        
        max_attempts = current_app.config.get("CREDENTIAL_STUFFING_MAX_ATTEMPTS_PER_IP", 10)
        window = current_app.config.get("CREDENTIAL_STUFFING_WINDOW_SECONDS", 300)
        
        key = f"stuffing:{ip_address}"
        try:
            attempts = int(rc.get(key) or 0)
            if attempts >= max_attempts:
                return False, f"Too many failed login attempts from this IP. Blocked for {window // 60} minutes."
        except Exception:
            pass
        return True, ""

    @staticmethod
    def increment_credential_stuffing(ip_address: str):
        rc = get_redis()
        if not rc:
            return
        window = current_app.config.get("CREDENTIAL_STUFFING_WINDOW_SECONDS", 300)
        key = f"stuffing:{ip_address}"
        try:
            if rc.exists(key):
                rc.incr(key)
            else:
                rc.setex(key, window, 1)
        except Exception:
            pass

    @staticmethod
    def check_account_lockout(username: str) -> tuple:
        """Check if account is locked due to too many failed attempts."""
        rc = get_redis()
        if not rc:
            return True, current_app.config.get("MAX_LOGIN_ATTEMPTS", 5), None
            
        max_attempts = current_app.config.get("MAX_LOGIN_ATTEMPTS", 5)
        
        key = f"lockout:{username}"
        try:
            attempts = int(rc.get(key) or 0)
            if attempts >= max_attempts:
                ttl = rc.ttl(key)
                if ttl > 0:
                    from datetime import datetime, timedelta, timezone
                    lockout_until = datetime.now(timezone.utc) + timedelta(seconds=ttl)
                    return False, 0, lockout_until.isoformat()
            return True, max(0, max_attempts - attempts), None
        except Exception:
            return True, max_attempts, None

    @staticmethod
    def increment_account_lockout(username: str) -> tuple:
        """Increment failed attempts and return remaining attempts and optional lockout_until."""
        rc = get_redis()
        if not rc:
            return current_app.config.get("MAX_LOGIN_ATTEMPTS", 5), None
            
        max_attempts = current_app.config.get("MAX_LOGIN_ATTEMPTS", 5)
        lockout_minutes = current_app.config.get("LOCKOUT_DURATION_MINUTES", 15)
        
        key = f"lockout:{username}"
        try:
            if rc.exists(key):
                attempts = rc.incr(key)
            else:
                rc.setex(key, lockout_minutes * 60, 1)
                attempts = 1
                
            if attempts >= max_attempts:
                ttl = rc.ttl(key)
                from datetime import datetime, timedelta, timezone
                lockout_until = datetime.now(timezone.utc) + timedelta(seconds=ttl)
                return 0, lockout_until.isoformat()
            return max(0, max_attempts - attempts), None
        except Exception:
            return max_attempts, None

    @staticmethod
    def reset_account_lockout(username: str):
        rc = get_redis()
        if rc:
            try:
                rc.delete(f"lockout:{username}")
            except Exception:
                pass

    @staticmethod
    def is_known_device(db, user_id: int, device_id: str) -> bool:
        """
        Check if this device_id has successfully logged in before
        for this user. Returns False for new/unknown devices.
        """
        if not device_id:
            return False
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        try:
            with db.get_connection() as conn:
                query = resolve_query(
                    db,
                    """
                    SELECT session_id FROM sessions
                    WHERE user_id = :param
                      AND device_id = :param
                      AND created_at < :param
                    LIMIT 1
                    """,
                )
                rows = conn.execute(
                    query,
                    (user_id, device_id, cutoff.isoformat()),
                ).fetchall()
            return len(rows) > 0
        except Exception:
            return False

    # ── Two-Phase Login: Challenge Tokens ──────────────────────────────────

    @staticmethod
    def create_login_challenge(user_id: int) -> str:
        """Generate a signed challenge token for Phase 2 of login.

        Uses itsdangerous to embed user_id in the token itself,
        so Redis is NOT required. Token is valid for 5 minutes.
        """
        from flask import current_app
        from itsdangerous import URLSafeTimedSerializer
        s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="login-challenge")
        token = s.dumps({"uid": user_id})
        return token

    @staticmethod
    def validate_login_challenge(token: str) -> int | None:
        """Validate a signed login challenge token.

        Returns user_id if valid, None if expired/invalid.
        Token is valid for 5 minutes (300 seconds).
        """
        from flask import current_app
        from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
        s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="login-challenge")
        try:
            data = s.loads(token, max_age=300)
            return data.get("uid")
        except (BadSignature, SignatureExpired):
            return None
        except Exception:
            logger.error("Failed to validate login challenge")
            return None
        return None

    # ── Behavioral Decision Engine ─────────────────────────────────────────

    @staticmethod
    def evaluate_behavioral_decision(
        match_score: float,
        enrollment_phase: bool,
        is_known_device: bool = False,
    ) -> str:
        """Always grant access. Behavioral data is collected for analytics
        and dashboard display only — it never gates login."""
        return "grant"

    # ── User Blocking ──────────────────────────────────────────────────────

    @staticmethod
    def block_user(user_id: int):
        """Block a user due to behavioral anomaly. 24-hour TTL in Redis."""
        rc = get_redis()
        if rc:
            try:
                rc.setex(f"behavioral_block:{user_id}", 86400, "1")
            except Exception:
                pass

    @staticmethod
    def unblock_user(user_id: int):
        """Remove behavioral block for a user."""
        rc = get_redis()
        if rc:
            try:
                rc.delete(f"behavioral_block:{user_id}")
            except Exception:
                pass

    @staticmethod
    def is_user_blocked(user_id: int) -> bool:
        """Check if a user is currently blocked due to behavioral anomaly."""
        rc = get_redis()
        if not rc:
            return False
        try:
            return bool(rc.get(f"behavioral_block:{user_id}"))
        except Exception:
            return False

    # ── Account Recovery Tokens ────────────────────────────────────────────

    @staticmethod
    def create_recovery_token(user_id: int) -> str:
        """Generate a recovery token for blocked accounts. 30-minute TTL."""
        import uuid
        token = str(uuid.uuid4())
        rc = get_redis()
        if rc:
            try:
                rc.setex(f"recovery_token:{token}", 1800, str(user_id))
                # Track recovery attempts (max 3 per 24h)
                attempts_key = f"recovery_attempts:{user_id}"
                if not rc.exists(attempts_key):
                    rc.setex(attempts_key, 86400, 0)
            except Exception:
                logger.error("Failed to create recovery token")
        return token

    @staticmethod
    def validate_recovery_token(token: str) -> int | None:
        """Validate a recovery token. Returns user_id if valid."""
        rc = get_redis()
        if not rc:
            return None
        try:
            key = f"recovery_token:{token}"
            user_id_str = rc.get(key)
            if user_id_str:
                user_id = int(user_id_str)
                # Check attempts limit
                attempts = int(rc.get(f"recovery_attempts:{user_id}") or 0)
                if attempts >= 3:
                    return None  # Max attempts exceeded
                rc.incr(f"recovery_attempts:{user_id}")
                return user_id
        except Exception:
            logger.error("Failed to validate recovery token")
        return None

    @staticmethod
    def consume_recovery_token(token: str):
        """Delete a recovery token after successful recovery."""
        rc = get_redis()
        if rc:
            try:
                rc.delete(f"recovery_token:{token}")
            except Exception:
                pass

