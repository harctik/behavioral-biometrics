"""
UserManager: Lazy-load and cache per-user ML components.
"""

from typing import Dict
from collections import deque
import os
import logging

from app.feature_extractor import BehavioralFeatureExtractor
from app.drift_detector import BehavioralDriftDetector
from app.models.ml_models import EnsembleBehavioralClassifier

from app.config import Settings

settings = Settings()

logger = logging.getLogger(__name__)


class UserManager:
    def __init__(self, models_base_path: str):
        self.models_base_path = models_base_path
        self._models: Dict[int, EnsembleBehavioralClassifier] = {}
        self._extractors: Dict[int, BehavioralFeatureExtractor] = {}
        self._drift_detectors: Dict[int, BehavioralDriftDetector] = {}
        self._buffers: Dict[int, Dict[str, deque]] = {}

    def get_model(self, user_id: int) -> EnsembleBehavioralClassifier:
        """Get or initialize the ensemble model for a user."""
        if user_id not in self._models:
            model_path = os.path.join(self.models_base_path, str(user_id))
            os.makedirs(model_path, exist_ok=True)
            self._models[user_id] = EnsembleBehavioralClassifier(user_id, model_path)
            self._models[user_id].load_all_models()
            logger.info(f"Initialized ML model for user {user_id}")
        return self._models[user_id]

    def get_extractor(self, user_id: int) -> BehavioralFeatureExtractor:
        """Get or initialize the feature extractor for a user."""
        if user_id not in self._extractors:
            # Window size should be configurable; we'll pull from settings later.
            self._extractors[user_id] = BehavioralFeatureExtractor(window_size=30)
            logger.info(f"Initialized feature extractor for user {user_id}")
        return self._extractors[user_id]

    def get_drift_detector(self, user_id: int) -> BehavioralDriftDetector:
        """Retrieve or create drift detector for a user."""
        if user_id not in self._drift_detectors:
            self._drift_detectors[user_id] = BehavioralDriftDetector(
                window_size=100, alpha=0.01, min_samples=10
            )
            logger.info(f"Initialized drift detector for user {user_id}")
        return self._drift_detectors[user_id]

    def get_buffer(self, user_id: int) -> Dict[str, deque]:
        """Get or create behavioral buffers for a user.

        Returns a dict with keys ``keystroke``, ``mouse``, ``recent_features``.
        Each entry is a ``deque`` with a maxlen defined by config constants.
        """
        if user_id not in self._buffers:
            keystroke_max = settings.KEYSTROKE_BUFFER_SIZE
            mouse_max = settings.MOUSE_BUFFER_SIZE
            recent_max = settings.FEATURE_UPDATE_INTERVAL
            self._buffers[user_id] = {
                "keystroke": deque(maxlen=keystroke_max),
                "mouse": deque(maxlen=mouse_max),
                "recent_features": deque(maxlen=recent_max),
            }
            logger.info(f"Initialized behavioral buffers for user {user_id}")
        return self._buffers[user_id]

    def clear_user(self, user_id: int):
        """Clear cached components for a user (e.g., on logout or model retrain)."""
        self._models.pop(user_id, None)
        self._extractors.pop(user_id, None)
        self._drift_detectors.pop(user_id, None)
        logger.info(f"Cleared cached components for user {user_id}")
