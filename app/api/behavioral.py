"""Behavioral data collection API blueprint."""
from flask import request, current_app
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required
import logging

from app.extensions import get_db, limiter
from app.error_handling import make_error_response
from app.api.helpers import (
    get_session_cached,
    validate_session_context,
    get_current_user_id,
    validate_session_ownership,
)
from app.extended_risk_scorer import score_extended_features
from app.ml_ensemble import score_with_ensemble

logger = logging.getLogger(__name__)

behavioral_ns = Namespace(
    "behavioral", description="Behavioral data collection and calibration"
)

# Maximum number of events accepted per array field to prevent memory pressure
MAX_EVENTS_PER_ARRAY = 500

# ── Swagger models ───────────────────────────────────────────────────────────

behavioral_data_model = behavioral_ns.model(
    "BehavioralDataInput",
    {
        "session_id": fields.String(required=True),
        "type": fields.String(
            enum=["keystroke", "mouse", "extended"], default="keystroke"
        ),
        "event_count": fields.Integer(default=1),
        "events": fields.List(fields.Raw(), description="Raw event array"),
        "extended_features": fields.Raw(
            description="Behavioral Biometrics-style extended signals"
        ),
    },
)

behavioral_response = behavioral_ns.model(
    "BehavioralDataResponse",
    {
        "success": fields.Boolean(),
        "extended_risk": fields.Float(),
        "flags": fields.List(fields.String()),
        "signal_scores": fields.Raw(),
    },
)

calibration_model = behavioral_ns.model(
    "CalibrationInput",
    {
        "session_id": fields.String(required=True),
        "keystroke_data": fields.List(
            fields.Raw(), required=True, description="Calibration keystroke samples"
        ),
    },
)


