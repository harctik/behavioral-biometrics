"""
ADWIN (Adaptive Windowing) Drift Detection
Replaces fixed window with adaptive threshold for dynamic drift detection
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
import logging
from collections import deque

logger = logging.getLogger(__name__)


class ADWINNode:
    """ADWIN tree node for drift detection"""

    def __init__(self, delta: float = 0.05):
        self.delta = delta
        self.width = 0
        self.sum = 0.0
        self.variance = 0.0
        self.n0 = 0
        self.n1 = 0
        self.sum0 = 0.0
        self.sum1 = 0.0
        self.var0 = 0.0
        self.var1 = 0.0
        self.m0 = 0.0
        self.m1 = 0.0
        self.cut_point = -1
        self.delta = delta
        self.drift = False

    def add_observation(self, value: float):
        """Add observation to the window"""
        self.width += 1
        self.sum += value

        if self.width == 1:
            self.variance = 0.0
            self.n0 = 0
            self.n1 = 1
            self.sum0 = 0.0
            self.sum1 = value
            self.var0 = 0.0
            self.var1 = 0.0
            self.m0 = 0.0
            self.m1 = value
            self.cut_point = -1
            self.drift = False
        else:
            # Calculate new mean
            new_mean = self.sum / self.width

            # Update variance
            if self.width > 1:
                self.variance = (
                    (self.width - 1)
                    / self.width
                    * (
                        self.variance
                        + (value - self.m1) * (value - new_mean) / self.width
                    )
                )

            # Update statistics
            for cut_point in range(1, self.width):
                self.n0 = cut_point
                self.n1 = self.width - cut_point

                self.sum0 = (
                    self.sum0 + value
                    if cut_point == self.width - 1
                    else self.sum * self.n0 / self.width
                )
                self.sum1 = self.sum - self.sum0

                self.m0 = self.sum0 / self.n0 if self.n0 > 0 else 0.0
                self.m1 = self.sum1 / self.n1 if self.n1 > 0 else 0.0

                # Calculate variance for each window
                if self.n0 > 1:
                    self.var0 = (
                        self.variance * self.width / (self.n0 * (self.width - 1))
                    )
                if self.n1 > 1:
                    self.var1 = (
                        self.variance * self.width / (self.n1 * (self.width - 1))
                    )

                # Calculate delta for this cut point
                delta_cut = np.sqrt(
                    2 * self.variance * np.log(2 / self.delta) / (self.n0 * self.n1)
                )

                # Check if cut point is significant
                if abs(self.m1 - self.m0) > delta_cut:
                    self.cut_point = cut_point
                    self.drift = True
                    break

            # Remove old observations if drift detected
            if self.drift:
                self.width = self.cut_point
                self.sum = self.sum0
                self.variance = self.var0


class ADWINDetector:
    """ADWIN drift detector for behavioral authentication"""

    def __init__(self, delta: float = 0.05, max_window_size: int = 1000):
        self.delta = delta
        self.max_window_size = max_window_size
        self.windows = []
        self.contexts = {}  # Separate ADWIN for each context
        self.drift_history = deque(maxlen=100)
        self.total_observations = 0

    def add_observation(self, value: float, context: str = "default"):
        """Add observation to ADWIN detector"""
        self.total_observations += 1

        # Get or create ADWIN node for this context
        if context not in self.contexts:
            self.contexts[context] = ADWINNode(self.delta)

        node = self.contexts[context]
        node.add_observation(value)

        if node.drift:
            self.drift_history.append(
                {
                    "timestamp": self.total_observations,
                    "context": context,
                    "cut_point": node.cut_point,
                    "value": value,
                    "delta": self.delta,
                }
            )
            logger.warning(
                f"Drift detected in context {context} at observation {self.total_observations}"
            )

            # Reset window
            self.contexts[context] = ADWINNode(self.delta)

    def add_behavioral_score(
        self, score: float, user_id: int, context: str = "behavioral"
    ):
        """Add behavioral anomaly score for drift detection"""
        context_key = f"user_{user_id}_{context}"
        self.add_observation(score, context_key)

    def get_drift_status(self, context: str = "default") -> Tuple[bool, Optional[dict]]:
        """Check if drift is detected in specific context"""
        if context in self.contexts:
            return self.contexts[context].drift, self.get_last_drift(context)
        return False, None

    def get_last_drift(self, context: str = "default") -> Optional[dict]:
        """Get last drift information"""
        return self.drift_history[-1] if self.drift_history else None

    def get_statistics(self, context: str = "default") -> dict:
        """Get statistics for a context"""
        if context not in self.contexts:
            return {}

        node = self.contexts[context]
        return {
            "width": node.width,
            "mean": node.sum / node.width if node.width > 0 else 0.0,
            "variance": node.variance,
            "n0": node.n0,
            "n1": node.n1,
            "drift": node.drift,
            "cut_point": node.cut_point,
        }

    def clear_context(self, context: str):
        """Clear drift detection for a specific context"""
        if context in self.contexts:
            del self.contexts[context]

    def save(self, path: str):
        """Save ADWIN detector state"""
        import joblib

        state = {
            "delta": self.delta,
            "max_window_size": self.max_window_size,
            "contexts": self.contexts,
            "drift_history": list(self.drift_history),
            "total_observations": self.total_observations,
        }
        joblib.dump(state, path)

    def load(self, path: str):
        """Load ADWIN detector state"""
        import joblib

        state = joblib.load(path)
        self.delta = state["delta"]
        self.max_window_size = state["max_window_size"]
        self.contexts = state["contexts"]
        self.drift_history = deque(state["drift_history"], maxlen=100)
        self.total_observations = state["total_observations"]


class BehavioralDriftDetector:
    """Enhanced multi-stream drift detector for authentication.

    Monitors 6 key behavioral feature streams simultaneously:
    - flight_time_mean, hold_time_mean, typing_speed_wpm
    - rhythm_consistency, correction_rate, modifier_overlap_mean

    Features:
    - Per-user, per-feature ADWIN windows
    - EMA-smoothed severity scoring
    - Cooldown period to prevent alert fatigue
    - Drift-rate-per-hour metric for SOC dashboards
    """

    MONITORED_FEATURES = [
        "flight_time_mean",
        "hold_time_mean",
        "typing_speed_wpm",
        "rhythm_consistency",
        "correction_rate",
        "modifier_overlap_mean",
    ]

    def __init__(
        self,
        delta: float = 0.05,
        max_window_size: int = 1000,
        cooldown_observations: int = 20,
    ):
        self.adwin = ADWINDetector(delta, max_window_size)
        self.user_drifts: Dict[int, List[dict]] = {}
        self.global_threshold = 0.8
        self._cooldown = cooldown_observations
        self._user_last_drift_obs: Dict[str, int] = {}  # per context
        self._ema_severity: Dict[int, float] = {}  # EMA severity per user

    def add_user_score(
        self,
        user_id: int,
        score: float,
        context: str = "behavioral",
    ):
        """Add single-metric score for a user (legacy API)."""
        self._add_observation(user_id, score, context)

    def add_user_features(
        self,
        user_id: int,
        features: Dict[str, float],
    ):
        """Add multiple feature streams simultaneously.

        Monitors each of the 6 key features in its own ADWIN window,
        enabling fine-grained drift detection per behavioral signal.
        """
        for feat_name in self.MONITORED_FEATURES:
            val = features.get(feat_name)
            if val is not None and isinstance(val, (int, float)):
                self._add_observation(user_id, float(val), feat_name)

    def _add_observation(self, user_id: int, value: float, context: str):
        """Internal: add observation with cooldown check."""
        ctx_key = f"user_{user_id}_{context}"
        self.adwin.add_behavioral_score(value, user_id, context)

        drift_status, drift_info = self.adwin.get_drift_status(ctx_key)
        if not drift_status:
            return

        # Cooldown: ignore if too close to last drift on same stream
        last_obs = self._user_last_drift_obs.get(ctx_key, -9999)
        if self.adwin.total_observations - last_obs < self._cooldown:
            return

        self._user_last_drift_obs[ctx_key] = self.adwin.total_observations

        if user_id not in self.user_drifts:
            self.user_drifts[user_id] = []

        self.user_drifts[user_id].append(
            {
                "timestamp": drift_info["timestamp"] if drift_info else self.adwin.total_observations,
                "context": context,
                "score": value,
                "action": "drift_detected",
                "stream": context,
            }
        )

        # Update EMA severity
        alpha = 0.3
        old = self._ema_severity.get(user_id, 0.0)
        self._ema_severity[user_id] = old * (1 - alpha) + 1.0 * alpha

        logger.warning(
            "Drift on stream '%s' for user %d (obs=%d, val=%.4f)",
            context, user_id, self.adwin.total_observations, value,
        )

    def check_user_drift(self, user_id: int) -> Tuple[bool, List[dict]]:
        """Check if user has drift issues."""
        has_drift = user_id in self.user_drifts and len(self.user_drifts[user_id]) > 0
        return has_drift, self.user_drifts.get(user_id, [])

    def get_drift_severity(self, user_id: int) -> float:
        """Get EMA-smoothed drift severity (0 = no drift, 1 = severe)."""
        return self._ema_severity.get(user_id, 0.0)

    def get_drift_rate_per_hour(self, user_id: int) -> float:
        """Compute drifts-per-hour metric for SOC dashboards."""
        drifts = self.user_drifts.get(user_id, [])
        if len(drifts) < 2:
            return 0.0
        span = drifts[-1]["timestamp"] - drifts[0]["timestamp"]
        if span <= 0:
            return 0.0
        # Estimate: assume ~1 obs/second for rate calculation
        hours = span / 3600.0
        return len(drifts) / max(hours, 0.001)

    def should_recalibrate(self, user_id: int) -> bool:
        """Determine if user needs recalibration."""
        has_drift, drifts = self.check_user_drift(user_id)

        if not has_drift:
            return False

        # Recalibrate if severity is high
        if self.get_drift_severity(user_id) > 0.6:
            return True

        # Or if many recent drifts across multiple streams
        recent_drifts = [
            d
            for d in drifts
            if d["timestamp"] > self.adwin.total_observations - 100
        ]
        unique_streams = len(set(d.get("stream", "") for d in recent_drifts))
        if len(recent_drifts) > 5 or unique_streams >= 3:
            return True

        return False

    def get_user_statistics(self, user_id: int) -> dict:
        """Get drift statistics for user."""
        stats = {}
        for feat in self.MONITORED_FEATURES:
            ctx = f"user_{user_id}_{feat}"
            feat_stats = self.adwin.get_statistics(ctx)
            if feat_stats:
                stats[feat] = feat_stats

        stats["severity"] = self.get_drift_severity(user_id)
        stats["drift_rate_per_hour"] = self.get_drift_rate_per_hour(user_id)
        stats["total_drifts"] = len(self.user_drifts.get(user_id, []))
        return stats

    def clear_user_drifts(self, user_id: int):
        """Clear drift history for user."""
        if user_id in self.user_drifts:
            del self.user_drifts[user_id]
        if user_id in self._ema_severity:
            del self._ema_severity[user_id]
        for feat in self.MONITORED_FEATURES:
            self.adwin.clear_context(f"user_{user_id}_{feat}")
        self.adwin.clear_context(f"user_{user_id}_behavioral")

    def save(self, path: str):
        """Save drift detector"""
        import joblib

        state = {
            "adwin_state": {
                "delta": self.adwin.delta,
                "max_window_size": self.adwin.max_window_size,
                "contexts": self.adwin.contexts,
                "drift_history": list(self.adwin.drift_history),
                "total_observations": self.adwin.total_observations,
            },
            "user_drifts": self.user_drifts,
            "global_threshold": self.global_threshold,
        }
        joblib.dump(state, path)

    def load(self, path: str):
        """Load drift detector"""
        import joblib

        state = joblib.load(path)

        self.adwin.delta = state["adwin_state"]["delta"]
        self.adwin.max_window_size = state["adwin_state"]["max_window_size"]
        self.adwin.contexts = state["adwin_state"]["contexts"]
        self.adwin.drift_history = deque(
            state["adwin_state"]["drift_history"], maxlen=100
        )
        self.adwin.total_observations = state["adwin_state"]["total_observations"]
        self.user_drifts = state["user_drifts"]
        self.global_threshold = state.get("global_threshold", 0.8)
