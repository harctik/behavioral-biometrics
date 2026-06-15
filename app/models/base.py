import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import logging
logger = logging.getLogger(__name__)

class FeatureConsistencyMixin:
    """Mixin class to handle feature consistency across models"""

    def _ensure_feature_consistency(self, features: List[Dict]) -> List[Dict]:
        """Ensure all feature dicts have the same keys in the same order.

        - On first call (feature_names is None): learns the feature schema
          from the union of all keys across samples.
        - Fills missing keys with 0.0 so every sample has identical shape.
        - Filters out non-numeric values (strings, None).

        Args:
            features: List of feature dictionaries (possibly ragged).

        Returns:
            List of feature dictionaries with identical keys.
        """
        if not features:
            return features

        if not hasattr(self, "feature_names") or self.feature_names is None:
            # Learn feature schema from all samples
            all_keys = set()
            for f in features:
                all_keys.update(k for k, v in f.items() if isinstance(v, (int, float)))
            self.feature_names = sorted(all_keys)

        # Normalize all samples to the learned schema
        consistent = []
        for f in features:
            normalized = {}
            for key in self.feature_names:
                val = f.get(key, 0.0)
                if isinstance(val, (int, float)):
                    normalized[key] = float(val) if np.isfinite(float(val)) else 0.0
                else:
                    normalized[key] = 0.0
            consistent.append(normalized)

        return consistent

    def _prepare_data(
        self, features: List[Dict], scaler: Any = None, fit: bool = True
    ) -> np.ndarray:
        """Convert feature dictionaries to normalized matrix"""
        if not features:
            return np.array([])

        features = self._ensure_feature_consistency(features)

        data_matrix = np.array(
            [[f[name] for name in self.feature_names] for f in features]
        )

        if scaler is not None:
            if fit:
                data_matrix = scaler.fit_transform(data_matrix)
            else:
                data_matrix = scaler.transform(data_matrix)

        return data_matrix
