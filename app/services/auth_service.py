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
