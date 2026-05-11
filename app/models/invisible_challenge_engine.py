"""
Invisible Challenge Engine — Backend Scoring.

Patent: US20150205955A1 — "differentiating among users based on
responses to injected interferences"

Scores user responses to invisible challenges and builds a
sensorimotor control loop profile per user.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class InvisibleChallengeEngine:
    """Scores challenge responses and detects bots/RATs."""

    # Thresholds calibrated from Behavioral Biometrics research
    BOT_SCORE_THRESHOLD = 0.7
    HUMAN_CORRECTION_TIME_MIN = 50  # ms — too fast = scripted
    HUMAN_CORRECTION_TIME_MAX = 2000  # ms — too slow = no correction

    def __init__(self):
        self.user_profiles: Dict[int, Dict] = {}

    def score_responses(
        self,
        challenge_features: Dict[str, Any],
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Score invisible challenge responses.

        Returns:
            {
                "challenge_risk": float,           # 0–1
                "bot_probability": float,          # 0–1
                "sensorimotor_profile": dict,      # user-unique response pattern
                "profile_match_score": float,      # vs stored baseline (0–1)
                "flags": list[str],
            }
        """
        flags: list[str] = []
        risk = 0.0

        challenge_count = challenge_features.get("challenge_count", challenge_features.get("ch_challenge_count", 0))
        response_count = challenge_features.get("response_count", challenge_features.get("ch_response_count", 0))
        bot_score = challenge_features.get("bot_challenge_score", challenge_features.get("ch_bot_challenge_score", 0))
        correction_time = challenge_features.get("correction_time_mean", challenge_features.get("ch_correction_time_mean", 0))
        correction_acc = challenge_features.get("correction_accuracy_mean", challenge_features.get("ch_correction_accuracy_mean", 0))
        subconscious = challenge_features.get("subconscious_ratio", challenge_features.get("ch_subconscious_ratio", 0))

        # Bot detection: no correction to challenges
        if challenge_count > 0 and response_count == 0:
            risk += 0.8
            flags.append("challenge:no_responses — bot or script")

        if bot_score > self.BOT_SCORE_THRESHOLD:
            risk += 0.5
            flags.append(f"challenge:bot_score({bot_score:.2f})")

        # Superhuman correction time
        if correction_time > 0 and correction_time < self.HUMAN_CORRECTION_TIME_MIN:
            risk += 0.4
            flags.append(f"challenge:superhuman_correction({correction_time:.0f}ms)")

        # No correction at all
        if challenge_count >= 3 and correction_time == 0:
            risk += 0.6
            flags.append("challenge:zero_correction — bot/RAT suspected")

        # Build sensorimotor profile
        profile = {
            "correction_time_mean": correction_time,
            "correction_accuracy": correction_acc,
            "subconscious_ratio": subconscious,
            "mouse_deviation_time": challenge_features.get(
                "mouse_deviation_correction_time", 0
            ),
            "button_shift_time": challenge_features.get(
                "button_micro_shift_correction_time", 0
            ),
        }

        # Profile matching
        match_score = 1.0
        if user_id and user_id in self.user_profiles:
            match_score = self._match_profile(profile, self.user_profiles[user_id])
            if match_score < 0.5:
                risk += 0.3
                flags.append(
                    f"challenge:profile_mismatch({match_score:.2f}) — "
                    "different user at keyboard?"
                )

        # Store profile for future comparison
        if user_id and challenge_count > 0:
            self._update_profile(user_id, profile)

        return {
            "challenge_risk": round(min(1.0, risk), 4),
            "bot_probability": round(min(1.0, bot_score + (risk * 0.3)), 4),
            "sensorimotor_profile": profile,
            "profile_match_score": round(match_score, 4),
            "flags": flags,
        }

    def _match_profile(
        self, current: Dict[str, float], baseline: Dict[str, float]
    ) -> float:
        """Compare current challenge response profile to stored baseline."""
        if not baseline:
            return 1.0

        diffs = []
        for key in [
            "correction_time_mean",
            "correction_accuracy",
            "subconscious_ratio",
        ]:
            c = current.get(key, 0)
            b = baseline.get(key, 0)
            if b > 0:
                diffs.append(abs(c - b) / (b + 1e-6))
            else:
                diffs.append(abs(c))

        if not diffs:
            return 1.0

        avg_diff = sum(diffs) / len(diffs)
        return max(0.0, 1.0 - avg_diff)

    def _update_profile(self, user_id: int, profile: Dict[str, float]):
        """Exponential moving average update of user profile."""
        alpha = 0.3  # Learning rate
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = profile
        else:
            stored = self.user_profiles[user_id]
            for key in profile:
                if isinstance(profile[key], (int, float)):
                    old = stored.get(key, profile[key])
                    stored[key] = old * (1 - alpha) + profile[key] * alpha


# ── Singleton ─────────────────────────────────────────────────────────────────
_challenge_engine: InvisibleChallengeEngine | None = None


def get_challenge_engine() -> InvisibleChallengeEngine:
    global _challenge_engine
    if _challenge_engine is None:
        _challenge_engine = InvisibleChallengeEngine()
    return _challenge_engine
