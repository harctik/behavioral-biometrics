"""
ML Ensemble Integration Layer.

Bridges the gap between the ML models (CognitiveEngine, DuressDetector,
LivenessDetector, InvisibleChallengeEngine, DeviceIntelligence,
CompositeSignalEngine, PassiveEnrollment, PerUserFeatureSelector,
TransactionBaseline, ADWIN drift) and the API scoring pipeline.

This module provides a single ``score_with_ensemble()`` function that:
1. Runs CognitiveEngine analysis on extended features
2. Runs DuressDetector if user baseline exists
3. Runs LivenessDetector for bot detection
4. Runs InvisibleChallengeEngine (Patent US20150205955A1)
5. Runs DeviceIntelligenceEngine (RAT, emulator, geo-velocity)
6. Runs CompositeSignalEngine (lie detection, multi-user, fraud patterns)
7. Runs PassiveEnrollmentManager (BioCatch-style silent profile building)
8. Runs PerUserFeatureSelector (top-20 unique features per user)
9. Runs TransactionHistoryBaseline (amount/beneficiary/timing anomaly)
10. Fuses all 9 engine signals into a unified risk score
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Configurable ensemble weights — sum to 1.0.
# Override at runtime via ``ENSEMBLE_WEIGHTS.update(...)`` for auto-calibration.
ENSEMBLE_WEIGHTS: Dict[str, float] = {
    "cognitive":           0.14,
    "duress":              0.14,
    "liveness":            0.10,
    "invisible_challenge": 0.09,
    "device_intelligence": 0.07,
    "composite_fraud":     0.05,
    "passive_enrollment":  0.07,
    "feature_selection":   0.09,
    "transaction":         0.10,
    "replay_detection":    0.10,
    "concept_drift":       0.05,
}

# Lazy singletons — avoids import-time cost for numpy/scipy
_cognitive_engine = None
_duress_detector = None
_liveness_detector = None

import threading
_cognitive_lock = threading.Lock()
_duress_lock = threading.Lock()
_liveness_lock = threading.Lock()


def _get_cognitive_engine():
    global _cognitive_engine
    if _cognitive_engine is None:
        with _cognitive_lock:
            if _cognitive_engine is None:
                from app.models.cognitive_engine import CognitiveEngine
                _cognitive_engine = CognitiveEngine()
    return _cognitive_engine


def _get_duress_detector():
    global _duress_detector
    if _duress_detector is None:
        with _duress_lock:
            if _duress_detector is None:
                from app.models.duress_detector import DuressDetector
                _duress_detector = DuressDetector()
    return _duress_detector


def _get_liveness_detector():
    global _liveness_detector
    if _liveness_detector is None:
        with _liveness_lock:
            if _liveness_detector is None:
                from app.models.liveness_detector import LivenessDetector
                _liveness_detector = LivenessDetector()
    return _liveness_detector


def score_with_ensemble(
    extended_features: Dict[str, Any],
    user_id: Optional[int] = None,
    session_history: Optional[List[Dict]] = None,
    user_baseline: Optional[Dict[str, Any]] = None,
    keystroke_features: Optional[Dict] = None,
    mouse_features: Optional[Dict] = None,
    transaction_amount: Optional[float] = None,
    beneficiary_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the full ML ensemble (9 engines) and return a unified risk assessment.

    Engines:
      1. CognitiveEngine (duress, APP fraud, takeover, bot)
      2. DuressDetector (43-feature stress detection)
      3. LivenessDetector (bot vs human liveness)
      4. InvisibleChallengeEngine (Patent US20150205955A1)
      5. DeviceIntelligenceEngine (RAT, emulator, geo-velocity)
      6. CompositeSignalEngine (lie detection, multi-user, fraud patterns)
      7. PassiveEnrollmentManager (BioCatch-style silent enrollment)
      8. PerUserFeatureSelector (top-20 unique features per user)
      9. TransactionHistoryBaseline (amount/beneficiary/timing anomaly)

    Returns:
        {
            "ensemble_risk": float,
            "cognitive_analysis": dict|None,
            "duress_score": float,
            "liveness_score": float,
            "challenge_risk": float,
            "device_risk": float,
            "enrollment_status": dict|None,
            "feature_selection": dict|None,
            "transaction_risk": dict|None,
            "weighted_match_score": float,
            "ensemble_action": str,
            "ensemble_flags": list[str],
        }
    """
    result = {
        "ensemble_risk": 0.0,
        "cognitive_analysis": None,
        "duress_score": 0.0,
        "liveness_score": 1.0,
        "challenge_risk": 0.0,
        "device_risk": 0.0,
        "enrollment_status": None,
        "feature_selection": None,
        "transaction_risk": None,
        "weighted_match_score": 0.0,
        "ensemble_action": "allow",
        "ensemble_flags": [],
    }

    # ── 1. CognitiveEngine ─────────────────────────────────────────────
    cognitive = None
    try:
        engine = _get_cognitive_engine()
        cognitive = engine.analyze(
            extended_features=extended_features or {},
            session_history=session_history,
            baseline=user_baseline,
        )
        result["cognitive_analysis"] = cognitive
    except Exception as exc:
        logger.warning("CognitiveEngine failed: %s", exc)

    # ── 2. DuressDetector ──────────────────────────────────────────────
    duress_score = 0.0
    if user_id and (keystroke_features or mouse_features):
        try:
            detector = _get_duress_detector()
            duress_result = detector.compute_duress_score(
                user_id=user_id,
                keystroke_features=keystroke_features or {},
                mouse_features=mouse_features or {},
            )
            duress_score = duress_result.get("duress_score", 0.0)
            if duress_score > 0.5:
                result["ensemble_flags"].append(
                    f"duress:score={duress_score:.2f} alert={duress_result.get('alert_level', 'unknown')}"
                )
        except Exception as exc:
            logger.warning("DuressDetector failed: %s", exc)

    result["duress_score"] = duress_score

    # ── 3. LivenessDetector ────────────────────────────────────────────
    liveness_score = 1.0
    if extended_features:
        try:
            detector = _get_liveness_detector()
            liveness = detector.analyze(extended_features)
            liveness_score = liveness.get("liveness_score", 1.0)
            if liveness_score < 0.5:
                result["ensemble_flags"].append(
                    f"liveness:low_score={liveness_score:.2f}"
                )
        except Exception as exc:
            logger.warning("LivenessDetector failed: %s", exc)

    result["liveness_score"] = liveness_score

    # ── 4. Invisible Challenge Engine (Patent US20150205955A1) ─────────
    challenge_risk = 0.0
    challenge_result: dict = {}
    if extended_features:
        try:
            from app.models.invisible_challenge_engine import get_challenge_engine

            ch_engine = get_challenge_engine()
            challenge_result = ch_engine.score_responses(
                challenge_features=extended_features,
                user_id=int(user_id) if user_id else None,
            )
            challenge_risk = challenge_result.get("challenge_risk", 0.0)
            if challenge_result.get("flags"):
                result["ensemble_flags"].extend(challenge_result["flags"])
        except Exception as exc:
            logger.warning("InvisibleChallengeEngine failed: %s", exc)

    result["challenge_risk"] = challenge_risk
    result["challenge_analysis"] = challenge_result

    # ── 5. Device Intelligence Engine ──────────────────────────────────
    device_risk = 0.0
    device_result: dict = {}
    if extended_features:
        try:
            from app.models.device_intelligence import get_device_engine

            dev_engine = get_device_engine()
            device_result = dev_engine.analyze(
                device_features=extended_features,
                user_id=int(user_id) if user_id else None,
            )
            device_risk = device_result.get("device_risk", 0.0)
            if device_result.get("flags"):
                result["ensemble_flags"].extend(device_result["flags"])
        except Exception as exc:
            logger.warning("DeviceIntelligenceEngine failed: %s", exc)

    result["device_risk"] = device_risk
    result["device_analysis"] = device_result

    # ── 6. Composite Signal Engine (Category 8) ────────────────────────
    composite_result: dict = {}
    if extended_features:
        try:
            from app.models.composite_signal_engine import get_composite_engine

            comp_engine = get_composite_engine()
            composite_result = comp_engine.analyze(
                features=extended_features,
                user_id=int(user_id) if user_id else None,
            )
            if composite_result.get("composite_flags"):
                result["ensemble_flags"].extend(composite_result["composite_flags"])
        except Exception as exc:
            logger.warning("CompositeSignalEngine failed: %s", exc)

    result["composite_analysis"] = composite_result

    # ── 7. Passive Enrollment Manager (BioCatch-style) ─────────────────
    enrollment_result: dict = {}
    if user_id and extended_features:
        try:
            from app.models.passive_enrollment import get_enrollment_manager

            enrollment_mgr = get_enrollment_manager()
            session_context = {
                "is_new_device": device_risk > 0.6,
                "is_new_ip": device_result.get("flags") and any("ip" in f.lower() for f in device_result["flags"])
            }
            enrollment_result = enrollment_mgr.ingest_session_data(
                user_id=int(user_id),
                keystroke_features=keystroke_features,
                mouse_features=mouse_features,
                extended_features=extended_features,
                session_context=session_context,
                source="session",
            )
            if enrollment_result.get("action") == "anomaly":
                result["ensemble_flags"].append(
                    f"enrollment:behavioral_anomaly("
                    f"match={enrollment_result.get('match_score', 0):.2f})"
                )
        except Exception as exc:
            logger.warning("PassiveEnrollmentManager failed: %s", exc)

    result["enrollment_status"] = enrollment_result

    # ── 8. Per-User Feature Selection (BioCatch top-20) ────────────────
    weighted_match = 0.0
    feature_selection_result: dict = {}
    if user_id and extended_features and user_baseline:
        try:
            from app.models.per_user_feature_selector import get_feature_selector

            selector = get_feature_selector()
            feature_selection_result = selector.get_weighted_score(
                user_id=int(user_id),
                current_features=extended_features,
                user_profile=user_baseline,
            )
            weighted_match = feature_selection_result.get("weighted_match_score", 0.0)
            anomalous = feature_selection_result.get("anomalous_features", [])
            if anomalous:
                result["ensemble_flags"].append(
                    f"feature_selection:anomalous_features("
                    f"{len(anomalous)}: {', '.join(anomalous[:3])})"
                )
        except Exception as exc:
            logger.warning("PerUserFeatureSelector failed: %s", exc)

    result["feature_selection"] = feature_selection_result
    result["weighted_match_score"] = weighted_match

    # ── 9. Transaction History Baseline ─────────────────────────────────
    txn_risk = 0.0
    txn_result: dict = {}
    if user_id and transaction_amount is not None:
        try:
            from app.models.transaction_baseline import get_txn_baseline

            txn_baseline = get_txn_baseline()
            txn_result = txn_baseline.score_transaction(
                user_id=int(user_id),
                amount=transaction_amount,
                beneficiary_id=beneficiary_id or "unknown",
                behavioral_risk=cognitive.get("cognitive_risk", 0.0)
                if cognitive
                else 0.0,
            )
            txn_risk = txn_result.get("transaction_risk", 0.0)
            if txn_result.get("flags"):
                result["ensemble_flags"].extend(txn_result["flags"])
        except Exception as exc:
            logger.warning("TransactionHistoryBaseline failed: %s", exc)

    result["transaction_risk"] = txn_result

    # ── 10. GAN Liveness / Replay Detection (Entropy Analysis) ─────────
    replay_risk = 0.0
    replay_result: dict = {}
    if session_history:
        try:
            from app.models.gan_adversarial import LivenessDetector as GANLiveness
            gan_detector = GANLiveness()
            # Analyze entropy of hold times to detect replayed/synthetic streams
            replay_result = gan_detector.check_entropy(session_history, "hold_time")
            if replay_result.get("is_suspicious"):
                replay_risk = replay_result.get("replay_probability", 0.0)
                result["ensemble_flags"].append(f"replay_detected:prob={replay_risk:.2f}")
        except Exception as exc:
            logger.warning("GAN LivenessDetector failed: %s", exc)

    result["replay_risk"] = replay_risk
    result["replay_analysis"] = replay_result

    # ── 10b. ADWIN Concept Drift Detection ─────────────────────────────
    drift_risk = 0.0
    if session_history and len(session_history) > 10:
        try:
            from app.models.adwin_drift import get_adwin_detector
            adwin = get_adwin_detector()
            drift_result = adwin.detect(
                stream=[s.get("flight_time_mean", 0) for s in session_history]
            )
            drift_risk = drift_result.get("drift_probability", 0.0)
            if drift_risk > 0.5:
                result["ensemble_flags"].append(f"adwin:concept_drift_detected({drift_risk:.2f})")
        except Exception as exc:
            logger.warning("ADWIN drift detection failed: %s", exc)

    result["drift_risk"] = drift_risk

    # ── 11. Fuse ALL 11 engine signals with explainability ────────────────
    cognitive_risk = cognitive.get("cognitive_risk", 0.0) if cognitive else 0.0
    fraud_score = composite_result.get("fraud_pattern_score", 0.0)
    social_eng = composite_result.get("social_eng_score", 0.0)
    enrollment_match = enrollment_result.get("match_score", 0.5)

    # Named engine signals for attribution
    engine_signals = {
        "cognitive":         cognitive_risk,
        "duress":            duress_score,
        "liveness":          1.0 - liveness_score,   # Inverted: low liveness = high risk
        "invisible_challenge": challenge_risk,
        "device_intelligence": device_risk,
        "composite_fraud":   max(fraud_score, social_eng),
        "passive_enrollment": 1.0 - enrollment_match,  # Inverted: low match = high risk
        "feature_selection":  1.0 - weighted_match,     # Inverted: mismatch = risk
        "transaction":       txn_risk,
        "replay_detection":  replay_risk,
        "concept_drift":     drift_risk,
    }

    # Configurable weights — keys must match engine_signals
    weights = ENSEMBLE_WEIGHTS.copy()

    # Weighted fusion with per-engine attribution (SHAP-like)
    risk_attribution = {}
    ensemble_risk = 0.0
    for engine_name, signal in engine_signals.items():
        w = weights.get(engine_name, 0.0)
        contribution = signal * w
        risk_attribution[engine_name] = round(contribution, 4)
        ensemble_risk += contribution

    ensemble_risk = round(min(1.0, max(0.0, ensemble_risk)), 4)
    result["ensemble_risk"] = ensemble_risk
    result["risk_attribution"] = risk_attribution

    # Top risk drivers (for explainability UI)
    sorted_drivers = sorted(risk_attribution.items(), key=lambda x: x[1], reverse=True)
    result["top_risk_drivers"] = [
        {"engine": name, "contribution": val}
        for name, val in sorted_drivers[:3]
        if val > 0.001
    ]

    # Collect flags from cognitive
    if cognitive and cognitive.get("cognitive_flags"):
        result["ensemble_flags"].extend(cognitive["cognitive_flags"])

    # Determine action — use the most restrictive recommendation
    if cognitive and cognitive.get("recommended_action") == "block":
        result["ensemble_action"] = "block"
    elif duress_score >= 0.7:
        result["ensemble_action"] = "block"
    elif device_risk >= 0.8:
        result["ensemble_action"] = "block"
    elif txn_risk >= 0.8:
        result["ensemble_action"] = "block"
    elif replay_risk >= 0.7:
        result["ensemble_action"] = "block"
    elif ensemble_risk >= 0.6:
        result["ensemble_action"] = "step_up"
    elif ensemble_risk >= 0.3:
        result["ensemble_action"] = "silent_challenge"
    else:
        result["ensemble_action"] = "allow"

    return result
