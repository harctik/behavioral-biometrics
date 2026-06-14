"""
Tests for security edge cases identified during the project audit.

Covers:
- T-1: Password reset end-to-end (token generation → confirmation → login with new password)
- T-2: Account lockout enforcement (6th attempt with correct password is rejected)
- CSRF token endpoint
"""
import hashlib
import uuid
import pytest


class TestPasswordResetEndToEnd:
    """Full password reset flow: forgot → token → confirm → login with new password."""

    def test_full_reset_flow(self, client, app):
        """Register, forget password, retrieve token from DB, confirm reset, login."""
        app.config["CSRF_ENABLED"] = False

        # 1. Register a user
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "username": "resetfull",
                "email": "resetfull@example.com",
                "password": "OldPassword123!",
            },
        )
        assert reg.status_code == 200
        user_id = reg.get_json()["data"]["user_id"]

        # 2. Request password reset
        resp = client.post(
            "/api/v1/auth/forgot-password",
            json={"username": "resetfull"},
        )
        assert resp.status_code == 200

        # 3. Retrieve the reset token from DB (simulates email delivery)
        from app.extensions import get_db

        with app.app_context():
            db = get_db()
            with db.get_connection() as conn:
                try:
                    from app.database_pg import DatabaseManager as PostgresDatabaseManager
                    is_pg = isinstance(db, PostgresDatabaseManager)
                except ImportError:
                    is_pg = False
                placeholder = "%s" if is_pg else "?"
                row = conn.execute(
                    f"SELECT token_hash FROM password_reset_tokens WHERE user_id = {placeholder} ORDER BY issued_at DESC LIMIT 1",
                    (user_id,),
                ).fetchone()

        assert row is not None, "No reset token found in DB"
        stored_hash = row["token_hash"]

        # We can't reverse the hash, so we need to find the raw token.
        # In test env, we inject a known token directly.
        raw_token = str(uuid.uuid4())
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        with app.app_context():
            db = get_db()
            import datetime

            db.issue_password_reset_token(
                user_id,
                token_hash,
                datetime.datetime.now() + datetime.timedelta(minutes=15),
            )

        # 4. Confirm password reset with the token
        confirm = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": raw_token, "new_password": "NewPassword456!"},
        )
        assert confirm.status_code == 200, f"Reset confirm failed: {confirm.get_json()}"

        # 5. Login with OLD password should fail
        old_login = client.post(
            "/api/v1/auth/login",
            json={"username": "resetfull", "password": "OldPassword123!"},
        )
        assert old_login.status_code == 401

        # 6. Login with NEW password should succeed
        new_login = client.post(
            "/api/v1/auth/login",
            json={"username": "resetfull", "password": "NewPassword456!"},
        )
        assert new_login.status_code == 200
        assert "access_token" in new_login.get_json()["data"]

    def test_expired_reset_token_rejected(self, client, app):
        """An expired token should be rejected with 400."""
        app.config["CSRF_ENABLED"] = False

        reg = client.post(
            "/api/v1/auth/register",
            json={
                "username": "expireuser",
                "email": "expire@example.com",
                "password": "Password123!",
            },
        )
        user_id = reg.get_json()["data"]["user_id"]

        raw_token = str(uuid.uuid4())
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        # Issue a token that already expired (5 minutes ago)
        from app.extensions import get_db
        import datetime

        with app.app_context():
            db = get_db()
            db.issue_password_reset_token(
                user_id,
                token_hash,
                datetime.datetime.now() - datetime.timedelta(minutes=5),
            )

        confirm = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": raw_token, "new_password": "NewPassword456!"},
        )
        assert confirm.status_code == 400

    def test_used_token_cannot_be_reused(self, client, app):
        """A consumed reset token should not work a second time."""
        app.config["CSRF_ENABLED"] = False

        reg = client.post(
            "/api/v1/auth/register",
            json={
                "username": "reuseuser",
                "email": "reuse@example.com",
                "password": "Password123!",
            },
        )
        user_id = reg.get_json()["data"]["user_id"]

        raw_token = str(uuid.uuid4())
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        from app.extensions import get_db
        import datetime

        with app.app_context():
            db = get_db()
            db.issue_password_reset_token(
                user_id,
                token_hash,
                datetime.datetime.now() + datetime.timedelta(minutes=15),
            )

        # First use should succeed
        resp1 = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": raw_token, "new_password": "NewPassword1!"},
        )
        assert resp1.status_code == 200

        # Second use should fail
        resp2 = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": raw_token, "new_password": "NewPassword2!"},
        )
        assert resp2.status_code == 400


class TestAccountLockoutEnforcement:
    """Verify that accounts are actually locked after too many failed attempts."""

    def test_locked_account_rejects_correct_password(self, client, app):
        """After 5 wrong attempts, even the correct password is rejected."""
        app.config["CSRF_ENABLED"] = False

        password = "CorrectPassword123!"
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "locktest",
                "email": "locktest@example.com",
                "password": password,
            },
        )

        # Trigger 5 failed login attempts
        for i in range(5):
            resp = client.post(
                "/api/v1/auth/login",
                json={"username": "locktest", "password": "WrongPassword!"},
            )
            assert resp.status_code == 401, f"Attempt {i+1} should fail"

        # 6th attempt with CORRECT password should STILL fail (locked)
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "locktest", "password": password},
        )
        assert resp.status_code == 401, (
            "Account should be locked after 5 failed attempts — "
            "correct password must be rejected"
        )

    def test_lockout_resets_after_successful_login(self, client, app):
        """Verify that failed_attempts counter resets to 0 after a successful login."""
        app.config["CSRF_ENABLED"] = False

        password = "CorrectPassword123!"
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "resetcount",
                "email": "resetcount@example.com",
                "password": password,
            },
        )

        # 3 failed attempts (below lockout threshold)
        for _ in range(3):
            client.post(
                "/api/v1/auth/login",
                json={"username": "resetcount", "password": "WrongPassword!"},
            )

        # Successful login should reset the counter
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "resetcount", "password": password},
        )
        assert resp.status_code == 200

        # Another 3 failed attempts should NOT trigger lockout
        # (counter was reset to 0 by the successful login)
        for _ in range(3):
            client.post(
                "/api/v1/auth/login",
                json={"username": "resetcount", "password": "WrongPassword!"},
            )

        # Should still be able to login (only 3 failed, not 5)
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "resetcount", "password": password},
        )
        assert resp.status_code == 200


class TestCSRFTokenEndpoint:
    """Test the new CSRF token API endpoint."""

    def test_csrf_token_endpoint_returns_token(self, client, app):
        """GET /csrf-token should return a signed token."""
        app.config["CSRF_ENABLED"] = False
        resp = client.get("/api/v1/auth/csrf-token")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "csrf_token" in data
        assert len(data["csrf_token"]) > 10  # signed tokens are long

    def test_csrf_token_is_valid(self, client, app):
        """A fetched CSRF token should pass validation on a POST request."""
        # First get a token
        resp = client.get("/api/v1/auth/csrf-token")
        token = resp.get_json()["csrf_token"]

        # Now make an API call with CSRF enabled
        app.config["CSRF_ENABLED"] = True
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "noone", "password": "nopass"},
            headers={"X-CSRF-Token": token},
        )
        # Should get 401 (invalid creds), NOT 403 (CSRF error)
        assert resp.status_code == 401
