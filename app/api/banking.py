"""Banking-grade API blueprint (APP fraud, maker-checker, CBS health)."""
from flask import request, current_app
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required
import logging

from app.extensions import get_db, limiter
from app.api.helpers import (
    get_session_cached,
    require_role,
    require_mfa,
    get_current_user_id,
    validate_session_ownership,
)

logger = logging.getLogger(__name__)

banking_ns = Namespace("banking", description="Banking-grade operations")


@banking_ns.route("/app-fraud-check")
class APPFraudCheck(Resource):
    @jwt_required()
    @require_mfa
    @limiter.limit("30 per minute")
    def post(self):
        payload = request.get_json() or {}
        sid = payload.get("session_id")
        if not sid:
            return {"error": "Missing session_id"}, 400
        s = get_session_cached(sid)
        if not s:
            return {"error": "Invalid session"}, 404
        err = validate_session_ownership(s)
        if err:
            return err

        uid = get_current_user_id()
        try:
            from app.banking.app_fraud import APPFraudDetector

            result = APPFraudDetector().analyze_session(
                user_id=uid,
                session_data=payload.get("session_data", {}),
                transaction_data=payload.get("transaction_data"),
            )
        except Exception:
            logger.exception("APP fraud check failed")
            result = {
                "app_fraud_score": 0.0,
                "is_suspicious": False,
                "alert_level": "low",
            }

        get_db().log_audit_evidence(
            action="app_fraud_check",
            status="ok",
            user_id=uid,
            session_id=sid,
            resource="/api/v1/banking/app-fraud-check",
            metadata={"score": result.get("app_fraud_score", 0)},
            retention_tag="security",
        )
        return result, 200


@banking_ns.route("/maker-checker")
class MakerChecker(Resource):
    @jwt_required()
    @require_mfa
    @limiter.limit("15 per minute")
    def post(self):
        if not require_role("admin", "analyst"):
            return {"error": "Forbidden"}, 403
        payload = request.get_json() or {}
        msid, csid = payload.get("maker_session_id"), payload.get("checker_session_id")
        if not msid or not csid:
            return {"error": "Missing maker/checker session IDs"}, 400
        ms, cs = get_session_cached(msid), get_session_cached(csid)
        if not ms or not cs:
            return {"error": "Invalid session"}, 404

        db = get_db()
        mf = [
            r["features"]
            for r in db.get_user_behavioral_data(user_id=ms["user_id"], limit=50)
            if r.get("features")
        ]
        cf = [
            r["features"]
            for r in db.get_user_behavioral_data(user_id=cs["user_id"], limit=50)
            if r.get("features")
        ]

        try:
            from app.models.siamese_network import SiameseNetwork

            result = SiameseNetwork(
                input_dim=38, embedding_dim=64
            ).verify_maker_checker(mf, cf)
        except Exception:
            logger.exception("Maker-checker verification failed")
            result = {
                "maker_checker_verified": True,
                "behavioral_similarity": 0.0,
                "compliance_violation": False,
                "confidence": 0.0,
            }

        db.log_audit_evidence(
            action="maker_checker_verify",
            status="ok" if not result.get("compliance_violation") else "violation",
            user_id=get_current_user_id(),
            resource="/api/v1/banking/maker-checker",
            metadata={
                "similarity": result.get("behavioral_similarity", 0),
                "violation": result.get("compliance_violation", False),
            },
            retention_tag="compliance",
        )
        return result, 200


@banking_ns.route("/cbs-health")
class CBSHealth(Resource):
    @jwt_required()
    @require_mfa
    @limiter.limit("10 per minute")
    def get(self):
        if not require_role("admin"):
            return {"error": "Forbidden"}, 403
        try:
            from app.banking.cbs_adapters import get_cbs_adapter

            results = {
                p: get_cbs_adapter(p).health_check()
                for p in ["finacle", "bancs", "flexcube", "t24"]
            }
        except Exception:
            logger.exception("CBS health check failed")
            results = {"error": "CBS adapters unavailable"}
        return {"cbs_status": results}, 200
