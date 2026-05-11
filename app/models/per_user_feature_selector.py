"""
Per-User Feature Selector — BioCatch-Style Unique Feature Identification.

BioCatch's core differentiator: out of 3,000+ parameters, they select the
20 most unique features PER USER. This means every person's behavioral
fingerprint uses a different subset of signals.

For example:
  - User A might be most distinctive in typing rhythm + scroll speed
  - User B might be most distinctive in mouse curvature + click precision
  - User C might be most distinctive in jitter frequency + hold time CV

This module implements the same concept:
  1. After enrollment, analyze which features are most consistent
     (low intra-user variance) for this specific user
  2. Identify which features are most distinctive compared to population
     (high inter-user variance or distance from population mean)
  3. Select the top N features and assign weights accordingly
  4. Use weighted features for authentication scoring
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Maximum features to select per user
DEFAULT_TOP_N = 20

# Minimum samples before feature selection is reliable
MIN_SAMPLES_FOR_SELECTION = 10


class PerUserFeatureSelector:
    """Selects and weights the most distinctive behavioral features per user.

    The selection process:
      1. Consistency Score: Features with low coefficient of variation
         across the user's sessions are more reliable for that user.
      2. Distinctiveness Score: Features where the user's mean value
         deviates significantly from the population mean are more
         distinctive for identification.
      3. Combined Score: Consistency × Distinctiveness = Feature Importance

    The top N features by combined score are selected, and their
    weights are normalized to sum to 1.0.
    """

    def __init__(self, top_n: int = DEFAULT_TOP_N):
        self.top_n = top_n
        # Per-user feature importance profiles
        self._user_selections: Dict[int, Dict[str, Any]] = {}
        # Population statistics (aggregated across all users)
        self._population_stats: Dict[str, Dict[str, float]] = {}
        self._population_sample_count = 0

    def update_population_stats(self, user_id: int, features: Dict[str, float]):
        """Update population-level statistics with a new user's data.

        Called during enrollment to build the population baseline
        needed for distinctiveness scoring.
        """
        for key, value in features.items():
            if (
                not isinstance(value, (int, float))
                or math.isnan(value)
                or math.isinf(value)
            ):
                continue

            if key not in self._population_stats:
                self._population_stats[key] = {
                    "sum": 0.0,
                    "sum_sq": 0.0,
                    "count": 0,
                    "min": float("inf"),
                    "max": float("-inf"),
                }

            s = self._population_stats[key]
            s["sum"] += value
            s["sum_sq"] += value**2
            s["count"] += 1
            s["min"] = min(s["min"], value)
            s["max"] = max(s["max"], value)

        self._population_sample_count += 1

    def select_features(
        self,
        user_id: int,
        user_profile: Dict[str, Dict[str, float]],
    ) -> Dict[str, Any]:
        """Select the top N most distinctive features for a specific user.

        Args:
            user_id: The user to compute feature selection for.
            user_profile: The user's feature statistics from enrollment.
                Expected format: {feature_name: {"mean": float, "std": float, "count": int}}

        Returns:
            {
                "selected_features": list[str],  # top N feature names
                "feature_weights": dict[str, float],  # normalized weights
                "feature_scores": list[dict],  # detailed scores per feature
                "selection_quality": float,  # 0–1 confidence in selection
            }
        """
        if not user_profile:
            return self._empty_result()

        # Score each feature
        scored_features: List[Tuple[str, float, float, float]] = []

        for feature_name, user_stats in user_profile.items():
            user_mean = user_stats.get("mean", 0)
            user_std = user_stats.get("std", 0)
            user_count = user_stats.get("count", 0)

            if user_count < 2 or user_mean == 0:
                continue

            # 1. Consistency Score (lower CV = more consistent = better)
            cv = user_std / (abs(user_mean) + 1e-6)
            consistency = 1.0 / (1.0 + cv)  # Ranges 0–1, higher is better

            # 2. Distinctiveness Score (how far from population mean)
            distinctiveness = self._compute_distinctiveness(
                feature_name, user_mean, user_std
            )

            # 3. Combined importance score
            # Weight consistency slightly higher — a consistent feature
            # is more valuable even if less distinctive
            importance = consistency * 0.6 + distinctiveness * 0.4

            scored_features.append(
                (feature_name, importance, consistency, distinctiveness)
            )

        if not scored_features:
            return self._empty_result()

        # Sort by importance (descending) and select top N
        scored_features.sort(key=lambda x: x[1], reverse=True)
        selected = scored_features[: self.top_n]

        # Normalize weights to sum to 1.0
        total_importance = sum(s[1] for s in selected) or 1.0
        weights = {s[0]: s[1] / total_importance for s in selected}

        # Build detailed results
        feature_scores = [
            {
                "feature": name,
                "importance": round(importance, 4),
                "consistency": round(consistency, 4),
                "distinctiveness": round(distinctiveness, 4),
                "weight": round(weights.get(name, 0), 4),
            }
            for name, importance, consistency, distinctiveness in selected
        ]

        # Selection quality based on how many features have strong scores
        strong_features = sum(1 for s in selected if s[1] > 0.5)
        selection_quality = min(1.0, strong_features / min(10, self.top_n))

        result = {
            "selected_features": [s[0] for s in selected],
            "feature_weights": weights,
            "feature_scores": feature_scores,
            "selection_quality": round(selection_quality, 4),
        }

        # Cache selection for this user
        self._user_selections[user_id] = result

        logger.info(
            "Feature selection for user %d: %d features selected "
            "(quality: %.2f, top feature: %s)",
            user_id,
            len(selected),
            selection_quality,
            selected[0][0] if selected else "none",
        )

        return result

    def get_weighted_score(
        self,
        user_id: int,
        current_features: Dict[str, float],
        user_profile: Dict[str, Dict[str, float]],
    ) -> Dict[str, Any]:
        """Compute a weighted match score using per-user feature selection.

        This is the main scoring function — called during authentication.
        Uses the previously selected features and their weights to compute
        a match score that emphasizes the user's most distinctive features.

        Args:
            user_id: The user being authenticated.
            current_features: Current session's feature values.
            user_profile: The user's stored baseline profile.

        Returns:
            {
                "weighted_match_score": float,  # 0–1
                "unweighted_match_score": float,  # 0–1 (for comparison)
                "per_feature_scores": dict[str, float],
                "anomalous_features": list[str],
            }
        """
        selection = self._user_selections.get(user_id)
        if not selection:
            # Run selection first
            selection = self.select_features(user_id, user_profile)

        weights = selection.get("feature_weights", {})
        selected = selection.get("selected_features", [])

        if not selected or not user_profile:
            return {
                "weighted_match_score": 0.5,
                "unweighted_match_score": 0.5,
                "per_feature_scores": {},
                "anomalous_features": [],
            }

        weighted_scores = []
        unweighted_scores = []
        per_feature = {}
        anomalous = []

        for feature_name in selected:
            if feature_name not in current_features:
                continue
            if feature_name not in user_profile:
                continue

            current_val = current_features[feature_name]
            baseline = user_profile[feature_name]
            mean = baseline.get("mean", 0)
            std = baseline.get("std", 1e-6)

            if not isinstance(current_val, (int, float)):
                continue
            if math.isnan(current_val) or math.isinf(current_val):
                continue

            # Z-score distance
            z = abs(current_val - mean) / (std + 1e-6)

            # Convert to match score (z=0 → 1.0, z=3 → ~0.1)
            feature_score = 1.0 / (1.0 + (z / 2.0) ** 2)

            weight = weights.get(feature_name, 1.0 / len(selected))
            weighted_scores.append(feature_score * weight)
            unweighted_scores.append(feature_score)
            per_feature[feature_name] = round(feature_score, 4)

            # Flag anomalous features (z > 2.5)
            if z > 2.5:
                anomalous.append(feature_name)

        if not weighted_scores:
            return {
                "weighted_match_score": 0.5,
                "unweighted_match_score": 0.5,
                "per_feature_scores": per_feature,
                "anomalous_features": anomalous,
            }

        weighted_match = sum(weighted_scores)  # Already normalized to sum ≈ 1
        unweighted_match = sum(unweighted_scores) / len(unweighted_scores)

        return {
            "weighted_match_score": round(float(weighted_match), 4),
            "unweighted_match_score": round(float(unweighted_match), 4),
            "per_feature_scores": per_feature,
            "anomalous_features": anomalous,
        }

    def _compute_distinctiveness(
        self, feature_name: str, user_mean: float, user_std: float
    ) -> float:
        """Compute how distinctive a feature value is vs the population."""
        pop = self._population_stats.get(feature_name)

        if not pop or pop["count"] < 2:
            # No population data — assume moderately distinctive
            return 0.5

        # Population mean and std
        pop_mean = pop["sum"] / pop["count"]
        pop_var = (pop["sum_sq"] / pop["count"]) - pop_mean**2
        pop_std = math.sqrt(max(0, pop_var)) + 1e-6

        # Z-score of user's mean vs population
        z = abs(user_mean - pop_mean) / pop_std

        # Convert to 0–1 distinctiveness (z=0 → 0.0, z=2 → ~0.8, z=3 → ~0.9)
        distinctiveness = 1.0 - 1.0 / (1.0 + z)

        return float(min(1.0, distinctiveness))

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "selected_features": [],
            "feature_weights": {},
            "feature_scores": [],
            "selection_quality": 0.0,
        }

    def get_user_selection(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve cached feature selection for a user."""
        return self._user_selections.get(user_id)

    def invalidate_selection(self, user_id: int):
        """Force re-selection of features (e.g., after significant profile update)."""
        self._user_selections.pop(user_id, None)


# ── Singleton ──────────────────────────────────────────────────────────────────
_selector: PerUserFeatureSelector | None = None


def get_feature_selector() -> PerUserFeatureSelector:
    global _selector
    if _selector is None:
        _selector = PerUserFeatureSelector()
    return _selector
