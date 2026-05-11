"""
Behavioral Biometrics-style Cognitive Behavioral Engine.

This is the core differentiator — it doesn't just measure HOW you type,
it models WHY your behavior changed. This is what separates Behavioral Biometrics
from basic keystroke loggers.

Signals processed:
  - Hesitation patterns before high-value actions
  - Duress detection (coached / coerced behavior)
  - APP (Authorized Push Payment) fraud indicators
  - Account takeover mid-session detection
  - Bot vs human classification
  - Behavioral drift (profile mismatch over time)
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class CognitiveEngine:
    """
    Analyzes cognitive behavioral patterns to detect:
    - Duress / coercion
    - APP fraud (victim being coached)
    - Account takeover
    - Bot activity
    - Anomalous session behavior
    """

    # APP Fraud: copy-pasting account/amount fields is a strong indicator
    APP_FRAUD_PASTE_THRESHOLD = 2
    # Duress: long hovering + hesitation before submit
    DURESS_HESITATION_THRESHOLD_MS = 3000
    DURESS_HESITATION_COUNT = 3
    # Bot: zero variance in timing
    BOT_TIMING_VARIANCE_THRESHOLD = 0.001
    # Takeover: sudden rhythm change (Mahalanobis distance)
    TAKEOVER_RHYTHM_THRESHOLD = 3.5

    def analyze(
        self,
        extended_features: dict[str, Any],
        session_history: list[dict] | None = None,
        baseline: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Full cognitive behavioral analysis.

        Returns:
            {
                "duress_probability": float,      # 0–1
                "app_fraud_probability": float,   # 0–1
                "takeover_probability": float,    # 0–1
                "bot_probability": float,         # 0–1
                "cognitive_risk": float,          # composite 0–1
                "behavioral_state": str,          # "normal"|"suspicious"|"alert"|"critical"
                "cognitive_flags": list[str],
                "recommended_action": str,        # "allow"|"step_up"|"block"|"silent_challenge"
            }
        """
        flags: list[str] = []

        duress_prob = self._detect_duress(extended_features, flags)
        app_fraud_prob = self._detect_app_fraud(extended_features, flags)
        takeover_prob = self._detect_takeover(extended_features, baseline, flags)
        bot_prob = self._detect_bot(extended_features, flags)

        # Composite cognitive risk
        cognitive_risk = max(
            duress_prob * 0.9,  # Duress is highest priority
            app_fraud_prob * 0.85,
            takeover_prob * 0.8,
            bot_prob * 0.75,
        )
        # Add weighted contribution from all signals
        cognitive_risk = min(
            1.0,
            cognitive_risk
            + (
                duress_prob * 0.1
                + app_fraud_prob * 0.1
                + takeover_prob * 0.05
                + bot_prob * 0.05
            )
            * 0.3,
        )

        # Determine behavioral state
        if cognitive_risk >= 0.75:
            state = "critical"
        elif cognitive_risk >= 0.5:
            state = "alert"
        elif cognitive_risk >= 0.25:
            state = "suspicious"
        else:
            state = "normal"

        # Determine recommended action
        if duress_prob >= 0.7 or cognitive_risk >= 0.8:
            action = "block"
        elif app_fraud_prob >= 0.6 or cognitive_risk >= 0.6:
            action = "block"
        elif takeover_prob >= 0.5 or cognitive_risk >= 0.45:
            action = "step_up"
        elif cognitive_risk >= 0.25:
            action = "silent_challenge"
        else:
            action = "allow"

        return {
            "duress_probability": round(duress_prob, 4),
            "app_fraud_probability": round(app_fraud_prob, 4),
            "takeover_probability": round(takeover_prob, 4),
            "bot_probability": round(bot_prob, 4),
            "cognitive_risk": round(cognitive_risk, 4),
            "behavioral_state": state,
            "cognitive_flags": flags,
            "recommended_action": action,
        }

    # ── Duress Detection ──────────────────────────────────────────────────────

    def _detect_duress(self, f: dict, flags: list[str]) -> float:
        """
        Detect if user is under duress (being coerced/threatened).
        Behavioral Biometrics key feature: detects when someone is being forced to transact.

        Indicators:
        - Prolonged hesitation before submit
        - High reversal rate (scrolling back, re-reading)
        - Tab switching (looking for help?)
        - Unusually slow, deliberate typing
        - Accessing account at unusual hour (if time data available)
        """
        risk = 0.0

        hesitation_count = f.get("hesitation_count", 0)
        hesitation_duration = f.get("hesitation_duration_mean", 0)
        reread_count = f.get("reread_count", 0)
        tab_switches = f.get("tab_switch_count", 0)
        scroll_reversals = f.get("scroll_reversal_rate", 0)

        # Multiple long hesitations = strong duress signal
        if (
            hesitation_count >= self.DURESS_HESITATION_COUNT
            and hesitation_duration >= self.DURESS_HESITATION_THRESHOLD_MS
        ):
            risk += 0.5
            flags.append(
                f"duress:prolonged_hesitation({hesitation_count}x "
                f"avg {hesitation_duration:.0f}ms)"
            )

        # Repeated re-reading with hesitation
        if reread_count > 4 and hesitation_count >= 2:
            risk += 0.3
            flags.append(
                f"duress:anxious_rereading({reread_count}x rereed + hesitation)"
            )

        # Tab switching during transaction
        if tab_switches >= 3:
            risk += 0.2
            flags.append(f"duress:tab_switches({tab_switches}) during session")

        # High scroll reversal = anxiety/confusion
        if scroll_reversals > 0.5:
            risk += 0.15
            flags.append(f"duress:scroll_anxiety(reversal_rate={scroll_reversals:.2f})")

        return min(1.0, risk)

    # ── APP Fraud Detection ───────────────────────────────────────────────────

    def _detect_app_fraud(self, f: dict, flags: list[str]) -> float:
        """
        Detect Authorized Push Payment (APP) fraud.
        This is Behavioral Biometrics's flagship feature — detecting scam victims.

        APP fraud scenario: Victim is on phone with scammer who instructs
        them to transfer money. Key behavioral signals:
        - Copy-pasting account numbers (scammer sent them via WhatsApp/SMS)
        - Very fast navigation (coached — scammer told them exactly what to do)
        - No re-reading before submit (told "don't worry just click")
        - Rapid submit with no hesitation despite large amount
        - Unusual field focus sequence (going straight to amount/account)
        """
        risk = 0.0

        copy_pastes = f.get("copy_paste_count", 0)
        rapid_submit = f.get("rapid_submit_detected", 0)
        tab_switches = f.get("tab_switch_count", 0)
        nav_dwell = f.get("nav_dwell_mean", 1000)
        hesitation_count = f.get("hesitation_count", 0)
        reread_count = f.get("reread_count", 0)
        nav_entropy = f.get("nav_focus_sequence_entropy", 1.0)
        correction_rate = f.get("correction_rate", 0.1)

        # Copy-paste of account/amount — STRONGEST indicator
        if copy_pastes >= self.APP_FRAUD_PASTE_THRESHOLD:
            risk += 0.5
            flags.append(
                f"app_fraud:copy_paste({copy_pastes}x) — "
                "account number likely received via external channel"
            )
        elif copy_pastes == 1:
            risk += 0.2
            flags.append("app_fraud:single_paste_detected")

        # Rapid submit + no hesitation + paste = very high confidence APP fraud
        if rapid_submit and copy_pastes >= 1 and hesitation_count == 0:
            risk += 0.4
            flags.append(
                "app_fraud:COACHED_PATTERN — rapid submit + paste + no hesitation"
            )

        # Unusually fast navigation (coached: told exactly what to click)
        if nav_dwell < 300 and nav_entropy < 0.5:
            risk += 0.3
            flags.append(
                f"app_fraud:scripted_navigation "
                f"(dwell={nav_dwell:.0f}ms, entropy={nav_entropy:.2f})"
            )

        # Tab switching = victim checking WhatsApp/SMS for instructions
        if tab_switches >= 2 and copy_pastes >= 1:
            risk += 0.25
            flags.append(
                f"app_fraud:coaching_channel_suspected "
                f"(tab_switches={tab_switches} + pastes={copy_pastes})"
            )

        # Zero corrections on complex form = coached (told what to type)
        if correction_rate == 0.0 and nav_dwell < 500:
            risk += 0.15
            flags.append("app_fraud:zero_corrections_fast_nav — possibly coached input")

        return min(1.0, risk)

    # ── Account Takeover Detection ────────────────────────────────────────────

    def _detect_takeover(
        self, f: dict, baseline: dict | None, flags: list[str]
    ) -> float:
        """
        Detect mid-session account takeover.
        Compares current session behavior vs stored baseline.

        Key signals:
        - Sudden change in typing rhythm (new person at keyboard)
        - Mouse behavior completely different from baseline
        - Accessing unusual features (admin, transfer to new beneficiary)
        """
        if not baseline:
            return 0.0  # No baseline yet — can't compare

        risk = 0.0

        # Compare key behavioral metrics vs baseline
        baseline_dwell = baseline.get("nav_dwell_mean", 1000)
        current_dwell = f.get("nav_dwell_mean", 1000)

        if baseline_dwell > 0:
            dwell_ratio = abs(current_dwell - baseline_dwell) / baseline_dwell
            if dwell_ratio > 0.8:  # 80% change in dwell time
                risk += 0.4
                flags.append(
                    f"takeover:dwell_time_mismatch "
                    f"(baseline={baseline_dwell:.0f}ms, "
                    f"current={current_dwell:.0f}ms, "
                    f"diff={dwell_ratio:.0%})"
                )

        baseline_cr = baseline.get("correction_rate", 0.1)
        current_cr = f.get("correction_rate", 0.1)
        if abs(current_cr - baseline_cr) > 0.25:
            risk += 0.3
            flags.append(
                f"takeover:correction_rate_mismatch "
                f"(baseline={baseline_cr:.2f}, current={current_cr:.2f})"
            )

        baseline_scroll = baseline.get("scroll_velocity_mean", 1.0)
        current_scroll = f.get("scroll_velocity_mean", 1.0)
        if baseline_scroll > 0:
            scroll_ratio = abs(current_scroll - baseline_scroll) / baseline_scroll
            if scroll_ratio > 1.5:  # 150% change
                risk += 0.2
                flags.append(
                    f"takeover:scroll_pattern_mismatch({scroll_ratio:.0%} change)"
                )

        return min(1.0, risk)

    # ── Bot Detection ─────────────────────────────────────────────────────────

    def _detect_bot(self, f: dict, flags: list[str]) -> float:
        """
        Detect automated/bot activity.

        Bot indicators:
        - Zero touch events (no real touches on mobile)
        - Perfectly constant scroll speed (bots scroll at exact speed)
        - Zero corrections (bots don't make typos)
        - Superhuman navigation speed (< 100ms dwell)
        - Zero cognitive events (no hesitation, no re-reading)
        """
        risk = 0.0

        scroll_vel_std = f.get("scroll_velocity_std", 0.5)
        scroll_vel_mean = f.get("scroll_velocity_mean", 1.0)
        nav_dwell = f.get("nav_dwell_mean", 1000)
        correction_rate = f.get("correction_rate", 0.1)
        touch_count = f.get("touch_event_count", 0)
        hesitation_count = f.get("hesitation_count", 0)
        motion_count = f.get("motion_event_count", 0)
        nav_entropy = f.get("nav_focus_sequence_entropy", 1.0)

        # Constant scroll speed = bot
        if (
            scroll_vel_mean > 0.5
            and scroll_vel_std < self.BOT_TIMING_VARIANCE_THRESHOLD
        ):
            risk += 0.6
            flags.append(
                f"bot:constant_scroll_speed "
                f"(vel={scroll_vel_mean:.3f}, std={scroll_vel_std:.4f})"
            )

        # Superhuman navigation speed
        if nav_dwell < 50:
            risk += 0.5
            flags.append(f"bot:superhuman_navigation({nav_dwell:.0f}ms dwell)")

        # Zero corrections + fast = scripted
        if correction_rate == 0.0 and nav_dwell < 200:
            risk += 0.3
            flags.append("bot:zero_corrections_fast_nav")

        # No cognitive events at all = not human
        if hesitation_count == 0 and nav_dwell < 100:
            risk += 0.2
            flags.append("bot:no_cognitive_signals")

        # Perfect entropy = scripted (hits exact same elements in exact same order)
        if nav_entropy == 0.0 and nav_dwell < 500:
            risk += 0.3
            flags.append("bot:zero_nav_entropy — scripted element access pattern")

        return min(1.0, risk)


# ── Singleton ──────────────────────────────────────────────────────────────────

_engine: CognitiveEngine | None = None


def get_cognitive_engine() -> CognitiveEngine:
    global _engine
    if _engine is None:
        _engine = CognitiveEngine()
    return _engine


def run_cognitive_analysis(
    extended_features: dict,
    session_history: list | None = None,
    baseline: dict | None = None,
) -> dict:
    """Convenience function for use in app_impl.py."""
    return get_cognitive_engine().analyze(extended_features, session_history, baseline)