@behavioral_ns.route("/data")
class BehavioralData(Resource):
    @behavioral_ns.expect(behavioral_data_model)
    @behavioral_ns.response(200, "Data ingested", behavioral_response)
    @limiter.limit("120 per minute")
    @jwt_required()
    def post(self):
        """Ingest aggregated behavioral events + extended Behavioral Biometrics-style signals."""
        payload = request.get_json() or {}
        session_id = payload.get("session_id") or request.cookies.get("session_id")
        data_type = payload.get("type", "keystroke")
        event_count = payload.get("event_count", 1)
        raw_data = payload.get("events") or []
        extended_features = payload.get("extended_features") or {}
        keystroke_events = payload.get("keystroke_events") or []
        touch_events = payload.get("touch_events") or []
        scroll_events = payload.get("scroll_events") or []
        cognitive_events = payload.get("cognitive_events") or []
        motion_events = payload.get("motion_events") or []
        navigation_events = payload.get("navigation_events") or []

        # Enforce max array length to prevent memory pressure
        raw_data = raw_data[:MAX_EVENTS_PER_ARRAY]
        keystroke_events = keystroke_events[:MAX_EVENTS_PER_ARRAY]
        touch_events = touch_events[:MAX_EVENTS_PER_ARRAY]
        scroll_events = scroll_events[:MAX_EVENTS_PER_ARRAY]
        cognitive_events = cognitive_events[:MAX_EVENTS_PER_ARRAY]
        motion_events = motion_events[:MAX_EVENTS_PER_ARRAY]
        navigation_events = navigation_events[:MAX_EVENTS_PER_ARRAY]

        if not session_id:
            return make_error_response("MISSING_SESSION", "Missing session_id", status=400)
        if data_type not in {"keystroke", "mouse", "extended"}:
            data_type = "keystroke"

        session = get_session_cached(session_id)
        if not session:
            return make_error_response("INVALID_SESSION", "Invalid session", status=404)
        if not validate_session_context(session):
            return make_error_response("SESSION_CONTEXT_MISMATCH", "Session context mismatch", status=403)
        err = validate_session_ownership(session)
        if err:
            return err

        try:
            normalized_count = max(1, int(event_count))
        except Exception:
            normalized_count = 1

        ext_result: dict = {}
        ext_risk: float = 0.0
        ext_flags: list = []
        if extended_features:
            try:
                ext_result = score_extended_features(extended_features)
                ext_risk = ext_result.get("extended_risk", 0.0)
                ext_flags = ext_result.get("flags", [])
                if ext_flags:
                    logger.warning(
                        "Extended flags user=%s session=%s: %s",
                        get_current_user_id(),
                        session_id,
                        ext_flags,
                    )
            except Exception as exc:
                logger.error("Extended risk scoring failed: %s", exc)

        db = get_db()
        uid = get_current_user_id()
        db.store_behavioral_data(
            user_id=uid,
            session_id=session_id,
            data_type=data_type,
            features={
                "event_count": normalized_count,
                "extended_risk": ext_risk,
                "touch_events": len(touch_events),
                "scroll_events": len(scroll_events),
                "cognitive_events": len(cognitive_events),
                "motion_events": len(motion_events),
                "nav_events": len(navigation_events),
                **ext_result,
            },
            raw_data={
                "events": raw_data,
                "keystroke_events": keystroke_events[:50],
                "touch_events": touch_events[:20],
                "scroll_events": scroll_events[:20],
                "cognitive_events": cognitive_events[:20],
            },
            confidence_score=float(normalized_count),
            anomaly_score=ext_risk if ext_risk > 0 else None,
        )
        db.log_audit_evidence(
            action="behavioral_ingest",
            status="ok",
            user_id=uid,
            session_id=session_id,
            resource="/api/behavioral-data",
            metadata={
                "data_type": data_type,
                "event_count": normalized_count,
                "extended_risk": ext_risk,
                "flags": ext_flags,
                "signals_available": ext_result.get("signals_available", 0),
            },
            retention_tag="behavioral",
        )
        # ── Behavioral Biometrics Feature Engine (200+ features from all 8 categories) ──
        behavioral_features: dict = {}
        categories = payload.get("categories") or {}
        if categories:
            try:
                from app.behavioral_feature_engine import get_behavioral_engine

                bfe_engine = get_behavioral_engine()
                behavioral_features = bfe_engine.extract(payload)
                # Merge into extended_features for downstream engines
                extended_features.update(behavioral_features)
            except Exception as exc:
                logger.error("Behavioral Biometrics feature engine failed: %s", exc)

        # ── ML Ensemble scoring (6 engines) ──
        ensemble_result: dict = {}
        if extended_features:
            import threading
            import json
            from app.extensions import get_redis
            
            try:
                redis_client = get_redis()
                if redis_client:
                    last_score_str = redis_client.get(f"ensemble_score:{session_id}")
                    if last_score_str:
                        ensemble_result = json.loads(last_score_str)
            except Exception:
                pass

            def _run_ensemble_async(ext_feat, u_id, sess_id, ks_feat):
                try:
                    from app.ml_ensemble import score_with_ensemble
                    res = score_with_ensemble(
                        extended_features=ext_feat,
                        user_id=u_id,
                        keystroke_features=ks_feat,
                    )
                    if res.get("ensemble_flags"):
                        logger.warning(
                            "Ensemble flags user=%s session=%s: %s",
                            u_id,
                            sess_id,
                            res["ensemble_flags"],
                        )
                    rc = get_redis()
                    if rc:
                        rc.setex(f"ensemble_score:{sess_id}", 3600, json.dumps(res))
                except Exception as exc:
                    logger.error("ML ensemble scoring failed: %s", exc)

            threading.Thread(
                target=_run_ensemble_async,
                args=(extended_features, int(uid) if uid else None, session_id, raw_data[0] if raw_data else None)
            ).start()

        return {
            "success": True,
            "extended_risk": ext_risk,
            "flags": ext_flags,
            "signal_scores": {
                "touch": ext_result.get("touch_risk", 0),
                "scroll": ext_result.get("scroll_risk", 0),
                "navigation": ext_result.get("navigation_risk", 0),
                "cognitive": ext_result.get("cognitive_risk", 0),
                "motion": ext_result.get("motion_risk", 0),
            },
            "ensemble": {
                "ensemble_risk": ensemble_result.get("ensemble_risk", 0.0),
                "ensemble_action": ensemble_result.get("ensemble_action", "allow"),
                "duress_score": ensemble_result.get("duress_score", 0.0),
                "liveness_score": ensemble_result.get("liveness_score", 1.0),
                "challenge_risk": ensemble_result.get("challenge_risk", 0.0),
                "device_risk": ensemble_result.get("device_risk", 0.0),
            },
            "Behavioral Biometrics": {
                "feature_count": len(behavioral_features),
                "challenge_analysis": ensemble_result.get("challenge_analysis", {}),
                "device_analysis": ensemble_result.get("device_analysis", {}),
                "composite_analysis": ensemble_result.get("composite_analysis", {}),
                "ensemble_flags": ensemble_result.get("ensemble_flags", []),
            },
        }, 200


