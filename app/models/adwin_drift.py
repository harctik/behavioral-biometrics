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
        import pickle

        state = {
            "delta": self.delta,
            "max_window_size": self.max_window_size,
            "contexts": self.contexts,
            "drift_history": list(self.drift_history),
            "total_observations": self.total_observations,
        }
        with open(path, "wb") as f:
            pickle.dump(state, f)

    def load(self, path: str):
        """Load ADWIN detector state"""
        import pickle

        with open(path, "rb") as f:
            state = pickle.load(f)
        self.delta = state["delta"]
        self.max_window_size = state["max_window_size"]
        self.contexts = state["contexts"]
        self.drift_history = deque(state["drift_history"], maxlen=100)
        self.total_observations = state["total_observations"]


class BehavioralDriftDetector:
    """Enhanced drift detector using ADWIN for authentication"""

    def __init__(self, delta: float = 0.05, max_window_size: int = 1000):
        self.adwin = ADWINDetector(delta, max_window_size)
        self.user_drifts = {}  # Track drifts per user
        self.global_threshold = 0.8  # Global anomaly threshold

    def add_user_score(self, user_id: int, score: float, context: str = "behavioral"):
        """Add score for specific user"""
        self.adwin.add_behavioral_score(score, user_id, context)

        # Update user drift history
        if user_id not in self.user_drifts:
            self.user_drifts[user_id] = []

        drift_status, drift_info = self.adwin.get_drift_status(
            f"user_{user_id}_{context}"
        )
        if drift_status:
            self.user_drifts[user_id].append(
                {
                    "timestamp": drift_info["timestamp"],
                    "context": context,
                    "score": score,
                    "action": "drift_detected",
                }
            )

    def check_user_drift(self, user_id: int) -> Tuple[bool, List[dict]]:
        """Check if user has drift issues"""
        has_drift = user_id in self.user_drifts and len(self.user_drifts[user_id]) > 0
        return has_drift, self.user_drifts.get(user_id, [])

    def should_recalibrate(self, user_id: int) -> bool:
        """Determine if user needs recalibration"""
        has_drift, drifts = self.check_user_drift(user_id)

        # Recalibrate if drift detected or score too high
        if has_drift:
            return True

        # Check recent scores
        if user_id in self.user_drifts:
            recent_drifts = [
                d
                for d in self.user_drifts[user_id]
                if d["timestamp"] > self.adwin.total_observations - 100
            ]
            if len(recent_drifts) > 5:  # 5+ recent drifts
                return True

        return False

    def get_user_statistics(self, user_id: int) -> dict:
        """Get drift statistics for user"""
        context = f"user_{user_id}_behavioral"
        return self.adwin.get_statistics(context)

    def clear_user_drifts(self, user_id: int):
        """Clear drift history for user"""
        if user_id in self.user_drifts:
            del self.user_drifts[user_id]
        self.adwin.clear_context(f"user_{user_id}_behavioral")

    def save(self, path: str):
        """Save drift detector"""
        import pickle

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
        with open(path, "wb") as f:
            pickle.dump(state, f)

    def load(self, path: str):
        """Load drift detector"""
        import pickle

        with open(path, "rb") as f:
            state = pickle.load(f)

        self.adwin.delta = state["adwin_state"]["delta"]
        self.adwin.max_window_size = state["adwin_state"]["max_window_size"]
        self.adwin.contexts = state["adwin_state"]["contexts"]
        self.adwin.drift_history = deque(
            state["adwin_state"]["drift_history"], maxlen=100
        )
        self.adwin.total_observations = state["adwin_state"]["total_observations"]
        self.user_drifts = state["user_drifts"]
        self.global_threshold = state.get("global_threshold", 0.8)
