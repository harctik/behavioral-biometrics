"""
ML Ensemble Integration Layer.

Bridges the gap between the ML models (CognitiveEngine, DuressDetector,
LivenessDetector, InvisibleChallengeEngine, DeviceIntelligence,
CompositeSignalEngine, PassiveEnrollment, PerUserFeatureSelector,
TransactionBaseline, ADWIN drift) and the API scoring pipeline.

This module provides two fusion strategies:
  A. ``score_with_ensemble()`` — legacy weighted average (backward compat)
  B. ``score_with_bayesian_fusion()`` — state-of-the-art Bayesian belief
     update framework with calibrated posteriors and full explainability.

The Bayesian fusion (B) is the recommended path for production deployments.
It replaces naive weighted averaging with log-odds belief updates that are:
  - Uncertainty-aware (each engine reports score + confidence)
  - Self-calibrating (engine reliability priors adapt over time)
  - Fully explainable (audit trail shows how each engine shifted belief)
  - Robust to failure (gracefully degrades on low-confidence signals)
"""

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Configurable ensemble weights — sum to 1.0.
# Override at runtime via ``ENSEMBLE_WEIGHTS.update(...)`` for auto-calibration.
ENSEMBLE_WEIGHTS: Dict[str, float] = {
    "cognitive":           0.12,
    "duress":              0.12,
    "liveness":            0.09,
    "invisible_challenge": 0.08,
    "device_intelligence": 0.06,
    "composite_fraud":     0.05,
    "passive_enrollment":  0.06,
    "feature_selection":   0.08,
    "transaction":         0.09,
    "replay_detection":    0.09,
    "concept_drift":       0.04,
    "digraph_match":       0.12,
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
    # Fall back to CognitiveEngine's duress probability if standalone detector didn't fire
    if duress_score < 0.01 and cognitive:
        cog_duress = cognitive.get("duress_probability", 0.0)
        if cog_duress > duress_score:
            result["duress_score"] = cog_duress

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

            # Also build/update per-key digraph profile for keystroke identity matching
            if keystroke_features:
                try:
                    # Extract per-key hold and per-digraph flight from keystroke features
                    digraph_input = {
                        "per_key_hold": keystroke_features.get("per_key_hold", {}),
                        "per_digraph_flight": keystroke_features.get("per_digraph_flight", {}),
                    }
                    # If no per_key data, try to synthesize from hold_time features
                    if not digraph_input["per_key_hold"] and "hold_time_mean" in extended_features:
                        digraph_input["per_key_hold"] = {"_aggregate": {
                            "mean": extended_features.get("hold_time_mean", 70),
                            "std": extended_features.get("hold_time_std", 12),
                            "count": 1,
                        }}
                    if not digraph_input["per_digraph_flight"] and "flight_time_mean" in extended_features:
                        digraph_input["per_digraph_flight"] = {"_aggregate": {
                            "mean": extended_features.get("flight_time_mean", 110),
                            "std": extended_features.get("flight_time_std", 15),
                            "count": 1,
                        }}
                    if digraph_input["per_key_hold"] or digraph_input["per_digraph_flight"]:
                        enrollment_mgr.ingest_digraph_profile(
                            user_id=int(user_id),
                            digraph_profile=digraph_input,
                            source="session",
                        )
                except Exception as dgp_exc:
                    logger.debug("Digraph profile ingestion failed: %s", dgp_exc)
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
            # Analyze entropy of multiple features to detect replayed/synthetic streams
            # Try different feature keys that exist in our extended features
            best_replay = {"replay_probability": 0.0}
            for fkey in ("typing_hold_variance", "flight_time_cv", "bigram_speed_mean",
                         "correction_rate", "mouse_acceleration_mean"):
                try:
                    r = gan_detector.check_entropy(session_history, fkey)
                    if r.get("sufficient_data") and r.get("replay_probability", 0) > best_replay.get("replay_probability", 0):
                        best_replay = r
                except Exception:
                    pass
            replay_result = best_replay
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
                stream=[s.get("bigram_speed_mean", s.get("flight_time_cv", 0)) for s in session_history]
            )
            drift_risk = drift_result.get("drift_probability", 0.0)
            if drift_risk > 0.5:
                result["ensemble_flags"].append(f"adwin:concept_drift_detected({drift_risk:.2f})")
        except Exception as exc:
            logger.warning("ADWIN drift detection failed: %s", exc)

    result["drift_risk"] = drift_risk

    # ── 11b. Digraph Bayesian Profile Match (Per-Key/Digraph) ──────────
    digraph_match_score = 0.5  # Neutral default
    digraph_confidence = 0.0
    if user_id:
        try:
            from app.models.passive_enrollment import get_enrollment_manager
            em = get_enrollment_manager()
            dgp_state = em._load_digraph_state(int(user_id))
            if dgp_state and dgp_state.get("per_key_hold"):
                # If we have current keystroke features, build a lightweight profile for matching
                if keystroke_features:
                    incoming_profile = {
                        "per_key_hold": keystroke_features.get("per_key_hold", {}),
                        "per_digraph_flight": keystroke_features.get("per_digraph_flight", {}),
                    }
                    if incoming_profile["per_key_hold"] or incoming_profile["per_digraph_flight"]:
                        digraph_match_score = em._compute_digraph_match_score(
                            dgp_state, incoming_profile
                        )
                # Confidence based on profile maturity
                n_keys = len(dgp_state.get("per_key_hold", {}))
                n_digraphs = len(dgp_state.get("per_digraph_flight", {}))
                updates = dgp_state.get("updates_count", 0)
                digraph_confidence = min(
                    1.0,
                    (updates / 5.0) * 0.5
                    + (n_keys / 20.0) * 0.3
                    + (n_digraphs / 30.0) * 0.2,
                )
                if digraph_match_score < 0.3 and digraph_confidence > 0.5:
                    result["ensemble_flags"].append(
                        f"digraph:anomaly(match={digraph_match_score:.2f},conf={digraph_confidence:.2f})"
                    )
        except Exception as exc:
            logger.warning("Digraph profile match failed: %s", exc)

    result["digraph_match_score"] = round(digraph_match_score, 4)
    result["digraph_confidence"] = round(digraph_confidence, 4)

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
        "digraph_match":     (1.0 - digraph_match_score) * digraph_confidence,  # Weighted by confidence
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

    # ── 12. Risk Confidence — how certain is the ensemble about this score ──
    # Based on signal consensus: if engines agree, confidence is high
    non_zero_signals = [v for v in engine_signals.values() if v > 0.01]
    if len(non_zero_signals) >= 3:
        import statistics
        signal_std = statistics.stdev(non_zero_signals) if len(non_zero_signals) > 1 else 0.0
        # Low variance = high consensus = high confidence
        risk_confidence = round(max(0.1, min(1.0, 1.0 - signal_std)), 4)
    else:
        risk_confidence = 0.3  # Low confidence when few signals are active
    result["risk_confidence"] = risk_confidence

    # ── 13. GAN Adversarial — synthetic behavior probability ───────────────
    synthetic_probability = 0.0
    try:
        from app.models.gan_adversarial import GANAdversarialDetector
        gan = GANAdversarialDetector()
        gan_result = gan.analyze(extended_features)
        synthetic_probability = gan_result.get("synthetic_probability", 0.0)
        if synthetic_probability > 0.7:
            result["ensemble_flags"].append(
                f"gan:synthetic_behavior_detected(prob={synthetic_probability:.2f})"
            )
            # Boost ensemble risk when GAN detects synthetic behavior
            ensemble_risk = min(1.0, ensemble_risk + synthetic_probability * 0.15)
            result["ensemble_risk"] = round(ensemble_risk, 4)
    except Exception as exc:
        logger.debug("GAN adversarial detection skipped: %s", exc)

    result["synthetic_probability"] = round(synthetic_probability, 4)

    # ── 14. Adaptive Threshold Tuning ──────────────────────────────────────
    # Adjust action thresholds based on user enrollment maturity and confidence
    block_threshold = 0.6
    step_up_threshold = 0.3
    if enrollment_result.get("enrollment_phase") == "collecting":
        # Be more lenient during enrollment — user profile is still building
        block_threshold = 0.75
        step_up_threshold = 0.45
    elif risk_confidence < 0.5:
        # Low confidence — don't block, escalate to step-up instead
        block_threshold = 0.8
        step_up_threshold = 0.4

    result["adaptive_thresholds"] = {
        "block": round(block_threshold, 2),
        "step_up": round(step_up_threshold, 2),
        "confidence_adjusted": risk_confidence < 0.5,
        "enrollment_adjusted": enrollment_result.get("enrollment_phase") == "collecting",
    }

    # Collect flags from cognitive
    if cognitive and cognitive.get("cognitive_flags"):
        result["ensemble_flags"].extend(cognitive["cognitive_flags"])

    # Determine action — use adaptive thresholds
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
    elif ensemble_risk >= block_threshold:
        result["ensemble_action"] = "step_up"
    elif ensemble_risk >= step_up_threshold:
        result["ensemble_action"] = "silent_challenge"
    else:
        result["ensemble_action"] = "allow"

    return result


