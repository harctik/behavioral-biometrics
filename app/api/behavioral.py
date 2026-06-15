"""Behavioral data collection API blueprint."""
from flask import request, current_app
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required
import logging
from pydantic import ValidationError
from typing import Optional, Any
from app.schemas.behavioral_schemas import BehavioralPayloadSchema

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
        mouse_events_list = payload.get("mouse_events") or raw_data  # Frontend sends mouse_events, legacy sends events
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
        mouse_events_list = mouse_events_list[:MAX_EVENTS_PER_ARRAY]
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

        # Merge raw extended features with scoring results so ML engines
        # can access actual feature values (nav_dwell_mean, scroll_velocity_std,
        # hesitation_count, etc.) for bot/duress/cognitive detection.
        stored_features = {
            "event_count": normalized_count,
            "extended_risk": ext_risk,
            "touch_events": len(touch_events),
            "scroll_events": len(scroll_events),
            "cognitive_events": len(cognitive_events),
            "motion_events": len(motion_events),
            "nav_events": len(navigation_events),
            "keystroke_event_count": len(keystroke_events),
            "mouse_event_count": len(mouse_events_list),
        }
        # Include the actual frontend-computed extended features
        if extended_features and isinstance(extended_features, dict):
            stored_features.update(extended_features)
        # Overlay scoring results (higher priority)
        if ext_result and isinstance(ext_result, dict):
            stored_features.update(ext_result)

        db.store_behavioral_data(
            user_id=uid,
            session_id=session_id,
            data_type=data_type,
            features=stored_features,
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

        # ── Granular session-aware storage (new tables) ──────────────────
        try:
            # Store individual keystroke events for per-session analysis
            if keystroke_events:
                db.store_keystroke_events(
                    session_id=session_id,
                    user_id=uid,
                    events=keystroke_events,
                    context="SESSION",
                )
            # Store mouse events for trajectory analysis
            if mouse_events_list:
                db.store_mouse_events(
                    session_id=session_id,
                    user_id=uid,
                    events=mouse_events_list,
                    context="SESSION",
                )
        except Exception as exc:
            logger.warning("Granular event storage failed: %s", exc)

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
                # Merge per-key/digraph profile into keystroke features for ensemble digraph matching
                ks_feats = {"events": keystroke_events}
                incoming_profile = payload.get("keystroke_profile") or {}
                if incoming_profile:
                    ks_feats["per_key_hold"] = incoming_profile.get("per_key_hold", {})
                    ks_feats["per_digraph_flight"] = incoming_profile.get("per_digraph_flight", {})

                # Run synchronously to return the latest risk score immediately
                res = score_with_ensemble(
                    extended_features=extended_features,
                    user_id=int(uid) if uid else None,
                    keystroke_features=ks_feats,
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
    @behavioral_ns.response(200, "Calibration saved and training dispatched")
    @limiter.limit("10 per minute")
    @jwt_required()
    def post(self):
        """Submit calibration keystroke samples and trigger ML model training.

        This is the most critical endpoint in the system. It:
        1. Validates and stores the raw keystroke calibration data
        2. Extracts 230+ behavioral features via BehavioralFeatureEngine
        3. Dispatches async ML training across all 15 engines:
           - OC-SVM, Isolation Forest, k-NN, Passive-Aggressive
           - Autoencoder, Transformer (4-head), GRU
           - Siamese Network, SimCLR contrastive
           - GAN discriminator, Duress baseline
        4. Generates synthetic impostor data for supervised training
        5. Calibrates Bayesian fusion weights
        6. Logs the full training run to the audit trail

        The training runs asynchronously via Celery so the HTTP response
        returns immediately (~100ms) while models train in the background.
        """
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

        # ── Step 1: Store raw calibration data ────────────────────────────
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
        except Exception:
            logger.exception("Failed to persist calibration data")
            return make_error_response("CALIBRATION_FAILED", "Calibration persistence failed", status=500)

        # ── Step 2: Extract features and store as behavioral profile ──────
        training_dispatched = False
        training_mode = "none"
        training_task_id = None
        training_report = None

        try:
            from app.behavioral_feature_engine import get_behavioral_engine
            engine = get_behavioral_engine()

            # Convert raw keystroke data into feature-engineered samples
            feature_samples = []
            for ks_event in keystroke_data:
                if isinstance(ks_event, dict):
                    feat = engine.extract({
                        "extended_features": ks_event,
                        "categories": {},
                        "device_context": payload.get("device_context", {}),
                    })
                    feature_samples.append(feat)

            if feature_samples:
                # Store extracted features for training pipeline
                db.store_behavioral_data(
                    user_id=uid,
                    session_id=session_id,
                    data_type="extended",
                    features=feature_samples[-1],  # Latest snapshot
                    raw_data=None,
                    confidence_score=None,
                    anomaly_score=None,
                )

            # ── Step 3: Dispatch async ML training ────────────────────────
            try:
                from app.tasks import train_user_models_async
                task = train_user_models_async.delay(uid)
                training_dispatched = True
                training_mode = "async_celery"
                training_task_id = task.id
                logger.info(
                    "ML training dispatched via Celery for user %d (task=%s)",
                    uid, task.id,
                )
            except Exception:
                # Celery not available — fall back to synchronous training
                logger.warning(
                    "Celery unavailable; falling back to synchronous training for user %d",
                    uid,
                )
                try:
                    from app.training_orchestrator import TrainingOrchestrator
                    orchestrator = TrainingOrchestrator(db=db, models_dir="models")
                    report = orchestrator.train_all(user_id=uid)
                    training_dispatched = True
                    training_mode = "synchronous"
                    training_report = {
                        "models_trained": len(report.models_trained),
                        "models_failed": len(report.models_failed),
                        "duration_seconds": report.duration_seconds,
                        "enrollment_phase": report.enrollment_phase,
                    }
                except Exception:
                    logger.exception("Synchronous training also failed for user %d", uid)
                    training_mode = "failed"

        except Exception:
            logger.exception("Feature extraction failed for user %d", uid)

        # ── Step 4: Update calibration status + audit log ─────────────────
        try:
            db.update_calibration_status(uid, True)
            db.log_audit_evidence(
                action="calibration_complete",
                status="ok",
                user_id=uid,
                session_id=session_id,
                resource="/api/calibration/complete",
                metadata={
                    "sample_count": len(keystroke_data),
                    "features_extracted": len(feature_samples) if 'feature_samples' in dir() else 0,
                    "training_mode": training_mode,
                    "training_task_id": training_task_id,
                },
                retention_tag="behavioral",
            )
        except Exception:
            logger.exception("Failed to update calibration status for user %d", uid)

        response = {
            "success": True,
            "training": {
                "dispatched": training_dispatched,
                "mode": training_mode,
                "task_id": training_task_id,
            },
        }
        if training_report:
            response["training"]["report"] = training_report

        return response, 200


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


@behavioral_ns.route("/training/trigger")
class TrainingTrigger(Resource):
    @behavioral_ns.response(200, "Training dispatched")
    @limiter.limit("3 per minute")
    @jwt_required()
    def post(self):
        """Trigger on-demand ML model retraining for the current user.

        Use this when:
        - The user has accumulated new behavioral data since last training
        - After a significant change in user behavior (new device, injury, etc.)
        - Admin-initiated retraining for a specific user

        Training runs asynchronously — check /training/status for results.
        """
        uid = get_current_user_id()
        db = get_db()
        payload = request.get_json() or {}
        force_phase = payload.get("force_phase")  # Optional: bootstrap/building/mature

        try:
            from app.tasks import train_user_models_async
            task = train_user_models_async.delay(uid, force_phase=force_phase)

            db.log_audit_evidence(
                action="training_triggered",
                status="ok",
                user_id=uid,
                metadata={
                    "task_id": task.id,
                    "force_phase": force_phase,
                    "trigger": "user_api",
                },
                retention_tag="ml_training",
            )

            return {
                "success": True,
                "task_id": task.id,
                "message": "ML training dispatched asynchronously. Check /training/status for results.",
            }, 200
        except Exception:
            # Celery unavailable — try synchronous fallback
            logger.warning("Celery unavailable; attempting synchronous training for user %d", uid)
            try:
                from app.training_orchestrator import TrainingOrchestrator
                orchestrator = TrainingOrchestrator(db=db, models_dir="models")
                report = orchestrator.train_all(user_id=uid, force_phase=force_phase)
                return {
                    "success": True,
                    "mode": "synchronous",
                    "report": {
                        "models_trained": len(report.models_trained),
                        "models_failed": len(report.models_failed),
                        "duration_seconds": report.duration_seconds,
                        "enrollment_phase": report.enrollment_phase,
                        "data_hash": report.data_hash[:16],
                        "model_details": report.models_trained,
                    },
                }, 200
            except Exception:
                logger.exception("Training failed for user %d", uid)
                return make_error_response(
                    "TRAINING_FAILED", "ML model training failed", status=500
                )


@behavioral_ns.route("/training/status")
class TrainingStatus(Resource):
    @behavioral_ns.response(200, "Training status")
    @limiter.limit("30 per minute")
    @jwt_required()
    def get(self):
        """Check ML training status and model metadata for the current user.

        Returns:
        - Current model version and training date
        - Per-model accuracy metrics
        - Enrollment phase (bootstrap/building/mature)
        - Training history from audit trail
        """
        uid = get_current_user_id()
        db = get_db()

        try:
            # Get model metadata
            model_meta = db.get_model_metadata(uid)

            # Get recent training audit entries
            audit_entries = db.get_audit_evidence(
                user_id=uid, action="ml_training_complete", limit=5
            )
            training_history = []
            for entry in (audit_entries or []):
                meta = entry.get("metadata")
                if isinstance(meta, str):
                    import json
                    try:
                        meta = json.loads(meta)
                    except (json.JSONDecodeError, TypeError):
                        meta = {}
                training_history.append({
                    "timestamp": entry.get("created_at"),
                    "models_trained": meta.get("models_trained_count", 0) if meta else 0,
                    "duration_seconds": meta.get("duration_seconds", 0) if meta else 0,
                    "enrollment_phase": meta.get("enrollment_phase", "unknown") if meta else "unknown",
                })

            return {
                "success": True,
                "model_metadata": model_meta,
                "training_history": training_history,
                "models_available": bool(model_meta),
            }, 200
        except Exception:
            logger.exception("Training status check failed for user %d", uid)
            return make_error_response(
                "TRAINING_STATUS_UNAVAILABLE", "Training status unavailable", status=500
            )

