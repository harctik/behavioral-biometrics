"""Behavioral data collection API blueprint."""
from flask import request, current_app
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required
import logging
from pydantic import BaseModel, Field, ValidationError, model_validator
from typing import List, Optional, Any

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


# ── Pydantic Validation Schemas ──────────────────────────────────────────────

class KeystrokeEventSchema(BaseModel):
    model_config = {'extra': 'allow'}
    key: Optional[str] = None
    hold_time: Optional[float] = None
    flight_time: Optional[float] = None
    timestamp: Optional[float] = None
    pressure: Optional[float] = None
    dwell_time: Optional[float] = None
    ts: Optional[float] = None
    count: Optional[int] = None


class MouseEventSchema(BaseModel):
    model_config = {'extra': 'allow'}
    type: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    duration: Optional[float] = None
    timestamp: Optional[float] = None
    button: Optional[int] = None
    ts: Optional[float] = None
    count: Optional[int] = None


class TouchEventSchema(BaseModel):
    model_config = {'extra': 'allow'}
    type: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    pressure: Optional[float] = None
    area: Optional[float] = None
    timestamp: Optional[float] = None
    ts: Optional[float] = None


class ScrollEventSchema(BaseModel):
    model_config = {'extra': 'allow'}
    x: Optional[float] = None
    y: Optional[float] = None
    delta_x: Optional[float] = None
    delta_y: Optional[float] = None
    timestamp: Optional[float] = None
    ts: Optional[float] = None


class MotionEventSchema(BaseModel):
    model_config = {'extra': 'allow'}
    alpha: Optional[float] = None
    beta: Optional[float] = None
    gamma: Optional[float] = None
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    timestamp: Optional[float] = None
    ts: Optional[float] = None


class CognitiveEventSchema(BaseModel):
    model_config = {'extra': 'allow'}
    hesitation_duration: Optional[float] = None
    correction_count: Optional[int] = None
    error_rate: Optional[float] = None
    timestamp: Optional[float] = None
    ts: Optional[float] = None


class NavigationEventSchema(BaseModel):
    model_config = {'extra': 'allow'}
    path: Optional[str] = None
    timestamp: Optional[float] = None
    ts: Optional[float] = None


class ExtendedFeaturesSchema(BaseModel):
    model_config = {'extra': 'allow'}
    touch_event_count: Optional[int] = 0
    touch_force_mean: Optional[float] = 0.5
    touch_area_mean: Optional[float] = 15.0
    touch_velocity_mean: Optional[float] = 0.5
    
    scroll_event_count: Optional[int] = 0
    scroll_velocity_mean: Optional[float] = 1.0
    scroll_velocity_std: Optional[float] = 0.5
    scroll_reversal_rate: Optional[float] = 0.2
    
    nav_dwell_mean: Optional[Any] = 1000.0
    nav_field_revisit_count: Optional[int] = 0
    nav_focus_sequence_entropy: Optional[float] = 1.0
    
    copy_paste_count: Optional[int] = 0
    correction_rate: Optional[float] = 0.1
    tab_switch_count: Optional[int] = 0
    hesitation_count: Optional[int] = 0
    hesitation_duration_mean: Optional[float] = 0.0
    reread_count: Optional[int] = 0
    rapid_submit_detected: Optional[Any] = 0
    
    motion_event_count: Optional[int] = 0
    motion_acc_std: Optional[float] = 1.0


class BehavioralPayloadSchema(BaseModel):
    session_id: str
    type: Optional[str] = "keystroke"
    event_count: Optional[int] = 1
    events: Optional[List[MouseEventSchema]] = Field(default=[])
    extended_features: Optional[ExtendedFeaturesSchema] = Field(default_factory=ExtendedFeaturesSchema)
    keystroke_events: Optional[List[KeystrokeEventSchema]] = Field(default=[])
    touch_events: Optional[List[TouchEventSchema]] = Field(default=[])
    scroll_events: Optional[List[ScrollEventSchema]] = Field(default=[])
    cognitive_events: Optional[List[CognitiveEventSchema]] = Field(default=[])
    motion_events: Optional[List[MotionEventSchema]] = Field(default=[])
    navigation_events: Optional[List[NavigationEventSchema]] = Field(default=[])

    @model_validator(mode="after")
    def limit_arrays(self) -> "BehavioralPayloadSchema":
        for attr in ["events", "keystroke_events", "touch_events", "scroll_events", "cognitive_events", "motion_events", "navigation_events"]:
            lst = getattr(self, attr)
            if lst and len(lst) > 500:
                raise ValueError(f"Array '{attr}' exceeds maximum limit of 500 items")
        return self


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
        try:
            validated_payload = BehavioralPayloadSchema(**request.get_json() or {})
            payload = validated_payload.model_dump()
        except ValidationError as e:
            logger.warning("Behavioral data validation failed: %s", e)
            return make_error_response("VALIDATION_ERROR", str(e), status=400)

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
            # Fallback to DB if Redis is unavailable
            db = get_db()
            db_session = db.get_session(session_id)
            if not db_session:
                return make_error_response("INVALID_SESSION", "Invalid session", status=404)
            session = db_session

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
                "events": raw_data[:500],
                "keystroke_events": keystroke_events[:500],
                "touch_events": touch_events[:500],
                "scroll_events": scroll_events[:500],
                "cognitive_events": cognitive_events[:500],
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
        if data_type == "extended":
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
            import json
            from app.extensions import get_redis
            from app.ml_ensemble import score_with_ensemble

            # Fetch user baseline for takeover detection & feature selection
            baseline = None
            if uid:
                try:
                    from app.models.passive_enrollment import get_enrollment_manager
                    mgr = get_enrollment_manager()
                    profile = mgr.get_profile_summary(int(uid))
                    baseline = profile.get("feature_stats")
                except Exception:
                    pass

            try:
                # Run synchronously to return the latest risk score immediately
                res = score_with_ensemble(
                    extended_features=extended_features,
                    user_id=int(uid) if uid else None,
                    keystroke_features={"events": keystroke_events},
                    mouse_features={"events": raw_data},
                    user_baseline=baseline,
                )
                if res.get("ensemble_flags"):
                    logger.warning(
                        "Ensemble flags user=%s session=%s: %s",
                        uid,
                        session_id,
                        res["ensemble_flags"],
                    )
                ensemble_result = res

                # Cache it for other endpoints (like /session/metrics)
                rc = get_redis()
                if rc:
                    rc.setex(f"ensemble_score:{session_id}", 3600, json.dumps(res))
                    rc.setex(f"behavioral_features:{session_id}", 3600, json.dumps(extended_features))
            except Exception as exc:
                logger.error("ML ensemble scoring failed: %s", exc)

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
            "behavioral_biometrics": {
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
        min_samples = current_app.config.get("CALIBRATION_MIN_SAMPLES", 30)
        if not isinstance(keystroke_data, list) or len(keystroke_data) < min_samples:
            return make_error_response("INSUFFICIENT_DATA", f"Need at least {min_samples} keystrokes for calibration", status=400)

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
