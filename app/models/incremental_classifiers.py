import numpy as np
from collections import deque
from typing import Dict, List, Tuple, Optional, Any
import logging
logger = logging.getLogger(__name__)

from app.models.base import FeatureConsistencyMixin
from sklearn.neighbors import NearestNeighbors
from sklearn.linear_model import PassiveAggressiveClassifier
from sklearn.preprocessing import StandardScaler
import joblib
import os

class IncrementalKNNClassifier(FeatureConsistencyMixin):
    """Incremental k-NN with sliding window for adaptive learning"""

    def __init__(self, k: int = 5, window_size: int = 1000):
        self.k = k
        self.window_size = window_size
        self.genuine_buffer = deque(maxlen=window_size)
        self.imposter_buffer = deque(maxlen=window_size // 4)  # Smaller imposter buffer
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names = None

    def prepare_data(self, features: List[Dict]) -> np.ndarray:
        """Convert feature dictionaries to matrix"""
        if not features:
            return np.array([])

        # Ensure feature consistency
        features = self._ensure_feature_consistency(features)

        data_matrix = np.array(
            [[f[name] for name in self.feature_names] for f in features]
        )

        return data_matrix

    def update(self, features: Dict, is_genuine: bool):
        """Update the classifier with new data"""
        # Ensure feature consistency for single feature dict
        consistent = self._ensure_feature_consistency([features])
        if not consistent:
            return
        feat = consistent[0]

        if is_genuine:
            self.genuine_buffer.append(feat)
        else:
            self.imposter_buffer.append(feat)

        # Update scaler periodically
        if len(self.genuine_buffer) > 50 and len(self.genuine_buffer) % 20 == 0:
            all_data = list(self.genuine_buffer) + list(self.imposter_buffer)
            if all_data:
                data_matrix = self.prepare_data(all_data)
                self.scaler.fit(data_matrix)
                self.is_trained = True

    def predict(self, features: Dict) -> Tuple[float, float]:
        """Predict authenticity using k-NN"""
        if not self.is_trained or len(self.genuine_buffer) < self.k:
            return 0.5, 0.0

        # Ensure feature consistency for single feature dict
        consistent = self._ensure_feature_consistency([features])
        if not consistent:
            return 0.5, 0.0
        features = consistent[0]

        # Prepare query point
        query_data = self.prepare_data([features])
        if len(query_data) == 0:
            return 0.5, 0.0

        query_data = self.scaler.transform(query_data)
        query_point = query_data[0]

        # Prepare training data
        genuine_data = self.prepare_data(list(self.genuine_buffer))
        imposter_data = self.prepare_data(list(self.imposter_buffer))

        all_data = []
        all_labels = []

        if len(genuine_data) > 0:
            genuine_data = self.scaler.transform(genuine_data)
            all_data.extend(genuine_data)
            all_labels.extend([1] * len(genuine_data))

        if len(imposter_data) > 0:
            imposter_data = self.scaler.transform(imposter_data)
            all_data.extend(imposter_data)
            all_labels.extend([0] * len(imposter_data))

        if len(all_data) < self.k:
            return 0.5, 0.0

        # Find k nearest neighbors
        all_data = np.array(all_data)
        distances = np.linalg.norm(all_data - query_point, axis=1)
        k_nearest_indices = np.argsort(distances)[: self.k]

        # Calculate prediction
        k_nearest_labels = [all_labels[i] for i in k_nearest_indices]
        genuine_votes = sum(k_nearest_labels)
        confidence = abs(genuine_votes / self.k - 0.5) * 2

        return float(genuine_votes / self.k), float(confidence)

    def save(self, filepath: str):
        """Save the classifier state"""
        joblib.dump(
            {
                "genuine_buffer": list(self.genuine_buffer),
                "imposter_buffer": list(self.imposter_buffer),
                "scaler": self.scaler,
                "is_trained": self.is_trained,
                "feature_names": self.feature_names,
            },
            f"{filepath}_knn.pkl",
        )

    def load(self, filepath: str):
        """Load the classifier state"""
        try:
            data = joblib.load(f"{filepath}_knn.pkl")
            self.genuine_buffer = deque(data["genuine_buffer"], maxlen=self.window_size)
            self.imposter_buffer = deque(
                data["imposter_buffer"], maxlen=self.window_size // 4
            )
            self.scaler = data["scaler"]
            self.is_trained = data["is_trained"]
            self.feature_names = data.get("feature_names", None)
            return True
        except Exception:
            logger.exception("Failed to load k-NN artifacts from %s", filepath)
            return False



class PassiveAggressiveDetector(FeatureConsistencyMixin):
    """Passive-Aggressive classifier for online learning"""

    def __init__(self, C: float = 1.0):
        self.model = PassiveAggressiveClassifier(C=C, random_state=42)
        self.scaler = StandardScaler()
        self.is_trained = False
        self.sample_count = 0
        self.feature_names = None

    def prepare_data(self, features: List[Dict]) -> np.ndarray:
        """Convert feature dictionaries to matrix"""
        if not features:
            return np.array([])

        # Ensure feature consistency
        features = self._ensure_feature_consistency(features)

        data_matrix = np.array(
            [[f[name] for name in self.feature_names] for f in features]
        )

        return data_matrix

    def partial_fit(self, features: List[Dict], labels: List[int]):
        """Update model with new data"""
        if not features:
            return

        X = self.prepare_data(features)
        y = np.array(labels)

        if not self.is_trained:
            # Initial fit with scaling
            self.scaler.fit(X)
            X_scaled = self.scaler.transform(X)
            self.model.partial_fit(X_scaled, y, classes=[0, 1])
            self.is_trained = True
        else:
            # Incremental update
            X_scaled = self.scaler.transform(X)
            self.model.partial_fit(X_scaled, y)

        self.sample_count += len(features)

    def predict(self, features: List[Dict]) -> Tuple[float, float]:
        """Predict authenticity probability"""
        if not self.is_trained:
            return 0.5, 0.0

        X = self.prepare_data(features)
        if len(X) == 0:
            return 0.5, 0.0

        X_scaled = self.scaler.transform(X)

        # Get prediction for most recent sample
        prediction = self.model.predict(X_scaled[-1:])[0]

        # Try to get prediction probability
        try:
            if hasattr(self.model, "decision_function"):
                decision_score = self.model.decision_function(X_scaled[-1:])[0]
                # Convert decision score to probability-like score
                probability = 1 / (1 + np.exp(-decision_score))
                confidence = abs(probability - 0.5) * 2
            else:
                probability = float(prediction)
                confidence = 1.0 if prediction in [0, 1] else 0.0
        except Exception:
            logger.exception("Failed to derive PA confidence; using fallback")
            probability = float(prediction)
            confidence = 1.0 if prediction in [0, 1] else 0.0

        return float(probability), float(confidence)

    def save(self, filepath: str):
        """Save the model and scaler"""
        joblib.dump(
            {
                "model": self.model,
                "scaler": self.scaler,
                "is_trained": self.is_trained,
                "sample_count": self.sample_count,
                "feature_names": self.feature_names,
            },
            f"{filepath}_pa.pkl",
        )

    def load(self, filepath: str):
        """Load the model and scaler"""
        try:
            data = joblib.load(f"{filepath}_pa.pkl")
            self.model = data["model"]
            self.scaler = data["scaler"]
            self.is_trained = data["is_trained"]
            self.sample_count = data["sample_count"]
            self.feature_names = data.get("feature_names", None)
            return True
        except Exception:
            logger.exception(
                "Failed to load passive-aggressive artifacts from %s", filepath
            )
            return False


