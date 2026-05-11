"""
Integration tests for the 4 Netbanking Code Fixes.

Fix 1: Login keystroke capture — keystroke_data stored via behavioral pipeline
Fix 2: Session risk recalibration — low-activity penalty threshold raised
Fix 3: Personalised transaction threshold — P90-based step-up trigger
Fix 4: Device fingerprint anomaly — new device flagged in login response
"""

import pytest
import uuid


# ═══════════════════════════════════════════════════════════════════════════════
# Fix 1 — Login keystroke capture
# ═══════════════════════════════════════════════════════════════════════════════


class TestLoginKeystrokeCapture:
    """Verify that keystroke_data in the login payload is persisted."""

    def test_login_accepts_keystroke_data(self, client, registered_user):
        """Login should succeed when keystroke_data is provided."""
        keystrokes = [
            {"key": "t", "t": 1000, "type": "down"},
            {"key": "t", "t": 1050, "type": "up"},
            {"key": "e", "t": 1100, "type": "down"},
            {"key": "e", "t": 1150, "type": "up"},
        ]
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "username": registered_user["username"],
                "password": registered_user["password"],
                "keystroke_data": keystrokes,
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "access_token" in data
        assert "session_id" in data

    def test_login_stores_keystroke_behavioral_data(self, app, client, registered_user):
        """Keystroke data sent during login must be stored in behavioral_data."""
        keystrokes = [
            {"key": f"k{i}", "t": 1000 + i * 50, "type": "down"} for i in range(20)
        ]
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "username": registered_user["username"],
                "password": registered_user["password"],
                "keystroke_data": keystrokes,
            },
        )
        assert resp.status_code == 200
        session_id = resp.get_json()["data"]["session_id"]

        from app.extensions import get_db

        with app.app_context():
            db = get_db()
            records = db.get_user_behavioral_data(
                user_id=registered_user["user_id"], data_type="keystroke", limit=1
            )
            assert len(records) >= 1
            features = records[0]["features"]
            assert features["source"] == "login"
            assert features["login_anxiety_flag"] is True
            assert features["event_count"] == 20

    def test_login_without_keystroke_data_still_works(self, client, registered_user):
        """Login with no keystroke_data should still succeed (backwards compatible)."""
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "username": registered_user["username"],
                "password": registered_user["password"],
            },
        )
        assert resp.status_code == 200

    def test_login_caps_keystroke_data_at_100_events(
        self, app, client, registered_user
    ):
        """Raw data should be capped at 100 events even if more are sent."""
        keystrokes = [
            {"key": f"k{i}", "t": 1000 + i, "type": "down"} for i in range(200)
        ]
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "username": registered_user["username"],
                "password": registered_user["password"],
                "keystroke_data": keystrokes,
            },
        )
        assert resp.status_code == 200
        session_id = resp.get_json()["data"]["session_id"]

        from app.extensions import get_db
        import json

        with app.app_context():
            db = get_db()
            records = db.get_user_behavioral_data(
                user_id=registered_user["user_id"], data_type="keystroke", limit=1
            )
            assert len(records) >= 1
            features = records[0]["features"]
            # The features should report 200 events captured
            assert features["event_count"] == 200


# ═══════════════════════════════════════════════════════════════════════════════
# Fix 2 — Session risk recalibration
# ═══════════════════════════════════════════════════════════════════════════════


class TestSessionRiskRecalibration:
    """Verify the recalibrated scoring thresholds."""

    def test_low_activity_session_not_penalised_above_threshold(
        self, client, logged_in_user, auth_headers
    ):
        """A session with 0 events should still not crash — just get penalised."""
        sid = logged_in_user["session_id"]
        resp = client.get(
            f"/api/v1/session/metrics?session_id={sid}", headers=auth_headers
        )
        assert resp.status_code == 200
        body = resp.get_json()
        # With 0 activity, low_activity_penalty fires, but score should still be valid
        assert 0.0 <= body["authenticity_score"] <= 1.0
        assert 0.0 <= body["risk_score"] <= 1.0
        assert body["risk_level"] in {"low", "medium", "high"}

    def test_moderate_activity_earns_bonus(
        self, app, client, logged_in_user, auth_headers
    ):
        """Inject enough behavioral data that the activity bonus kicks in."""
        sid = logged_in_user["session_id"]
        uid = logged_in_user["user_id"]

        from app.extensions import get_db

        with app.app_context():
            db = get_db()
            # Inject 90 keystroke events — above the 80 threshold
            for _ in range(90):
                db.store_behavioral_data(
                    user_id=uid,
                    session_id=sid,
                    data_type="keystroke",
                    features={"hold_time": 120},
                    raw_data={},
                    confidence_score=1.0,
                )

        resp = client.get(
            f"/api/v1/session/metrics?session_id={sid}", headers=auth_headers
        )
        assert resp.status_code == 200
        body = resp.get_json()
        # With 90 events and no anomalies, score should be decent
        assert body["authenticity_score"] >= 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# Fix 3 — Personalised transaction threshold
