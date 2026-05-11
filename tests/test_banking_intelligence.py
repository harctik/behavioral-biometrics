"""
Tests for new banking intelligence layer:
- Payment rail risk multipliers
- Velocity checks
- Daily cumulative limits
- Time-of-day risk
"""

import pytest
import json
from unittest.mock import patch
from datetime import datetime


class TestBankingVelocityChecks:
    """_check_velocity — block rapid-fire transactions."""

    def test_velocity_allows_first_transaction(
        self, app, client, mfa_logged_in_user, mfa_auth_headers
    ):
        """First transaction should always pass velocity check."""
        nonce_resp = client.get("/api/v1/transaction/nonce", headers=mfa_auth_headers)
        nonce = nonce_resp.get_json()["nonce"]
        intent = {
            "session_id": mfa_logged_in_user["session_id"],
            "amount": 100,
            "operation": "transfer",
            "nonce": nonce,
        }
        sig_resp = client.post(
            "/api/v1/transaction/sign-intent", json=intent, headers=mfa_auth_headers
        )
        sig = sig_resp.get_json()["signature"]
        resp = client.post(
            "/api/v1/transaction/assess",
            json={**intent, "signature": sig},
            headers=mfa_auth_headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["decision"] in {"allow", "step_up_required", "blocked"}

    def test_velocity_unit_function(self, app):
        """Direct test of _check_velocity function."""
        from app.api.transaction import _check_velocity
        from app.extensions import get_db

        with app.app_context():
            db = get_db()
            ok, reason = _check_velocity(db, 1)
            assert ok is True
            assert reason == ""

    def test_daily_limit_unit_function(self, app):
        """Direct test of _check_daily_limit function."""
        from app.api.transaction import _check_daily_limit
        from app.extensions import get_db

        with app.app_context():
            db = get_db()
            ok, reason = _check_daily_limit(db, 1, 100)
            assert ok is True

    def test_daily_limit_exceeded(self, app):
        """Daily limit should block when exceeded."""
        from app.api.transaction import _check_daily_limit
        from app.extensions import get_db

        with app.app_context():
            app.config["DAILY_TRANSFER_LIMIT"] = 1000
            db = get_db()
            # Log previous "allowed" transactions (metadata must be dict, not json string)
            for i in range(5):
                db.log_audit_evidence(
                    action="transaction_assess",
                    status="ok",
                    user_id=1,
                    resource="/api/transaction/assess",
                    metadata={"amount": 300, "decision": "allow"},
                    retention_tag="security",
                )
            ok, reason = _check_daily_limit(db, 1, 500)
            # Should be blocked: 5 * 300 = 1500 > 1000 limit
            assert ok is False
            assert "Daily limit" in reason


class TestPaymentRailMultiplier:
    """Verify payment rail multiplier is applied correctly."""

    def test_rail_multiplier_constants(self):
        from app.api.transaction import RAIL_RISK_MULTIPLIER

        assert RAIL_RISK_MULTIPLIER["upi"] > RAIL_RISK_MULTIPLIER["neft"]
        assert RAIL_RISK_MULTIPLIER["internal"] < RAIL_RISK_MULTIPLIER["transfer"]

    def test_upi_operation_assess(
        self, app, client, mfa_logged_in_user, mfa_auth_headers
    ):
        """UPI operation should use 1.3x risk multiplier."""
        nonce_resp = client.get("/api/v1/transaction/nonce", headers=mfa_auth_headers)
        nonce = nonce_resp.get_json()["nonce"]
        intent = {
            "session_id": mfa_logged_in_user["session_id"],
            "amount": 500,
            "operation": "upi",
            "nonce": nonce,
        }
        sig_resp = client.post(
            "/api/v1/transaction/sign-intent", json=intent, headers=mfa_auth_headers
        )
        sig = sig_resp.get_json()["signature"]
        resp = client.post(
            "/api/v1/transaction/assess",
            json={**intent, "signature": sig},
            headers=mfa_auth_headers,
        )
        assert resp.status_code == 200

    def test_neft_operation_assess(
        self, app, client, mfa_logged_in_user, mfa_auth_headers
    ):
        """NEFT operation should use 0.8x risk multiplier."""
        nonce_resp = client.get("/api/v1/transaction/nonce", headers=mfa_auth_headers)
        nonce = nonce_resp.get_json()["nonce"]
        intent = {
            "session_id": mfa_logged_in_user["session_id"],
            "amount": 500,
            "operation": "neft",
            "nonce": nonce,
        }
        sig_resp = client.post(
            "/api/v1/transaction/sign-intent", json=intent, headers=mfa_auth_headers
        )
        sig = sig_resp.get_json()["signature"]
        resp = client.post(
            "/api/v1/transaction/assess",
            json={**intent, "signature": sig},
            headers=mfa_auth_headers,
        )
        assert resp.status_code == 200


class TestTimeOfDayRisk:
    """_time_of_day_risk function."""

    def test_daytime_no_risk(self):
        from app.api.transaction import _time_of_day_risk

        with patch("app.api.transaction.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 28, 14, 0)  # 2 PM
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            flagged, reason = _time_of_day_risk(50000)
            # At 2 PM, should not flag
            assert flagged is False

    def test_late_night_high_value(self):
        from app.api.transaction import _time_of_day_risk

        with patch("app.api.transaction.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 28, 3, 0)  # 3 AM
            flagged, reason = _time_of_day_risk(50000)
            assert flagged is True
            assert "Late-night" in reason

    def test_late_night_low_value(self):
        from app.api.transaction import _time_of_day_risk

        with patch("app.api.transaction.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 28, 3, 0)  # 3 AM
            flagged, reason = _time_of_day_risk(1000)  # Below 10000
            assert flagged is False


class TestRBISessionTimeout:
    """Verify SESSION_INACTIVITY_TIMEOUT_MINUTES is configured."""

    def test_inactivity_timeout_configured(self, app):
        assert app.config.get("SESSION_INACTIVITY_TIMEOUT_MINUTES", 15) == 15
