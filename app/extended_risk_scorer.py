"""
Behavioral Biometrics-inspired Extended Behavioral Risk Scorer.

Processes the 7 new signal streams from the frontend BehavioralCollector
and produces a per-signal risk score and a combined extended_risk_score.

This runs INDEPENDENTLY of the existing 38-feature ML pipeline so
no existing models need retraining. The two scores are fused at the
session level in app_impl.py.

Signal streams processed:
  1. Touch dynamics      — pressure, contact area, velocity
  2. Scroll behavior     — velocity, reversals, depth
  3. Navigation patterns — dwell time, focus entropy, field revisits
  4. Cognitive signals   — hesitation, copy-paste, correction rate, tab switches
  5. Device motion/Gait  — accelerometer magnitude & variance
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ─── Per-signal thresholds (tuned for banking context) ───────────────────────

# Values outside these ranges are flagged as anomalous.
# Derived from Behavioral Biometrics published research + common banking UX patterns.

THRESHOLDS: dict[str, dict[str, float]] = {
    "touch": {
        "force_mean_min": 0.05,
        "force_mean_max": 0.95,
        "area_mean_min": 5.0,
        "area_mean_max": 60.0,
        "velocity_mean_max": 5.0,  # px/ms — anything faster is suspicious
    },
    "scroll": {
        "velocity_mean_max": 3.0,  # px/ms — bots scroll at constant high speed
        "reversal_rate_max": 0.6,  # > 60% reversals = anxious / coached behaviour
        "reversal_rate_min": 0.0,
    },
    "navigation": {
        "dwell_mean_min": 200,  # ms — too fast = bot or scripted
        "dwell_mean_max": 60_000,  # ms — > 60s on a field = confused / coached
        "revisit_max": 3,
        "entropy_min": 0.3,  # very low entropy = scripted navigation
    },
    "cognitive": {
        "correction_rate_max": 0.4,  # > 40% backspaces = unusual
        "copy_paste_max": 2,  # > 2 pastes = suspicious (e.g. pasting account number)
        "tab_switch_max": 3,
        "hesitation_max": 5,
    },
    "motion": {
        "acc_std_min": 0.01,  # Zero motion = desktop (OK) or fixed mount (suspect)
        "acc_std_max": 15.0,  # Extreme movement = being physically coerced?
    },
}


class ExtendedRiskScorer:
    """
    Produces a risk score (0.0 = lowest risk, 1.0 = highest risk)
    for each signal stream and a weighted combined score.
    """

    SIGNAL_WEIGHTS = {
        "touch": 0.15,
        "scroll": 0.15,
        "navigation": 0.25,
        "cognitive": 0.30,  # Highest weight — matches Behavioral Biometrics's approach
        "motion": 0.15,
    }

    def score(self, extended_features: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            extended_features: The `extended_features` dict from the frontend payload.

        Returns:
            {
                "touch_risk":       float,
                "scroll_risk":      float,
                "navigation_risk":  float,
                "cognitive_risk":   float,
                "motion_risk":      float,
                "extended_risk":    float,   # weighted combination
                "flags":            list[str],
                "signals_available": int,    # how many streams had data
            }
        """
        if not extended_features:
            return self._empty_result()

        flags: list[str] = []

        touch_risk = self._score_touch(extended_features, flags)
        scroll_risk = self._score_scroll(extended_features, flags)
        navigation_risk = self._score_navigation(extended_features, flags)
        cognitive_risk = self._score_cognitive(extended_features, flags)
        motion_risk = self._score_motion(extended_features, flags)

        # Count how many streams had actual data
        signals_available = sum(
            [
                extended_features.get("touch_event_count", 0) > 0,
                extended_features.get("scroll_event_count", 0) > 0,
                len(extended_features.get("nav_dwell_mean", [0])) > 0
                if isinstance(extended_features.get("nav_dwell_mean"), list)
                else extended_features.get("nav_dwell_mean", 0) > 0,
                extended_features.get("hesitation_count", 0) >= 0,  # always available
                extended_features.get("motion_event_count", 0) > 0,
            ]
        )

        # Weighted combination — only weight streams that have data
        weights = self.SIGNAL_WEIGHTS.copy()
        if extended_features.get("touch_event_count", 0) == 0:
            weights["touch"] = 0
        if extended_features.get("scroll_event_count", 0) == 0:
            weights["scroll"] = 0
        if extended_features.get("motion_event_count", 0) == 0:
            weights["motion"] = 0

        total_weight = sum(weights.values()) or 1.0
        extended_risk = (
            touch_risk * weights["touch"] / total_weight
            + scroll_risk * weights["scroll"] / total_weight
            + navigation_risk * weights["navigation"] / total_weight
            + cognitive_risk * weights["cognitive"] / total_weight
            + motion_risk * weights["motion"] / total_weight
        )

        return {
            "touch_risk": round(touch_risk, 4),
            "scroll_risk": round(scroll_risk, 4),
            "navigation_risk": round(navigation_risk, 4),
            "cognitive_risk": round(cognitive_risk, 4),
            "motion_risk": round(motion_risk, 4),
            "extended_risk": round(extended_risk, 4),
            "flags": flags,
            "signals_available": signals_available,
        }

    # ── Touch ──────────────────────────────────────────────────────────────

    def _score_touch(self, f: dict, flags: list[str]) -> float:
        if f.get("touch_event_count", 0) < 5:
            return 0.0  # Not enough data — don't penalise

        risk = 0.0
        t = THRESHOLDS["touch"]

        force = f.get("touch_force_mean", 0.5)
        if force < t["force_mean_min"] or force > t["force_mean_max"]:
            risk += 0.3
            flags.append(f"touch:abnormal_force({force:.2f})")

        area = f.get("touch_area_mean", 15)
        if area < t["area_mean_min"] or area > t["area_mean_max"]:
            risk += 0.2
            flags.append(f"touch:abnormal_area({area:.1f})")

        vel = f.get("touch_velocity_mean", 0.5)
        if vel > t["velocity_mean_max"]:
            risk += 0.5
            flags.append(f"touch:high_velocity({vel:.2f}px/ms)")

        return min(1.0, risk)

    # ── Scroll ─────────────────────────────────────────────────────────────

    def _score_scroll(self, f: dict, flags: list[str]) -> float:
        if f.get("scroll_event_count", 0) < 3:
            return 0.0

        risk = 0.0
        t = THRESHOLDS["scroll"]

        vel = f.get("scroll_velocity_mean", 1.0)
        vel_std = f.get("scroll_velocity_std", 0.5)

        # Bot detection: very high speed + very low variance = scripted scrolling
        if vel > t["velocity_mean_max"] and vel_std < 0.1:
            risk += 0.6
            flags.append(f"scroll:bot_pattern(vel={vel:.2f},std={vel_std:.3f})")
        elif vel > t["velocity_mean_max"]:
            risk += 0.3
            flags.append(f"scroll:high_velocity({vel:.2f})")

        rev_rate = f.get("scroll_reversal_rate", 0.2)
        if rev_rate > t["reversal_rate_max"]:
            risk += 0.4
            flags.append(f"scroll:high_reversals({rev_rate:.2f}) — possible coaching")

        return min(1.0, risk)

    # ── Navigation ─────────────────────────────────────────────────────────

    def _score_navigation(self, f: dict, flags: list[str]) -> float:
        risk = 0.0
        t = THRESHOLDS["navigation"]

        dwell = f.get("nav_dwell_mean", 1000)
        if dwell < t["dwell_mean_min"]:
            risk += 0.5
            flags.append(f"nav:too_fast_dwell({dwell:.0f}ms) — bot/scripted")
        elif dwell > t["dwell_mean_max"]:
            risk += 0.2
            flags.append(f"nav:very_slow_dwell({dwell:.0f}ms) — coached?")

        revisits = f.get("nav_field_revisit_count", 0)
        if revisits > t["revisit_max"]:
            risk += 0.3
            flags.append(f"nav:high_revisits({revisits})")

        entropy = f.get("nav_focus_sequence_entropy", 1.0)
        if entropy < t["entropy_min"] and dwell < 500:
            risk += 0.4
            flags.append(f"nav:low_entropy({entropy:.2f}) + fast — scripted navigation")

        return min(1.0, risk)

    # ── Cognitive ──────────────────────────────────────────────────────────

    def _score_cognitive(self, f: dict, flags: list[str]) -> float:
        """
        This is the Behavioral Biometrics-style signal — modelling intent and stress.
        """
        risk = 0.0
        t = THRESHOLDS["cognitive"]

        # Copy-paste into account/amount fields — strong APP fraud indicator
        pastes = f.get("copy_paste_count", 0)
        if pastes > t["copy_paste_max"]:
            risk += 0.5
            flags.append(f"cognitive:copy_paste_count({pastes}) — APP fraud risk")
        elif pastes > 0:
            risk += 0.15

        # Correction rate — too high or too low is suspicious
        cr = f.get("correction_rate", 0.1)
        if cr > t["correction_rate_max"]:
            risk += 0.2
            flags.append(f"cognitive:high_correction_rate({cr:.2f})")
        elif cr == 0.0 and f.get("touch_event_count", 0) == 0:
            # Zero corrections + no touch = possibly scripted input
            risk += 0.1

        # Tab switching during transaction
        tabs = f.get("tab_switch_count", 0)
        if tabs > t["tab_switch_max"]:
            risk += 0.3
            flags.append(f"cognitive:tab_switches({tabs}) — possible coaching")
        elif tabs > 0:
            risk += 0.1

        # Hesitation before submit = user unsure / being coached
        hesitations = f.get("hesitation_count", 0)
        hesitation_duration = f.get("hesitation_duration_mean", 0)
        if hesitations > t["hesitation_max"]:
            risk += 0.4
            flags.append(
                f"cognitive:high_hesitation({hesitations}x, avg {hesitation_duration:.0f}ms)"
            )
        elif hesitations > 2 and hesitation_duration > 3000:
            risk += 0.25
            flags.append(f"cognitive:prolonged_hesitation({hesitation_duration:.0f}ms)")

        # Re-reading = anxious behaviour (mild positive signal in isolation)
        rereads = f.get("reread_count", 0)
        if rereads > 5:
            risk += 0.1
            flags.append(f"cognitive:many_rereads({rereads})")

        # Rapid submit with no hesitation and copy-paste = high-confidence fraud
        if f.get("rapid_submit_detected", 0) and pastes > 0:
            risk += 0.4
            flags.append("cognitive:rapid_submit+paste — HIGH APP FRAUD RISK")

        return min(1.0, risk)

    # ── Motion / Gait ──────────────────────────────────────────────────────

    def _score_motion(self, f: dict, flags: list[str]) -> float:
        if f.get("motion_event_count", 0) < 10:
            return 0.0  # Desktop — skip this signal

        risk = 0.0
        t = THRESHOLDS["motion"]

        acc_std = f.get("motion_acc_std", 1.0)
        if acc_std < t["acc_std_min"]:
            # Phone perfectly still but logging in = suspicious on mobile
            risk += 0.15
            flags.append("motion:zero_movement — phone possibly mounted/scripted")
        elif acc_std > t["acc_std_max"]:
            risk += 0.3
            flags.append(f"motion:extreme_movement({acc_std:.1f}) — physical coercion?")

        return min(1.0, risk)

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _empty_result() -> dict:
        return {
            "touch_risk": 0.0,
            "scroll_risk": 0.0,
            "navigation_risk": 0.0,
            "cognitive_risk": 0.0,
            "motion_risk": 0.0,
            "extended_risk": 0.0,
            "flags": [],
            "signals_available": 0,
        }


# ── Module-level singleton ────────────────────────────────────────────────────
_scorer: ExtendedRiskScorer | None = None


def get_extended_scorer() -> ExtendedRiskScorer:
    global _scorer
    if _scorer is None:
        _scorer = ExtendedRiskScorer()
    return _scorer


def score_extended_features(extended_features: dict) -> dict:
    """Convenience function for use in app_impl.py."""
    return get_extended_scorer().score(extended_features)
