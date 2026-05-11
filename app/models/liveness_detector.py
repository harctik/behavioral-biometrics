"""
Liveness Detector — Bot vs Human Classification.

Determines whether behavioral signals originate from a live human user
or an automated agent (bot, script, RAT replay).

Signals analyzed:
- Touch event presence and variability
- Scroll pattern naturalness
- Cognitive event presence (hesitation, re-reading)
- Motion sensor data (device movement)
- Invisible challenge response patterns
- Input timing entropy
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict

logger = logging.getLogger(__name__)


class LivenessDetector:
    """Scores behavioral signals for human liveness indicators."""

    def analyze(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze features for liveness.

        Returns:
            {
                "liveness_score": float,   # 0.0 = bot, 1.0 = definitely human
                "liveness_flags": list[str],
                "classification": str,     # "human" | "bot" | "uncertain"
            }
        """
        flags: list[str] = []
        evidence_human = 0.0
        evidence_bot = 0.0

        # ── Human indicators ──────────────────────────────────────────

        # Touch events with force variation = real finger
        touch_count = features.get("touch_event_count", 0)
        touch_force_std = features.get("touch_force_std", 0)
        if touch_count > 5 and touch_force_std > 0.01:
            evidence_human += 0.15
            flags.append("liveness:touch_variation_detected")

        # Motion sensor data = real device being held
        motion_count = features.get("motion_event_count", 0)
        motion_std = features.get("motion_acc_std", 0)
        if motion_count > 10 and motion_std > 0.5:
            evidence_human += 0.15
            flags.append("liveness:device_motion_detected")

        # Cognitive signals = human thinking
        hesitation = features.get("hesitation_count", 0)
        reread = features.get("reread_count", 0)
        if hesitation > 0 or reread > 0:
            evidence_human += 0.1
            flags.append("liveness:cognitive_signals_present")

        # Scroll behavior with reversals = human reading
        scroll_reversal = features.get("scroll_reversal_rate", 0)
        if scroll_reversal > 0.05:
            evidence_human += 0.1
            flags.append("liveness:natural_scroll_pattern")

        # Typing rhythm variation = human
        rhythm = features.get("rhythm_consistency", 0)
        if 0.2 < rhythm < 0.95:
            evidence_human += 0.1

        # Error corrections = human
        correction_rate = features.get("correction_rate", 0)
        if 0.01 < correction_rate < 0.3:
            evidence_human += 0.1
            flags.append("liveness:human_error_corrections")

        # Mouse micro-jitter = human hand tremor
        jitter = features.get("micro_jitter_amp", 0)
        if jitter > 0.1:
            evidence_human += 0.1

        # Invisible challenge responses
        challenge_score = features.get("bot_challenge_score", 0)
        if challenge_score < 0.3:
            evidence_human += 0.1

        # ── Bot indicators ────────────────────────────────────────────

        # Zero scroll variation = programmatic
        scroll_vel_std = features.get("scroll_velocity_std", 0)
        scroll_vel_mean = features.get("scroll_velocity_mean", 0)
        if scroll_vel_mean > 0.5 and scroll_vel_std < 0.001:
            evidence_bot += 0.3
            flags.append("liveness:constant_scroll_speed")

        # Superhuman navigation
        nav_dwell = features.get("nav_dwell_mean", 1000)
        if nav_dwell < 50:
            evidence_bot += 0.3
            flags.append("liveness:superhuman_navigation")

        # Zero corrections with fast input
        if correction_rate == 0 and nav_dwell < 200:
            evidence_bot += 0.2
            flags.append("liveness:zero_errors_fast_input")

        # No cognitive events at all
        if hesitation == 0 and reread == 0 and nav_dwell < 100:
            evidence_bot += 0.2
            flags.append("liveness:no_cognitive_signals")

        # Failed invisible challenges
        if challenge_score > 0.7:
            evidence_bot += 0.3
            flags.append("liveness:failed_challenges")

        # ── Score computation ─────────────────────────────────────────

        # Liveness = human evidence minus bot evidence
        liveness = 0.5 + evidence_human - evidence_bot
        liveness = max(0.0, min(1.0, liveness))

        if liveness >= 0.6:
            classification = "human"
        elif liveness <= 0.35:
            classification = "bot"
        else:
            classification = "uncertain"

        return {
            "liveness_score": round(liveness, 4),
            "liveness_flags": flags,
            "classification": classification,
        }
