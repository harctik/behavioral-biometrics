import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import logging
logger = logging.getLogger(__name__)

class FeatureConsistencyMixin:
    """Mixin class to handle feature consistency across models"""

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


