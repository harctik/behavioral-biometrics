"""Compliance & privacy API blueprint."""
from flask import request
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required
import logging

from app.extensions import get_db, limiter
from app.api.helpers import (
    get_session_cached,
    require_role,
    require_aal,
    get_current_user_id,
    validate_session_ownership,
)

logger = logging.getLogger(__name__)

compliance_ns = Namespace("compliance", description="Compliance and privacy")


@compliance_ns.route("/dsar")
class ComplianceDSAR(Resource):
    @jwt_required()
    @limiter.limit("10 per minute")
    def get(self):
        sid = request.args.get("session_id")
        if not sid:
            return {"error": "Missing session_id"}, 400
        s = get_session_cached(sid)
        if not s:
            return {"error": "Invalid session"}, 404
        err = validate_session_ownership(s)
        if err:
            return err

        db = get_db()
        uid = get_current_user_id()
        user = db.get_user_by_id(uid)
        behavioral = db.get_user_behavioral_data(user_id=uid, limit=200)
        evidence = db.get_audit_evidence(user_id=uid, limit=200)
        for row in behavioral:
            row.pop("raw_data", None)
        payload = {
            "user": {
                "user_id": user.get("user_id"),
                "username": user.get("username"),
                "email": user.get("email"),
                "created_at": user.get("created_at"),
                "last_login": user.get("last_login"),
            },
            "behavioral_records": behavioral,
            "audit_evidence": evidence,
            "export_scope": "redacted",
        }
        db.log_audit_evidence(
            action="dsar_export",
            status="ok",
            user_id=uid,
            session_id=sid,
            resource="/api/compliance/dsar",
            metadata={
                "behavioral_records": len(behavioral),
                "evidence_records": len(evidence),
            },
            retention_tag="compliance",
        )
        return payload, 200


@compliance_ns.route("/anonymize")
class ComplianceAnonymize(Resource):
    @jwt_required()
    @limiter.limit("5 per minute")
    def post(self):
        payload = request.get_json() or {}
        sid = payload.get("session_id")
        if not sid:
            return {"error": "Missing session_id"}, 400
        s = get_session_cached(sid)
        if not s:
            return {"error": "Invalid session"}, 404
        if not require_aal(s, "mfa"):
            return {"error": "MFA required"}, 403
        err = validate_session_ownership(s)
        if err:
            return err
        db = get_db()
        uid = get_current_user_id()
        db.anonymize_user(uid)
        db.end_session(sid)
        db.log_audit_evidence(
            action="account_anonymized",
            status="ok",
            user_id=uid,
            session_id=sid,
            resource="/api/compliance/anonymize",
            retention_tag="compliance",
        )
        return {"success": True}, 200


@compliance_ns.route("/report")
class ComplianceReport(Resource):
    @jwt_required()
    @limiter.limit("10 per minute")
    def get(self):
        if not require_role("admin", "analyst"):
            return {"error": "Forbidden"}, 403
        report_type = request.args.get("type", "rbi")
        db = get_db()
        try:
            from app.compliance import ComplianceReportGenerator

            gen = ComplianceReportGenerator(db)
            if report_type == "rbi":
                report = gen.generate_rbi_report()
            elif report_type == "pci_dss":
                report = gen.generate_pci_dss_evidence()
            elif report_type == "certin":
                report = gen.generate_certin_notification(
                    incident_type="behavioral_anomaly",
                    affected_users=0,
                    details={"description": "Routine compliance check"},
                )
            else:
                return {"error": f"Unknown report type: {report_type}"}, 400
        except Exception:
            logger.exception("Compliance report generation failed")
            return {"error": "Report generation failed"}, 500

        db.log_audit_evidence(
            action="compliance_report_generated",
            status="ok",
            user_id=get_current_user_id(),
            resource="/api/v1/compliance/report",
            metadata={"report_type": report_type},
            retention_tag="compliance",
        )
        return report, 200
