"""ML model status and feature importance API."""
import logging
import os
import datetime
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required

from app.extensions import get_db, limiter, get_redis
from app.api.helpers import get_current_user_id
from app.ml_ensemble import ENSEMBLE_WEIGHTS

logger = logging.getLogger(__name__)

ml_ns = Namespace("ml", description="Machine Learning model status and diagnostics")

# ── Swagger models ───────────────────────────────────────────────────────────

ml_status_model = ml_ns.model(
    "MLStatus",
    {
        "engines": fields.Raw(description="Status of each ML engine"),
        "ensemble_weights": fields.Raw(description="Current ensemble weight configuration"),
        "total_engines": fields.Integer(),
        "active_engines": fields.Integer(),
        "version": fields.String(),
    },
)


@ml_ns.route("/status")
class MLStatus(Resource):
    @ml_ns.response(200, "ML status", ml_status_model)
    @limiter.limit("30 per minute")
    @jwt_required()
    def get(self):
        """Return status of all ML engines, feature counts, and model versions."""
        engines = {}

        # 1. Cognitive Engine
        try:
            from app.models.cognitive_engine import CognitiveEngine
            engines["cognitive_engine"] = {
                "status": "loaded",
                "features": ["hesitation_analysis", "correction_patterns", "timing_anomalies"],
                "description": "Cognitive behavioral pattern analysis",
            }
        except ImportError:
            engines["cognitive_engine"] = {"status": "unavailable"}

        # 2. Duress Detector
        try:
            from app.models.duress_detector import DuressDetector
            engines["duress_detector"] = {
                "status": "loaded",
                "features": ["speed_variance", "pressure_anomaly", "timing_irregularity"],
                "description": "Coercion and duress detection (DPDP Act 2023)",
            }
        except ImportError:
            engines["duress_detector"] = {"status": "unavailable"}

        # 3. Liveness Detector
        try:
            from app.models.liveness_detector import LivenessDetector
            engines["liveness_detector"] = {
                "status": "loaded",
                "features": ["bot_detection", "replay_detection", "automation_markers"],
                "description": "Bot and replay attack detection",
            }
        except ImportError:
            engines["liveness_detector"] = {"status": "unavailable"}

        # 4. Invisible Challenge Engine
        try:
            from app.models.invisible_challenge_engine import InvisibleChallengeEngine
            engines["invisible_challenge"] = {
                "status": "loaded",
                "features": ["micro_challenges", "behavioral_CAPTCHAs", "implicit_verification"],
                "description": "Patent-style invisible verification (US20150205955A1)",
            }
        except ImportError:
            engines["invisible_challenge"] = {"status": "unavailable"}

        # 5. Device Intelligence
        try:
            from app.models.device_intelligence import DeviceIntelligenceEngine
            engines["device_intelligence"] = {
                "status": "loaded",
                "features": ["RAT_detection", "emulator_detection", "geo_velocity"],
                "description": "Remote access and device anomaly detection",
            }
        except ImportError:
            engines["device_intelligence"] = {"status": "unavailable"}

        # 6. Composite Signal Engine
        try:
            from app.models.composite_signal_engine import CompositeSignalEngine
            engines["composite_signal"] = {
                "status": "loaded",
                "features": ["multi_user_detection", "fraud_patterns", "behavioral_consistency"],
                "description": "Multi-signal fusion and fraud detection",
            }
        except ImportError:
            engines["composite_signal"] = {"status": "unavailable"}

        # 7. GAN Adversarial Detector
        try:
            from app.models.gan_adversarial import GANAdversarialDetector
            engines["gan_adversarial"] = {
                "status": "loaded",
                "features": ["synthetic_detection", "adversarial_patterns", "distribution_analysis"],
                "description": "GAN-based synthetic behavior detection",
            }
        except ImportError:
            engines["gan_adversarial"] = {"status": "unavailable"}

        # 8. Passive Enrollment
        try:
            from app.models.passive_enrollment import PassiveEnrollmentManager
            engines["passive_enrollment"] = {
                "status": "loaded",
                "features": ["silent_profiling", "progressive_trust", "behavioral_baseline"],
                "description": "BioCatch-style silent profile building",
            }
        except ImportError:
            engines["passive_enrollment"] = {"status": "unavailable"}

        # 9. ADWIN Drift Detector
        try:
            from app.models.adwin_drift import ADWINDriftDetector
            engines["adwin_drift"] = {
                "status": "loaded",
                "features": ["concept_drift", "distribution_shift", "model_staleness"],
                "description": "Adaptive windowing concept drift detection",
            }
        except ImportError:
            engines["adwin_drift"] = {"status": "unavailable"}

        # 10. Transaction Baseline
        try:
            from app.models.transaction_baseline import TransactionHistoryBaseline
            engines["transaction_baseline"] = {
                "status": "loaded",
                "features": ["amount_anomaly", "beneficiary_analysis", "timing_patterns"],
                "description": "Transaction history anomaly detection",
            }
        except ImportError:
            engines["transaction_baseline"] = {"status": "unavailable"}

        # 11. Per-User Feature Selector
        try:
            from app.models.per_user_feature_selector import PerUserFeatureSelector
            engines["feature_selector"] = {
                "status": "loaded",
                "features": ["top_20_selection", "user_unique_features", "discriminative_scoring"],
                "description": "Per-user discriminative feature selection",
            }
        except ImportError:
            engines["feature_selector"] = {"status": "unavailable"}

        active_count = sum(1 for e in engines.values() if e.get("status") == "loaded")

        return {
            "engines": engines,
            "ensemble_weights": ENSEMBLE_WEIGHTS,
            "total_engines": len(engines),
            "active_engines": active_count,
            "total_features": sum(len(e.get("features", [])) for e in engines.values()),
            "version": os.environ.get("APP_VERSION", "2.0.0"),
            "uptime_seconds": _get_uptime(),
        }, 200


@ml_ns.route("/feature-importance")
class FeatureImportance(Resource):
    @limiter.limit("30 per minute")
    @jwt_required()
    def get(self):
        """Return top-20 most important features with weights for the current user."""
        uid = get_current_user_id()
        
        # Try per-user feature selection first
        try:
            from app.models.per_user_feature_selector import get_feature_selector
            selector = get_feature_selector()
            selection = selector.get_user_selection(int(uid))
            if selection and selection.get("selected_features"):
                return {
                    "user_id": uid,
                    "features": selection["selected_features"][:20],
                    "selection_quality": selection.get("selection_quality", 0),
                    "source": "per_user_selector",
                }, 200
        except Exception:
            pass

        # Fallback: return ensemble weight distribution
        sorted_weights = sorted(
            ENSEMBLE_WEIGHTS.items(), key=lambda x: x[1], reverse=True
        )
        return {
            "user_id": uid,
            "features": [
                {"name": name, "weight": weight, "rank": i + 1}
                for i, (name, weight) in enumerate(sorted_weights)
            ],
            "source": "ensemble_weights",
        }, 200


# ── Uptime tracker ───────────────────────────────────────────────────────────

_start_time = datetime.datetime.now(datetime.timezone.utc)


def _get_uptime() -> float:
    """Return uptime in seconds since module load."""
    delta = datetime.datetime.now(datetime.timezone.utc) - _start_time
    return round(delta.total_seconds(), 1)
