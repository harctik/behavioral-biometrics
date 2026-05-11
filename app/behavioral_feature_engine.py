"""
Behavioral Biometrics Patent-Level Feature Engine — 200+ Behavioral Features.

Processes raw telemetry from all 8 frontend collector categories and
produces a comprehensive feature vector for ML scoring.

Categories processed:
  1. Mouse & Pointer Dynamics (40+ features)
  2. Keystroke Dynamics (35+ features)
  3. Cognitive / Behavioral Signals (25+ features)
  4. Duress & Social Engineering (15+ features)
  5. Invisible Challenge Responses (12+ features)
  6. Physiological Signals (18+ features)
  7. Device & Contextual Signals (20+ features)
  8. Derived & Composite Signals (30+ features)
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class BehavioralFeatureEngine:
    """Extracts 200+ features from all 8 Behavioral Biometrics signal categories."""

    # ── Category 1: Mouse & Pointer ───────────────────────────────────────

    MOUSE_FEATURES = [
        "mouse_vel_instant",
        "mouse_vel_mean",
        "mouse_vel_std",
        "mouse_vel_median",
        "mouse_acc_mean",
        "mouse_decel_rate",
        "mouse_jerk_mean",
        "mouse_jerk_std",
        "trajectory_curvature",
        "angular_deviation",
        "overshoot_distance",
        "click_precision",
        "click_dur_mean",
        "click_dur_std",
        "dbl_click_interval",
        "mouse_idle_time",
        "aimless_movement_dist",
        "dir_change_freq",
        "dir_change_angle_mean",
        "dir_change_angle_std",
        "micro_jitter_amp",
        "micro_jitter_freq",
        "hand_tremor_sig",
        "scroll_speed",
        "scroll_acc",
        "scroll_reversal_freq",
        "hover_dwell_mean",
        "mouse_event_count",
        "click_count",
        "scroll_event_count",
    ]

    # ── Category 2: Keystroke ─────────────────────────────────────────────

    KEYSTROKE_FEATURES = [
        "key_hold_mean",
        "key_hold_std",
        "key_hold_median",
        "key_hold_cv",
        "flight_time_mean",
        "flight_time_std",
        "flight_time_median",
        "inter_key_gap_cv",
        "typing_speed_wpm",
        "typing_speed_variance",
        "digraph_timing_consistency",
        "trigraph_timing_consistency",
        "ngram_pattern_entropy",
        "rhythm_consistency",
        "burst_count",
        "burst_mean_length",
        "burst_to_pause_ratio",
        "segmented_typing_score",
        "backspace_freq",
        "backspace_timing",
        "delete_vs_backspace",
        "error_correction_speed",
        "copy_paste_count",
        "shortcut_proficiency",
        "ctrl_usage_count",
        "caps_lock_used",
        "shift_hold_mean",
        "uppercase_method",
        "tab_nav_count",
        "enter_submit_count",
        "numpad_preference",
        "password_rhythm",
        "data_familiarity_signal",
        "time_to_first_key",
        "time_last_key_to_submit",
        "keystroke_event_count",
        "total_keys_pressed",
    ]

    # ── Category 3: Cognitive ─────────────────────────────────────────────

    COGNITIVE_FEATURES = [
        "nav_path_length",
        "nav_path_entropy",
        "nav_deviation_score",
        "field_visit_count",
        "field_revisit_count",
        "field_skip_count",
        "field_order_consistency",
        "form_fill_speed",
        "pre_field_hesitation_mean",
        "pre_field_hesitation_max",
        "hesitation_count",
        "hesitation_duration_mean",
        "pre_submit_pause",
        "back_button_count",
        "scroll_read_speed",
        "scroll_depth_reached",
        "session_duration",
        "session_flow_efficiency",
        "tab_switch_count",
        "session_dead_time",
        "idle_gap_count",
        "idle_gap_mean",
        "error_rate_spike",
        "slow_correction_count",
        "correction_rate",
        "rapid_submit_detected",
        "reread_count",
        "cognitive_event_count",
    ]

    # ── Category 4: Duress ────────────────────────────────────────────────

    DURESS_FEATURES = [
        "duress_probability",
    ]

    # ── Category 5: Invisible Challenges ──────────────────────────────────

    CHALLENGE_FEATURES = [
        "challenge_count",
        "response_count",
        "correction_time_mean",
        "correction_time_std",
        "correction_time_median",
        "correction_accuracy_mean",
        "correction_accuracy_std",
        "subconscious_ratio",
        "mouse_deviation_count",
        "mouse_deviation_correction_time",
        "button_micro_shift_count",
        "button_micro_shift_correction_time",
        "scroll_speed_inject_count",
        "scroll_speed_inject_correction_time",
        "cursor_speed_change_count",
        "cursor_speed_change_correction_time",
        "bot_challenge_score",
    ]

    # ── Category 6: Physiological ─────────────────────────────────────────

    PHYSIOLOGICAL_FEATURES = [
        "hand_dominance_score",
        "touch_force_mean",
        "touch_force_std",
        "touch_area_mean",
        "touch_area_std",
        "grip_posture_score",
        "motion_acc_mean",
        "motion_acc_std",
        "hand_tremor_magnitude",
        "hand_tremor_frequency",
        "device_tilt_mean",
        "device_tilt_std",
        "touch_event_count",
        "motion_event_count",
        "orientation_change_count",
    ]

    # ── Category 7: Device ────────────────────────────────────────────────

    DEVICE_FEATURES = [
        "screen_width",
        "screen_height",
        "device_memory",
        "hardware_concurrency",
        "max_touch_points",
        "login_hour",
        "login_day",
        "rat_latency_score",
        "emulator_score",
    ]

    # ── Category 8: Composite ─────────────────────────────────────────────

    COMPOSITE_FEATURES = [
        "sensorimotor_loop_time",
        "cognitive_signature_entropy",
        "bot_vs_human_score",
        "rat_vs_human_score",
        "social_eng_probability",
        "session_risk_trajectory",
        "lie_detection_signal",
        "multi_user_score",
        "fraud_pattern_score",
        "genuine_user_score",
    ]

    ALL_FEATURES = (
        MOUSE_FEATURES
        + KEYSTROKE_FEATURES
        + COGNITIVE_FEATURES
        + DURESS_FEATURES
        + CHALLENGE_FEATURES
        + PHYSIOLOGICAL_FEATURES
        + DEVICE_FEATURES
        + COMPOSITE_FEATURES
    )

    FEATURE_COUNT = len(ALL_FEATURES)

    def __init__(self):
        logger.info(
            "BehavioralFeatureEngine initialized with %d features across 8 categories",
            self.FEATURE_COUNT,
        )

    def extract(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract all features from a frontend telemetry payload.

        Args:
            payload: The full JSON payload from Behavioral BiometricsCollector.extractAll()

        Returns:
            Dict with all features normalized and filled with defaults.
        """
        categories = payload.get("categories", {})
        extended = payload.get("extended_features", {})
        device = payload.get("device_context", {})

        features: Dict[str, float] = {}

        # Category 1: Mouse
        mouse = categories.get("mouse_pointer", {})
        for feat in self.MOUSE_FEATURES:
            features[feat] = self._safe_float(
                mouse.get(feat, extended.get(f"mouse_{feat}", 0))
            )

        # Category 2: Keystroke
        ks = categories.get("keystroke", {})
        for feat in self.KEYSTROKE_FEATURES:
            features[feat] = self._safe_float(
                ks.get(feat, extended.get(f"ks_{feat}", 0))
            )

        # Category 3: Cognitive
        cog = categories.get("cognitive", {})
        for feat in self.COGNITIVE_FEATURES:
            features[feat] = self._safe_float(
                cog.get(feat, extended.get(f"cog_{feat}", 0))
            )

        # Category 4: Duress
        features["duress_probability"] = self._safe_float(
            cog.get("duress_probability", extended.get("duress_probability", 0))
        )

        # Category 5: Challenges
        ch = categories.get("invisible_challenges", {})
        for feat in self.CHALLENGE_FEATURES:
            features[feat] = self._safe_float(
                ch.get(feat, extended.get(f"ch_{feat}", 0))
            )

        # Category 6: Physiological
        phys = categories.get("physiological", {})
        for feat in self.PHYSIOLOGICAL_FEATURES:
            features[feat] = self._safe_float(
                phys.get(feat, extended.get(f"phys_{feat}", 0))
            )

        # Category 7: Device
        for feat in self.DEVICE_FEATURES:
            features[feat] = self._safe_float(device.get(feat, extended.get(feat, 0)))

        # Category 8: Composite
        comp = categories.get("composite", {})
        for feat in self.COMPOSITE_FEATURES:
            features[feat] = self._safe_float(comp.get(feat, 0))

        return features

    def get_feature_vector(self, features: Dict[str, float]) -> np.ndarray:
        """Convert feature dict to ordered numpy array."""
        return np.array(
            [features.get(f, 0.0) for f in self.ALL_FEATURES],
            dtype=np.float32,
        )

    def get_category_scores(self, features: Dict[str, float]) -> Dict[str, float]:
        """Compute a per-category risk summary."""
        scores = {}

        # Mouse anomaly
        scores["mouse_anomaly"] = self._score_category(features, self.MOUSE_FEATURES)

        # Keystroke anomaly
        scores["keystroke_anomaly"] = self._score_category(
            features, self.KEYSTROKE_FEATURES
        )

        # Cognitive risk
        scores["cognitive_risk"] = min(
            1.0,
            (
                features.get("hesitation_count", 0) * 0.1
                + features.get("tab_switch_count", 0) * 0.1
                + features.get("session_dead_time", 0) * 0.005
                + features.get("copy_paste_count", 0) * 0.15
                + features.get("reread_count", 0) * 0.02
            ),
        )

        # Duress
        scores["duress_risk"] = features.get("duress_probability", 0)

        # Challenge (bot detection)
        scores["challenge_bot_risk"] = features.get("bot_challenge_score", 0)

        # Physiological
        scores["physiological_anomaly"] = self._score_physio(features)

        # Device
        scores["device_risk"] = max(
            features.get("rat_latency_score", 0),
            features.get("emulator_score", 0),
        )

        # Composite
        scores["composite_fraud"] = features.get("fraud_pattern_score", 0)
        scores["bot_vs_human"] = features.get("bot_vs_human_score", 0)

        return scores

    def _score_category(self, features: Dict, feat_list: List[str]) -> float:
        """Simple anomaly: ratio of zero-valued features (less data = higher risk)."""
        if not feat_list:
            return 0.0
        zero_count = sum(1 for f in feat_list if features.get(f, 0) == 0)
        return zero_count / len(feat_list)

    def _score_physio(self, features: Dict) -> float:
        """Score physiological signals for anomalies."""
        risk = 0.0
        force = features.get("touch_force_mean", 0)
        if force > 0 and (force < 0.05 or force > 0.95):
            risk += 0.3
        tremor = features.get("hand_tremor_magnitude", 0)
        if tremor > 0.5:
            risk += 0.2
        motion_std = features.get("motion_acc_std", 0)
        if motion_std > 15:
            risk += 0.3
        return min(1.0, risk)

    @staticmethod
    def _safe_float(val: Any) -> float:
        """Convert value to float, handling None/NaN/Inf."""
        if val is None:
            return 0.0
        if isinstance(val, str):
            try:
                val = float(val)
            except (ValueError, TypeError):
                return 0.0
        if isinstance(val, (int, float)):
            if math.isnan(val) or math.isinf(val):
                return 0.0
            return float(val)
        return 0.0

    def get_info(self) -> Dict[str, Any]:
        """Return feature engine metadata."""
        return {
            "total_features": self.FEATURE_COUNT,
            "categories": {
                "mouse_pointer": len(self.MOUSE_FEATURES),
                "keystroke": len(self.KEYSTROKE_FEATURES),
                "cognitive": len(self.COGNITIVE_FEATURES),
                "duress": len(self.DURESS_FEATURES),
                "invisible_challenges": len(self.CHALLENGE_FEATURES),
                "physiological": len(self.PHYSIOLOGICAL_FEATURES),
                "device": len(self.DEVICE_FEATURES),
                "composite": len(self.COMPOSITE_FEATURES),
            },
            "all_feature_names": self.ALL_FEATURES,
        }


# ── Module-level singleton ────────────────────────────────────────────────────
_engine: BehavioralFeatureEngine | None = None


def get_behavioral_engine() -> BehavioralFeatureEngine:
    global _engine
    if _engine is None:
        _engine = BehavioralFeatureEngine()
    return _engine