@behavioral_ns.route("/calibration/complete")
class CalibrationComplete(Resource):
    @behavioral_ns.expect(calibration_model)
    @behavioral_ns.response(200, "Calibration saved")
    @limiter.limit("10 per minute")
    @jwt_required()
    def post(self):
        """Submit calibration keystroke samples to establish user baseline."""
        payload = request.get_json() or {}
        session_id = payload.get("session_id") or request.cookies.get("session_id")
        keystroke_data = payload.get("keystroke_data") or []
        if not session_id:
            return make_error_response("MISSING_SESSION", "Missing session_id", status=400)
        session = get_session_cached(session_id)
        if not session:
            return make_error_response("INVALID_SESSION", "Invalid session", status=404)
        if not validate_session_context(session):
            return make_error_response("SESSION_CONTEXT_MISMATCH", "Session context mismatch", status=403)
        err = validate_session_ownership(session)
        if err:
            return err
        if not isinstance(keystroke_data, list) or len(keystroke_data) < 1:
            return make_error_response("MISSING_DATA", "Missing keystroke_data", status=400)

        db = get_db()
        uid = get_current_user_id()
        try:
            db.store_behavioral_data(
                user_id=uid,
                session_id=session_id,
                data_type="keystroke",
                features={"calibration": True},
                raw_data={"keystroke_data": keystroke_data},
                confidence_score=None,
                anomaly_score=None,
            )
            db.update_calibration_status(uid, True)
            db.log_audit_evidence(
                action="calibration_complete",
                status="ok",
                user_id=uid,
                session_id=session_id,
                resource="/api/calibration/complete",
                metadata={"sample_count": len(keystroke_data)},
                retention_tag="behavioral",
            )
        except Exception:
            logger.exception("Failed to persist calibration data")
            return make_error_response("CALIBRATION_FAILED", "Calibration persistence failed", status=500)
        return {"success": True}, 200


@behavioral_ns.route("/enrollment/status")
class PassiveEnrollmentStatus(Resource):
    @behavioral_ns.response(200, "Enrollment status")
    @limiter.limit("30 per minute")
    @jwt_required()
    def get(self):
        """Check passive enrollment status — BioCatch-style silent profiling.

        Returns the user's enrollment phase:
        - "collecting": Still gathering behavioral data (sessions 1–N)
        - "ready": Enough data collected, profile being built
        - "active": Behavioral authentication is live

        No explicit calibration step is needed. The system passively
        builds profiles from normal login and session behavior.
        """
        uid = get_current_user_id()
        try:
            from app.models.passive_enrollment import get_enrollment_manager

            enrollment_mgr = get_enrollment_manager()
            status = enrollment_mgr.get_enrollment_status(int(uid))
            profile_summary = enrollment_mgr.get_profile_summary(int(uid))

            return {
                "success": True,
                "enrollment": status,
                "profile": profile_summary,
                "message": (
                    f"Phase: {status['enrollment_phase']}. "
                    f"{status['sessions_completed']}/{status['sessions_required']} sessions completed."
                ),
            }, 200
        except Exception:
            logger.exception("Enrollment status check failed")
            return make_error_response("ENROLLMENT_UNAVAILABLE", "Enrollment status unavailable", status=500)

    @behavioral_ns.response(200, "Enrollment reset")
    @limiter.limit("3 per minute")
    @jwt_required()
    def delete(self):
        """Reset passive enrollment for the current user.

        Used during account recovery or when behavioral profile
        needs to be rebuilt from scratch.
        """
        uid = get_current_user_id()
        try:
            from app.models.passive_enrollment import get_enrollment_manager

            enrollment_mgr = get_enrollment_manager()
            enrollment_mgr.reset_enrollment(int(uid))

            db = get_db()
            db.log_audit_evidence(
                action="enrollment_reset",
                status="ok",
                user_id=uid,
                resource="/api/behavioral/enrollment/status",
                metadata={"reason": "user_or_admin_initiated"},
                retention_tag="security",
            )

            return {
                "success": True,
                "message": "Enrollment reset. New profile will be built passively.",
            }, 200
        except Exception:
            logger.exception("Enrollment reset failed")
            return make_error_response("ENROLLMENT_RESET_FAILED", "Enrollment reset failed", status=500)


@behavioral_ns.route("/enrollment/feature-selection")
class FeatureSelectionStatus(Resource):
    @behavioral_ns.response(200, "Feature selection")
    @limiter.limit("30 per minute")
    @jwt_required()
    def get(self):
        """Get per-user feature selection — BioCatch top-20 unique features.

        Shows which behavioral features are most distinctive for this
        specific user, and their relative weights in authentication scoring.
        """
        uid = get_current_user_id()
        try:
            from app.models.per_user_feature_selector import get_feature_selector

            selector = get_feature_selector()
            selection = selector.get_user_selection(int(uid))

            if not selection:
                return {
                    "success": True,
                    "message": "Feature selection not yet available. Complete enrollment first.",
                    "selection": None,
                }, 200

            return {
                "success": True,
                "selection": selection,
                "message": (
                    f"{len(selection.get('selected_features', []))} features selected "
                    f"(quality: {selection.get('selection_quality', 0):.0%})"
                ),
            }, 200
        except Exception:
            logger.exception("Feature selection check failed")
            return make_error_response("FEATURE_SELECTION_UNAVAILABLE", "Feature selection unavailable", status=500)
