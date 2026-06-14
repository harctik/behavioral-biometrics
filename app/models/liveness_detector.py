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

        # Burst injection detection: flight_time_cv near-zero = automated
        flight_cv = features.get("flight_time_cv", 1.0)
        bigram_mean = features.get("bigram_speed_mean", 150)

        # Suspiciously fast AND robotic rhythm = script injection
        if bigram_mean < 50 and flight_cv < 0.1:
            evidence_bot += 0.4
            flags.append(f"liveness:sub50ms_burst_injection (mean={bigram_mean:.0f}ms, cv={flight_cv:.3f})")
        elif bigram_mean < 80 and flight_cv < 0.15:
            evidence_bot += 0.2
            flags.append(f"liveness:suspicious_burst_speed (mean={bigram_mean:.0f}ms)")

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

        # Zero backspaces over meaningful keycount = inhuman perfection
        total_keys = features.get("total_keystrokes", 0)
        if total_keys > 20 and correction_rate == 0.0:
            evidence_bot += 0.25
            flags.append(f"liveness:zero_errors_over_{int(total_keys)}_keys")

        # Flight time CV near zero = robotic injection
        if flight_cv < 0.05 and total_keys > 30:
            evidence_bot += 0.3
            flags.append(
                f"liveness:robotic_rhythm(cv={flight_cv:.3f}, keys={total_keys})"
            )

        # Zero modifier overlaps on extended typing = no shift usage = script
        mod_count = features.get("modifier_overlap_count", 0)
        if total_keys > 50 and mod_count == 0:
            evidence_bot += 0.15
            flags.append("liveness:zero_modifier_overlaps")

        # ── Digraph-based human indicators ────────────────────────────

        # Natural digraph variance = human (each pair has unique rhythm)
        digraph_stds = [
            v for k, v in features.items()
            if k.startswith("digraph_") and k.endswith("_std") and v > 0
        ]
        if len(digraph_stds) >= 3:
            import numpy as np
            avg_digraph_std = float(np.mean(digraph_stds))
            if avg_digraph_std > 15:  # Natural variance in ms
                evidence_human += 0.1
                flags.append(f"liveness:natural_digraph_variance(avg_std={avg_digraph_std:.0f}ms)")
            elif avg_digraph_std < 3:  # Too consistent = scripted
                evidence_bot += 0.2
                flags.append(f"liveness:uniform_digraph_timing(avg_std={avg_digraph_std:.0f}ms)")

        # Modifier overlap presence = human (bots rarely hold shift naturally)
        mod_mean = features.get("modifier_overlap_mean", 0)
        if mod_count > 0 and 50 < mod_mean < 500:
            evidence_human += 0.08
            flags.append(
                f"liveness:natural_modifier_usage"
                f"(count={mod_count}, mean={mod_mean:.0f}ms)"
            )

        # ── Score computation ─────────────────────────────────────────

        # Liveness = human evidence minus bot evidence
        liveness = 0.5 + evidence_human - evidence_bot
        liveness = max(0.0, min(1.0, liveness))

        # Confidence based on total evidence collected
        total_evidence = evidence_human + evidence_bot
        confidence = min(1.0, total_evidence / 0.8)  # Saturates at 0.8 total

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
            "confidence": round(confidence, 4),
            "evidence_human": round(evidence_human, 4),
            "evidence_bot": round(evidence_bot, 4),
        }

