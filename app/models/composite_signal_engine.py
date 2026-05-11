"""
Composite Signal Engine — Derived & Combined Signals (Category 8).

This is where Behavioral Biometrics's "3,000 parameters" come from — computed by
combining raw signals from all other categories.

Signals derived:
- Sensorimotor control loop model per user
- Cognitive biometric signature
- Behavioral biometric cookie (cross-session hash)
- Lie detection (data familiarity analysis)
- Multiple-user / shared-login detection
- Session risk trajectory (score over time)
- Per-field behavioral scoring
"""

from __future__ import annotations

import hashlib
import logging
import math
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class CompositeSignalEngine:
    """Derives high-level composite signals from raw feature categories."""

    def __init__(self):
        self.user_baselines: Dict[int, Dict] = {}
        self.session_trajectories: Dict[str, List[float]] = {}

    def analyze(
        self,
        features: Dict[str, float],
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Full composite analysis.

        Returns:
            {
                "sensorimotor_signature": dict,
                "cognitive_biometric_hash": str,
                "behavioral_cookie": str,
                "lie_detection_score": float,
                "multi_user_score": float,
                "shared_login_score": float,
                "session_risk_trajectory": list[float],
                "per_field_scores": dict,
                "fraud_pattern_score": float,
                "genuine_user_score": float,
                "bot_differentiation_score": float,
                "rat_differentiation_score": float,
                "social_eng_score": float,
                "composite_flags": list[str],
            }
        """
        flags: list[str] = []

        # Sensorimotor signature
        sensorimotor = self._build_sensorimotor_signature(features)

        # Cognitive biometric hash (top 20 most distinctive features)
        cog_hash = self._compute_cognitive_hash(features)

        # Behavioral cookie (persistent across sessions)
        cookie = self._compute_behavioral_cookie(features)

        # Lie detection
        lie_score = self._detect_lie(features, user_id, flags)

        # Multi-user detection
        multi_user = self._detect_multi_user(features, user_id, flags)

        # Shared login detection
        shared_login = self._detect_shared_login(user_id, cookie, flags)

        # Session risk trajectory
        trajectory = self._update_trajectory(session_id, features)

        # Per-field scoring
        field_scores = self._score_per_field(features)

        # Fraud pattern matching
        fraud_score = self._match_fraud_patterns(features, flags)

        # Bot/RAT differentiation
        bot_score = features.get("bot_vs_human_score", 0)
        rat_score = features.get("rat_vs_human_score", 0)

        # Social engineering probability
        social_eng = self._compute_social_eng(features, flags)

        # Genuine user matching
        genuine_score = self._match_genuine_user(features, user_id)

        # Store baseline for future comparison
        if user_id:
            self._update_baseline(user_id, features)

        return {
            "sensorimotor_signature": sensorimotor,
            "cognitive_biometric_hash": cog_hash,
            "behavioral_cookie": cookie,
            "lie_detection_score": round(lie_score, 4),
            "multi_user_score": round(multi_user, 4),
            "shared_login_score": round(shared_login, 4),
            "session_risk_trajectory": trajectory,
            "per_field_scores": field_scores,
            "fraud_pattern_score": round(fraud_score, 4),
            "genuine_user_score": round(genuine_score, 4),
            "bot_differentiation_score": round(bot_score, 4),
            "rat_differentiation_score": round(rat_score, 4),
            "social_eng_score": round(social_eng, 4),
            "composite_flags": flags,
        }

    def _build_sensorimotor_signature(self, f: Dict) -> Dict:
        """Build user-specific sensorimotor control loop model."""
        return {
            "motor_speed": f.get("mouse_vel_mean", 0),
            "motor_precision": 1 - min(1, f.get("click_precision", 0) / 50),
            "correction_latency": f.get("correction_time_mean", 0),
            "jitter_amplitude": f.get("micro_jitter_amp", 0),
            "jitter_frequency": f.get("micro_jitter_freq", 0),
            "tremor_signature": f.get("hand_tremor_sig", 0),
            "overshoot_tendency": f.get("overshoot_distance", 0),
            "curvature_profile": f.get("trajectory_curvature", 0),
            "typing_rhythm": f.get("rhythm_consistency", 0),
            "hold_time_profile": f.get("key_hold_mean", 0),
        }

    def _compute_cognitive_hash(self, f: Dict) -> str:
        """Hash the top 20 most user-distinctive features."""
        distinctive_keys = [
            "key_hold_mean",
            "key_hold_std",
            "flight_time_mean",
            "typing_speed_wpm",
            "rhythm_consistency",
            "digraph_timing_consistency",
            "burst_to_pause_ratio",
            "mouse_vel_mean",
            "mouse_vel_std",
            "mouse_acc_mean",
            "trajectory_curvature",
            "micro_jitter_amp",
            "micro_jitter_freq",
            "dir_change_freq",
            "click_dur_mean",
            "hover_dwell_mean",
            "hand_tremor_sig",
            "correction_time_mean",
            "subconscious_ratio",
            "hand_dominance_score",
        ]
        values = [str(round(f.get(k, 0), 3)) for k in distinctive_keys]
        raw = "|".join(values)
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def _compute_behavioral_cookie(self, f: Dict) -> str:
        """Generate persistent behavioral fingerprint."""
        core_features = [
            round(f.get("key_hold_mean", 0) * 10),
            round(f.get("flight_time_mean", 0) * 10),
            round(f.get("typing_speed_wpm", 0) * 10),
            round(f.get("mouse_vel_mean", 0) * 100),
            round(f.get("trajectory_curvature", 0) * 1000),
            round(f.get("micro_jitter_amp", 0) * 100),
            round(f.get("hand_dominance_score", 0.5) * 100),
            round(f.get("rhythm_consistency", 0) * 100),
        ]
        raw = ":".join(str(v) for v in core_features)
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def _detect_lie(self, f: Dict, user_id: Optional[int], flags: list) -> float:
        """Detect lying/unfamiliar data entry (Behavioral Biometrics patent).

        Users type faster on familiar data (own name, address) vs
        unfamiliar data (fake info, someone else's details).
        """
        familiarity = f.get("data_familiarity_signal", 0)

        # High variance in typing speed between fields = entering unfamiliar data
        if familiarity > 0.5:
            flags.append(
                f"composite:lie_detected(familiarity_variance={familiarity:.2f}) — "
                "user may be entering unfamiliar data"
            )
            return min(1.0, familiarity)

        return 0.0

    def _detect_multi_user(self, f: Dict, user_id: Optional[int], flags: list) -> float:
        """Detect if multiple people are using the same session."""
        score = f.get("multi_user_score", 0)

        # Sudden typing speed change = different person
        speed_var = f.get("typing_speed_variance", 0)
        if speed_var > 30:
            score = max(score, 0.6)
            flags.append(f"composite:multi_user_typing(speed_var={speed_var:.1f})")

        # Sudden mouse behavior change
        vel_std = f.get("mouse_vel_std", 0)
        vel_mean = f.get("mouse_vel_mean", 1)
        if vel_mean > 0 and vel_std > vel_mean * 1.5:
            score = max(score, 0.4)
            flags.append("composite:multi_user_mouse_pattern")

        return min(1.0, score)

    def _detect_shared_login(
        self, user_id: Optional[int], cookie: str, flags: list
    ) -> float:
        """Detect credential sharing between people."""
        if not user_id or user_id not in self.user_baselines:
            return 0.0

        stored_cookies = self.user_baselines[user_id].get("cookies", [])
        if not stored_cookies:
            return 0.0

        # If behavioral cookie differs significantly from stored ones
        matches = sum(1 for c in stored_cookies[-10:] if c == cookie)
        if len(stored_cookies) >= 5 and matches == 0:
            flags.append("composite:shared_login — behavioral cookie mismatch")
            return 0.7

        return 0.0

    def _update_trajectory(self, session_id: Optional[str], f: Dict) -> List[float]:
        """Track risk score over time within a session."""
        if not session_id:
            return []

        # Compute current risk from multiple signals
        current_risk = max(
            f.get("duress_probability", 0),
            f.get("fraud_pattern_score", 0),
            f.get("bot_vs_human_score", 0),
        )

        if session_id not in self.session_trajectories:
            self.session_trajectories[session_id] = []

        self.session_trajectories[session_id].append(round(current_risk, 4))

        # Keep last 50 data points
        if len(self.session_trajectories[session_id]) > 50:
            self.session_trajectories[session_id] = self.session_trajectories[
                session_id
            ][-30:]

        return self.session_trajectories[session_id]

    def _score_per_field(self, f: Dict) -> Dict:
        """Generate per-field behavioral score."""
        return {
            "overall_familiarity": f.get("data_familiarity_signal", 0),
            "password_rhythm_score": f.get("password_rhythm", 0),
            "time_to_first_key": f.get("time_to_first_key", 0),
        }

    def _match_fraud_patterns(self, f: Dict, flags: list) -> float:
        """Match behavior against known criminal behavior patterns."""
        score = 0.0

        # Pattern 1: Copy-paste + no hesitation + rapid submit
        if f.get("copy_paste_count", 0) > 1 and f.get("hesitation_count", 0) == 0:
            score += 0.4
            flags.append("composite:fraud_pattern_1 — paste+no_hesitation")

        # Pattern 2: Segmented typing + tab switches (coaching)
        if (
            f.get("segmented_typing_score", 0) > 0.3
            and f.get("tab_switch_count", 0) > 2
        ):
            score += 0.3
            flags.append("composite:fraud_pattern_2 — coached_entry")

        # Pattern 3: Bot-like precision + human timing
        if f.get("click_precision", 0) < 2 and f.get("correction_time_mean", 0) > 100:
            score += 0.2

        return min(1.0, score)

    def _compute_social_eng(self, f: Dict, flags: list) -> float:
        """Compute social engineering probability."""
        score = 0.0

        if f.get("tab_switch_count", 0) > 3:
            score += 0.2
        if f.get("session_dead_time", 0) > 30:
            score += 0.15
        if f.get("copy_paste_count", 0) > 1:
            score += 0.25
        if f.get("hesitation_count", 0) > 3:
            score += 0.2
        if f.get("segmented_typing_score", 0) > 0.3:
            score += 0.2

        if score > 0.5:
            flags.append(f"composite:social_engineering_risk({score:.2f})")

        return min(1.0, score)

    def _match_genuine_user(self, f: Dict, user_id: Optional[int]) -> float:
        """Match against historical profile for this user."""
        if not user_id or user_id not in self.user_baselines:
            return 0.5  # No baseline = uncertain

        baseline = self.user_baselines[user_id]
        compare_keys = [
            "key_hold_mean",
            "flight_time_mean",
            "typing_speed_wpm",
            "mouse_vel_mean",
            "trajectory_curvature",
            "rhythm_consistency",
        ]

        diffs = []
        for key in compare_keys:
            current = f.get(key, 0)
            stored = baseline.get(key, current)
            if stored > 0:
                diffs.append(abs(current - stored) / (stored + 1e-6))

        if not diffs:
            return 0.5

        avg_diff = sum(diffs) / len(diffs)
        return max(0.0, 1.0 - avg_diff)

    def _update_baseline(self, user_id: int, f: Dict):
        """Update user baseline with exponential moving average."""
        alpha = 0.2
        if user_id not in self.user_baselines:
            self.user_baselines[user_id] = {"cookies": []}

        baseline = self.user_baselines[user_id]

        # Update feature averages
        update_keys = [
            "key_hold_mean",
            "flight_time_mean",
            "typing_speed_wpm",
            "mouse_vel_mean",
            "trajectory_curvature",
            "rhythm_consistency",
            "micro_jitter_amp",
            "hand_dominance_score",
        ]
        for key in update_keys:
            val = f.get(key, 0)
            if isinstance(val, (int, float)) and val > 0:
                old = baseline.get(key, val)
                baseline[key] = old * (1 - alpha) + val * alpha

        # Store behavioral cookie
        cookie = self._compute_behavioral_cookie(f)
        if "cookies" not in baseline:
            baseline["cookies"] = []
        baseline["cookies"].append(cookie)
        if len(baseline["cookies"]) > 50:
            baseline["cookies"] = baseline["cookies"][-30:]


# ── Singleton ─────────────────────────────────────────────────────────────────
_composite_engine: CompositeSignalEngine | None = None


def get_composite_engine() -> CompositeSignalEngine:
    global _composite_engine
    if _composite_engine is None:
        _composite_engine = CompositeSignalEngine()
    return _composite_engine