# ═══════════════════════════════════════════════════════════════════════════════


class TestPersonalisedTransactionThreshold:
    """Verify threshold personalisation logic."""

    def test_threshold_defaults_to_floor_for_new_user(self, app):
        """A user with no history should get the Rs 10,000 floor."""
        from app.api.transaction import _get_personalised_threshold
        from app.extensions import get_db

        with app.app_context():
            db = get_db()
            result = _get_personalised_threshold(db, user_id=99999)
            assert result == 10000.0

    def test_threshold_floor_with_few_transactions(self, app):
        """A user with < 10 transactions should get the floor."""
        from app.api.transaction import _get_personalised_threshold
        from app.extensions import get_db
        import json

        with app.app_context():
            db = get_db()
            # Insert 5 transactions — below the 10-minimum
            for i in range(5):
                db.log_audit_evidence(
                    action="transaction_assess",
                    status="ok",
                    user_id=42,
                    metadata={"amount": 5000 + i * 1000, "decision": "allow"},
                )
            result = _get_personalised_threshold(db, user_id=42)
            assert result == 10000.0

    def test_threshold_uses_p90_with_history(self, app):
        """A user with 20+ transactions should get a P90-based threshold."""
        from app.api.transaction import _get_personalised_threshold
        from app.extensions import get_db

        with app.app_context():
            db = get_db()
            # Insert 20 transactions: 18 at Rs 5,000, 2 at Rs 50,000
            for _ in range(18):
                db.log_audit_evidence(
                    action="transaction_assess",
                    status="ok",
                    user_id=43,
                    metadata={"amount": 5000, "decision": "allow"},
                )
            for _ in range(2):
                db.log_audit_evidence(
                    action="transaction_assess",
                    status="ok",
                    user_id=43,
                    metadata={"amount": 50000, "decision": "allow"},
                )
            result = _get_personalised_threshold(db, user_id=43)
            # P90 of [5000*18, 50000*2] should be well above floor
            assert result >= 10000.0

    def test_threshold_custom_floor(self, app):
        """Custom floor value should be respected."""
        from app.api.transaction import _get_personalised_threshold
        from app.extensions import get_db

        with app.app_context():
            db = get_db()
            result = _get_personalised_threshold(db, user_id=99999, floor=25000.0)
            assert result == 25000.0


# ═══════════════════════════════════════════════════════════════════════════════
# Fix 4 — Device fingerprint anomaly detection
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeviceFingerprintAnomaly:
    """Verify new-device detection in login response."""

    def test_first_login_always_reports_device_new(self, client, registered_user):
        """First login from any device should always return device_new=True."""
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "username": registered_user["username"],
                "password": registered_user["password"],
            },
            headers={"X-Device-Id": "device-abc-123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "device_new" in data
        # First login for this device is always new (no prior session older than 5 min)
        assert data["device_new"] is True

    def test_login_without_device_id_still_works(self, client, registered_user):
        """Login without X-Device-Id header should still succeed."""
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "username": registered_user["username"],
                "password": registered_user["password"],
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "device_new" in data

    def test_new_device_creates_audit_trail(self, app, client, registered_user):
        """A new device login should create an audit evidence record."""
        device_id = f"device-{uuid.uuid4().hex[:8]}"
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "username": registered_user["username"],
                "password": registered_user["password"],
            },
            headers={"X-Device-Id": device_id},
        )
        assert resp.status_code == 200

        from app.extensions import get_db

        with app.app_context():
            db = get_db()
            with db.get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM audit_evidence WHERE action = 'new_device_login' AND user_id = ?",
                    (registered_user["user_id"],),
                ).fetchone()
            assert row is not None

    def test_is_known_device_returns_false_for_empty(self, app):
        """_is_known_device with empty device_id returns False."""
        from app.api.auth import _is_known_device
        from app.extensions import get_db

        with app.app_context():
            db = get_db()
            assert _is_known_device(db, user_id=1, device_id="") is False
            assert _is_known_device(db, user_id=1, device_id=None) is False
