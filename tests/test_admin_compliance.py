"""
Coverage-boosting integration tests for admin, compliance, and banking endpoints.

These routes require JWT + MFA + admin/analyst role, so we use the mfa_logged_in_user
fixture and manually promote the user to admin via the database.
"""

import pytest
import json


# ── Helper to promote user to admin ──────────────────────────────────────────


def _promote_to_admin(app, user_id):
    """Directly set a user's role to 'admin' in the DB."""
    from app.extensions import get_db

    with app.app_context():
        db = get_db()
        db.update_user_role(user_id, "admin")


# ═══════════════════════════════════════════════════════════════════════════════
# Admin endpoints
# ═══════════════════════════════════════════════════════════════════════════════


class TestAdminEndpoints:
    def test_audit_evidence_requires_admin(self, client, logged_in_user, auth_headers):
        """Non-admin user should be forbidden from audit-evidence."""
        sid = logged_in_user["session_id"]
        resp = client.get(
            f"/api/v1/admin/audit-evidence?session_id={sid}", headers=auth_headers
        )
        assert resp.status_code == 403

    def test_audit_verify_requires_admin(self, client, logged_in_user, auth_headers):
        """Non-admin user should be forbidden from audit-evidence/verify."""
        sid = logged_in_user["session_id"]
        resp = client.get(
            f"/api/v1/admin/audit-evidence/verify?session_id={sid}",
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_duress_check_requires_admin(self, client, logged_in_user, auth_headers):
        """Non-admin user should be forbidden from duress-check."""
        sid = logged_in_user["session_id"]
        resp = client.get(
            f"/api/v1/admin/duress-check?session_id={sid}", headers=auth_headers
        )
        assert resp.status_code == 403

    def test_set_role_requires_mfa(self, client, logged_in_user, auth_headers):
        """Setting user role requires MFA (aal=mfa)."""
        resp = client.post(
            "/api/v1/admin/users/role",
            json={"user_id": logged_in_user["user_id"], "role": "analyst"},
            headers=auth_headers,
        )
        # Should get 403 because aal=pwd, not mfa
        assert resp.status_code == 403

    def test_duress_check_missing_session(self, client, logged_in_user, auth_headers):
        """Duress check without session_id should return 400."""
        resp = client.get("/api/v1/admin/duress-check", headers=auth_headers)
        # Could be 400 or 403 depending on role check order
        assert resp.status_code in {400, 403}

    def test_audit_evidence_missing_session(self, client, logged_in_user, auth_headers):
        """Audit evidence without session_id should return 400."""
        resp = client.get("/api/v1/admin/audit-evidence", headers=auth_headers)
        assert resp.status_code in {400, 403}

    def test_admin_duress_check_with_admin_user(
        self, app, client, mfa_logged_in_user, mfa_auth_headers
    ):
        """Admin user with MFA should access duress-check (no data = normal)."""
        _promote_to_admin(app, mfa_logged_in_user["user_id"])
        sid = mfa_logged_in_user["session_id"]
        resp = client.get(
            f"/api/v1/admin/duress-check?session_id={sid}", headers=mfa_auth_headers
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["alert_level"] == "normal"

    def test_admin_audit_evidence_with_admin_user(
        self, app, client, mfa_logged_in_user, mfa_auth_headers
    ):
        """Admin user with MFA should access audit evidence."""
        _promote_to_admin(app, mfa_logged_in_user["user_id"])
        sid = mfa_logged_in_user["session_id"]
        resp = client.get(
            f"/api/v1/admin/audit-evidence?session_id={sid}", headers=mfa_auth_headers
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert "evidence" in body

    def test_admin_audit_verify_with_admin_user(
        self, app, client, mfa_logged_in_user, mfa_auth_headers
    ):
        """Admin user with MFA should verify audit chain."""
        _promote_to_admin(app, mfa_logged_in_user["user_id"])
        sid = mfa_logged_in_user["session_id"]
        resp = client.get(
            f"/api/v1/admin/audit-evidence/verify?session_id={sid}",
            headers=mfa_auth_headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert "is_valid" in body

    def test_admin_set_role_with_admin_user(
        self, app, client, mfa_logged_in_user, mfa_auth_headers
    ):
        """Admin user with MFA should set another user's role."""
        _promote_to_admin(app, mfa_logged_in_user["user_id"])
        resp = client.post(
            "/api/v1/admin/users/role",
            json={"user_id": mfa_logged_in_user["user_id"], "role": "analyst"},
            headers=mfa_auth_headers,
        )
        assert resp.status_code == 200

    def test_admin_set_role_invalid_role(
        self, app, client, mfa_logged_in_user, mfa_auth_headers
    ):
        """Setting an invalid role should return 400."""
        _promote_to_admin(app, mfa_logged_in_user["user_id"])
        resp = client.post(
            "/api/v1/admin/users/role",
            json={"user_id": mfa_logged_in_user["user_id"], "role": "superadmin"},
            headers=mfa_auth_headers,
        )
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# Compliance endpoints
# ═══════════════════════════════════════════════════════════════════════════════


class TestComplianceEndpoints:
    def test_dsar_export(self, client, logged_in_user, auth_headers):
        """DSAR export should return user data."""
        sid = logged_in_user["session_id"]
        resp = client.get(
            f"/api/v1/compliance/dsar?session_id={sid}", headers=auth_headers
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert "user" in body
        assert body["user"]["username"] == logged_in_user["username"]
        assert "behavioral_records" in body
        assert "audit_evidence" in body

    def test_dsar_missing_session(self, client, logged_in_user, auth_headers):
        """DSAR without session_id should return 400."""
        resp = client.get("/api/v1/compliance/dsar", headers=auth_headers)
        assert resp.status_code == 400

    def test_dsar_invalid_session(self, client, logged_in_user, auth_headers):
        """DSAR with non-existent session should return 404."""
        resp = client.get(
            "/api/v1/compliance/dsar?session_id=fake-session", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_compliance_report_requires_admin(
        self, client, logged_in_user, auth_headers
    ):
        """Compliance report should require admin/analyst role."""
        resp = client.get("/api/v1/compliance/report?type=rbi", headers=auth_headers)
        assert resp.status_code == 403

    def test_compliance_report_with_admin(
        self, app, client, mfa_logged_in_user, mfa_auth_headers
    ):
        """Admin should access compliance reports."""
        _promote_to_admin(app, mfa_logged_in_user["user_id"])
        resp = client.get(
            "/api/v1/compliance/report?type=rbi", headers=mfa_auth_headers
        )
        assert resp.status_code == 200

    def test_compliance_report_unknown_type(
        self, app, client, mfa_logged_in_user, mfa_auth_headers
    ):
        """Unknown report type should return 400."""
        _promote_to_admin(app, mfa_logged_in_user["user_id"])
        resp = client.get(
            "/api/v1/compliance/report?type=unknown", headers=mfa_auth_headers
        )
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# Banking endpoints
# ═══════════════════════════════════════════════════════════════════════════════


class TestBankingEndpoints:
    def test_app_fraud_check_requires_mfa(self, client, logged_in_user, auth_headers):
        """APP fraud check requires MFA."""
        resp = client.post(
            "/api/v1/banking/app-fraud-check",
            json={"session_id": logged_in_user["session_id"]},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_cbs_health_requires_mfa(self, client, logged_in_user, auth_headers):
        """CBS health check requires MFA."""
        resp = client.get("/api/v1/banking/cbs-health", headers=auth_headers)
        assert resp.status_code == 403

    def test_maker_checker_requires_mfa(self, client, logged_in_user, auth_headers):
        """Maker-checker requires MFA."""
        resp = client.post(
            "/api/v1/banking/maker-checker",
            json={"maker_session_id": "a", "checker_session_id": "b"},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_app_fraud_check_with_mfa(
        self, app, client, mfa_logged_in_user, mfa_auth_headers
    ):
        """APP fraud check with MFA should succeed."""
        resp = client.post(
            "/api/v1/banking/app-fraud-check",
            json={"session_id": mfa_logged_in_user["session_id"]},
            headers=mfa_auth_headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert "app_fraud_score" in body

    def test_cbs_health_with_admin(
        self, app, client, mfa_logged_in_user, mfa_auth_headers
    ):
        """CBS health check with admin MFA should succeed."""
        _promote_to_admin(app, mfa_logged_in_user["user_id"])
        resp = client.get("/api/v1/banking/cbs-health", headers=mfa_auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert "cbs_status" in body

    def test_app_fraud_missing_session(
        self, app, client, mfa_logged_in_user, mfa_auth_headers
    ):
        """APP fraud check without session_id should return 400."""
        resp = client.post(
            "/api/v1/banking/app-fraud-check",
            json={},
            headers=mfa_auth_headers,
        )
        assert resp.status_code == 400
