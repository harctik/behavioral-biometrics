"""Test-only admin / admin sign-in.

Off unless ``DEMO_LOGIN=1``, and then only for requests made on this computer.
It uses its own account, whose stored password is random and never shown, so
``admin`` / ``admin`` is never a password in the database.
"""

import os
import secrets
from typing import Optional

DEMO_USERNAME = "admin"
DEMO_PASSWORD = "admin"
DEMO_EMAIL = "admin@demo.invalid"

_LOOPBACK = {"127.0.0.1", "::1"}
# ProxyFix rewrites remote_addr from X-Forwarded-For, so any proxy header is refused.
_PROXY_HEADERS = ("X-Forwarded-For", "Forwarded", "X-Real-IP")
_HOSTING_MARKERS = ("RENDER", "VERCEL", "DYNO", "RAILWAY_ENVIRONMENT", "K_SERVICE")


def demo_login_allowed(remote_addr: Optional[str], headers) -> bool:
    if os.environ.get("DEMO_LOGIN") != "1":
        return False
    if os.environ.get("FLASK_ENV") == "production":
        return False
    if any(os.environ.get(name) for name in _HOSTING_MARKERS):
        return False
    if any(headers.get(name) is not None for name in _PROXY_HEADERS):
        return False
    return remote_addr in _LOOPBACK


def demo_user(
    db, username: str, password: str, remote_addr: Optional[str], headers
) -> Optional[dict]:
    """Return the test account for an allowed admin / admin request, else None."""
    if (username, password) != (DEMO_USERNAME, DEMO_PASSWORD):
        return None
    if not demo_login_allowed(remote_addr, headers):
        return None

    user = db.get_user_by_username(DEMO_USERNAME)
    if user is None:
        created = db.create_user(DEMO_USERNAME, DEMO_EMAIL, secrets.token_urlsafe(32))
        if not created:
            return None
        db.update_user_role(created[0], "admin")
        db.set_email_verified(created[0])
        user = db.get_user_by_username(DEMO_USERNAME)

    # Never open a real account that happens to be called "admin".
    if not user or user["email"] != DEMO_EMAIL or not user["is_active"]:
        return None
    return user