def score_with_bayesian_fusion(
    extended_features: Dict[str, Any],
    user_id: Optional[int] = None,
    session_history: Optional[List[Dict]] = None,
    user_baseline: Optional[Dict[str, Any]] = None,
    keystroke_features: Optional[Dict] = None,
    mouse_features: Optional[Dict] = None,
    transaction_amount: Optional[float] = None,
    beneficiary_id: Optional[str] = None,
    enrollment_phase: str = "mature",
) -> Dict[str, Any]:
    """State-of-the-art Bayesian risk fusion across all ML engines.

    Runs the same 13 engines as ``score_with_ensemble()`` but replaces
    the naive weighted-average fusion with a Bayesian belief-update
    framework that produces calibrated posterior probabilities.

    This is the recommended scoring path for production deployments.

    Returns:
        Dict with keys:
          - bayesian_risk: float (calibrated posterior)
          - decision: str (allow/silent_challenge/step_up/block)
          - confidence: float (meta-confidence in the decision)
          - evidence_trail: list (per-engine belief shifts)
          - top_risk_drivers: list (top 3 engines by contribution)
          - legacy_ensemble: dict (backward-compat weighted-average result)
    """
    from app.models.bayesian_fusion import BayesianRiskFusion, EngineEvidence

    # Run legacy ensemble to get all engine signals
    t0 = time.monotonic()
    legacy = score_with_ensemble(
        extended_features=extended_features,
        user_id=user_id,
        session_history=session_history,
        user_baseline=user_baseline,
        keystroke_features=keystroke_features,
        mouse_features=mouse_features,
        transaction_amount=transaction_amount,
        beneficiary_id=beneficiary_id,
    )
    engine_time_ms = (time.monotonic() - t0) * 1000

    # Collect evidence from all engine signals
    evidences: List[EngineEvidence] = []

    # 1. Cognitive
    cog = legacy.get("cognitive_analysis") or {}
    evidences.append(EngineEvidence(
        engine_name="cognitive",
        risk_score=cog.get("cognitive_risk", 0.0),
        confidence=0.8 if cog else 0.0,
        flags=cog.get("cognitive_flags", []),
        raw_output=cog,
    ))

    # 2. Duress
    evidences.append(EngineEvidence(
        engine_name="duress",
        risk_score=legacy.get("duress_score", 0.0),
        confidence=0.9 if legacy.get("duress_score", 0) > 0 else 0.0,
    ))

    # 3. Liveness (inverted: low liveness = high risk)
    liveness = legacy.get("liveness_score", 1.0)
    evidences.append(EngineEvidence(
        engine_name="liveness",
        risk_score=1.0 - liveness,
        confidence=0.85 if liveness < 1.0 else 0.1,
    ))

    # 4. Invisible Challenge
    evidences.append(EngineEvidence(
        engine_name="invisible_challenge",
        risk_score=legacy.get("challenge_risk", 0.0),
        confidence=0.7 if legacy.get("challenge_risk", 0) > 0 else 0.0,
    ))

    # 5. Device Intelligence
    evidences.append(EngineEvidence(
        engine_name="device_intelligence",
        risk_score=legacy.get("device_risk", 0.0),
        confidence=0.8 if legacy.get("device_risk", 0) > 0 else 0.0,
        flags=(legacy.get("device_analysis") or {}).get("flags", []),
    ))

    # 6. Composite Fraud
    comp = legacy.get("composite_analysis") or {}
    comp_risk = max(comp.get("fraud_pattern_score", 0.0), comp.get("social_eng_score", 0.0))
    evidences.append(EngineEvidence(
        engine_name="composite_fraud",
        risk_score=comp_risk,
        confidence=0.7 if comp_risk > 0 else 0.0,
        flags=comp.get("composite_flags", []),
    ))

    # 7. Passive Enrollment (inverted: low match = high risk)
    enrollment = legacy.get("enrollment_status") or {}
    match_score = enrollment.get("match_score", 0.5)
    evidences.append(EngineEvidence(
        engine_name="passive_enrollment",
        risk_score=1.0 - match_score,
        confidence=0.8 if enrollment.get("enrolled") else 0.1,
    ))

    # 8. Feature Selection (inverted: mismatch = risk)
    weighted_match = legacy.get("weighted_match_score", 0.0)
    evidences.append(EngineEvidence(
        engine_name="feature_selection",
        risk_score=1.0 - weighted_match,
        confidence=0.75 if weighted_match > 0 else 0.0,
    ))

    # 9. Transaction
    txn = legacy.get("transaction_risk") or {}
    txn_risk_val = txn.get("transaction_risk", 0.0) if isinstance(txn, dict) else 0.0
    evidences.append(EngineEvidence(
        engine_name="transaction",
        risk_score=txn_risk_val,
        confidence=0.85 if txn_risk_val > 0 else 0.0,
        flags=txn.get("flags", []) if isinstance(txn, dict) else [],
    ))

    # 10. Replay Detection
    evidences.append(EngineEvidence(
        engine_name="replay_detection",
        risk_score=legacy.get("replay_risk", 0.0),
        confidence=0.8 if legacy.get("replay_risk", 0) > 0 else 0.0,
    ))

    # 11. Concept Drift
    evidences.append(EngineEvidence(
        engine_name="concept_drift",
        risk_score=legacy.get("drift_risk", 0.0),
        confidence=0.6 if legacy.get("drift_risk", 0) > 0 else 0.0,
    ))

    # 12. GAN Adversarial
    evidences.append(EngineEvidence(
        engine_name="gan_adversarial",
        risk_score=legacy.get("synthetic_probability", 0.0),
        confidence=0.7 if legacy.get("synthetic_probability", 0) > 0 else 0.0,
    ))

    # Run Bayesian fusion
    fusion = BayesianRiskFusion(enrollment_phase=enrollment_phase)
    result = fusion.fuse(evidences)

    return {
        "bayesian_risk": result.posterior_risk,
        "prior_risk": result.prior_risk,
        "log_odds_shift": result.log_odds_shift,
        "decision": result.decision,
        "confidence": result.confidence,
        "evidence_trail": result.evidence_trail,
        "top_risk_drivers": result.top_risk_drivers,
        "fusion_time_ms": result.execution_time_ms,
        "total_time_ms": round((time.monotonic() - t0) * 1000 + result.execution_time_ms, 2),
        "engines_used": result.engines_used,
        "engines_skipped": result.engines_skipped,
        "adaptive_thresholds": fusion._thresholds,
        # Backward compat — include legacy weighted-average result
        "legacy_ensemble": {
            "ensemble_risk": legacy.get("ensemble_risk"),
            "ensemble_action": legacy.get("ensemble_action"),
            "risk_attribution": legacy.get("risk_attribution"),
            "risk_confidence": legacy.get("risk_confidence"),
        },
        # Pass through all flags
        "ensemble_flags": legacy.get("ensemble_flags", []),
    }

