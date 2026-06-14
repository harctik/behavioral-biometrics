import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import logging
logger = logging.getLogger(__name__)

from app.models.sequence_models import GRUSequenceModel
from app.models.anomaly_detectors import AutoencoderAnomalyDetector, OneClassSVMDetector
from app.models.incremental_classifiers import IncrementalKNNClassifier
from app.models.analytics_and_security import BehavioralAnalytics, SessionSecurityMonitor, AuditLogger
from sklearn.preprocessing import StandardScaler
import os
import joblib
class EnsembleBehavioralClassifier:
    """Banking-grade ensemble of behavioral models for robust authentication.

    Integrates 7 models + Duress Detector + Siamese Network:
    - BehavioralTransformerEncoder (primary — 4-head self-attention)
    - Autoencoder (reconstruction anomaly detection)
    - One-Class SVM (outlier boundary learning)
    - Isolation Forest (ensemble anomaly isolation)
    - LSTM (navigation sequence patterns)
    - GRU (legacy recurrent — lower weight)
    - Cognitive Engine (behavioral analytics)
    - Duress/coercion detection engine
    - Siamese Network for maker-checker verification

    Progressive Enrollment:
    - Day 1-3: OC-SVM + Isolation Forest only (bootstrap phase)
    - Day 4-7: Adds Transformer + k-NN (building phase)
    - Day 8+: Full ensemble activated (mature phase)
    """

    ENROLLMENT_PHASES = {
        "bootstrap": {"days": 3, "models": ["svm", "isolation", "knn"]},
        "building": {"days": 7, "models": ["svm", "isolation", "knn", "transformer", "pa"]},
        "mature": {
            "days": float("inf"),
            "models": ["transformer", "autoencoder", "svm", "knn", "pa", "isolation", "gru"],
        },
    }

    def __init__(self, user_id: int, models_path: str):
        self.user_id = user_id
        self.models_path = os.path.join(models_path, str(user_id))
        os.makedirs(self.models_path, exist_ok=True)

        # Initialize all models
        self.gru_model = GRUSequenceModel()
        self.autoencoder = AutoencoderAnomalyDetector()
        self.svm_detector = OneClassSVMDetector()
        self.knn_classifier = IncrementalKNNClassifier()
        self.pa_classifier = PassiveAggressiveDetector()
        self.isolation_forest = IsolationForestDetector()

        # BehavioralTransformerEncoder — primary sequence model
        self.transformer_model = None
        self._init_transformer()

        # Banking-grade extensions
        self.duress_detector = None
        self.siamese_network = None
        self._init_banking_models()

        # Enrollment tracking
        self.enrollment_start = None
        self.enrollment_phase = "bootstrap"

        self.model_weights = {
            "transformer": 0.25,  # Primary — 4-head self-attention
            "autoencoder": 0.20,
            "svm": 0.15,
            "knn": 0.15,
            "isolation": 0.10,
            "gru": 0.10,          # Legacy recurrent — lower weight
            "pa": 0.05,
        }

    def _init_transformer(self):
        """Initialize BehavioralTransformerEncoder (lazy — tolerates import failures)."""
        try:
            from app.models.transformer_model import BehavioralTransformerEncoder
            from app.behavioral_feature_engine import BehavioralFeatureEngine

            feature_dim = BehavioralFeatureEngine.FEATURE_COUNT  # Dynamic — matches actual engine

            self.transformer_model = BehavioralTransformerEncoder(
                sequence_length=50,   # Match GRU's default for feature dicts
                feature_dim=feature_dim,
                d_model=64,
                nhead=4,
                num_layers=2,
                dim_feedforward=128,
                dropout=0.1,
                embedding_dim=128,
            )
            logger.info("BehavioralTransformerEncoder initialized (d=64, h=4, L=2, features=%d)", feature_dim)
        except Exception:
            logger.warning("BehavioralTransformerEncoder not available — falling back to GRU-only")
            self.transformer_model = None

    def _init_banking_models(self):
        """Initialize banking-specific models (lazy — tolerates import failures)."""
        try:
            from app.models.duress_detector import DuressDetector

            self.duress_detector = DuressDetector()
        except Exception:
            logger.warning("Duress detector not available")

        try:
            from app.models.siamese_network import SiameseNetwork

            self.siamese_network = SiameseNetwork(input_dim=38, embedding_dim=64)
        except Exception:
            logger.warning("Siamese network not available")

    def get_enrollment_phase(self) -> Dict:
        """Get current enrollment phase based on days since enrollment start."""
        if self.enrollment_start is None:
            return {
                "phase": "bootstrap",
                "days_enrolled": 0,
                "progress_pct": 0,
                "active_models": self.ENROLLMENT_PHASES["bootstrap"]["models"],
                "total_models": len(self.model_weights),
                "active_model_count": len(self.ENROLLMENT_PHASES["bootstrap"]["models"]),
            }

        days = (datetime.now() - self.enrollment_start).days

        if days < 3:
            phase = "bootstrap"
            progress = int((days / 3) * 33)
        elif days < 7:
            phase = "building"
            progress = 33 + int(((days - 3) / 4) * 34)
        else:
            phase = "mature"
            progress = min(67 + int(((days - 7) / 7) * 33), 100)

        self.enrollment_phase = phase
        active_models = self.ENROLLMENT_PHASES[phase]["models"]

        return {
            "phase": phase,
            "days_enrolled": days,
            "progress_pct": progress,
            "active_models": active_models,
            "total_models": len(self.model_weights),
            "active_model_count": len(active_models),
        }

    def train_initial_models(self, genuine_features: List[Dict]) -> Dict:
        """Train all models on initial genuine data"""
        results = {}
        self.enrollment_start = datetime.now()

        try:
            # Train GRU
            if len(genuine_features) >= 50:
                results["gru"] = self.gru_model.train(genuine_features)

            # Train BehavioralTransformerEncoder (primary)
            if self.transformer_model is not None and len(genuine_features) >= 50:
                try:
                    results["transformer"] = self.transformer_model.train_model(genuine_features)
                except Exception as e:
                    logger.error("Transformer training failed: %s", e)
                    results["transformer"] = {"error": str(e)}

            # Train Autoencoder
            if len(genuine_features) >= 20:
                results["autoencoder"] = self.autoencoder.train(genuine_features)

            # Train One-Class SVM
            if len(genuine_features) >= 10:
                results["svm"] = self.svm_detector.train(genuine_features)

            # Initialize k-NN with genuine data
            for features in genuine_features:
                self.knn_classifier.update(features, is_genuine=True)

            # Train Isolation Forest
            if len(genuine_features) >= 20:
                results["isolation"] = self.isolation_forest.train(genuine_features)

            # Initialize Passive-Aggressive with genuine data
            if len(genuine_features) >= 5:
                labels = [1] * len(genuine_features)
                self.pa_classifier.partial_fit(genuine_features, labels)
                results["pa"] = {"initialized": True}

            # Initialize duress baseline
            if self.duress_detector and len(genuine_features) >= 10:
                self.duress_detector.set_user_baseline(self.user_id, genuine_features)
                results["duress"] = {"baseline_set": True}

        except Exception as e:
            results["error"] = str(e)

        results["enrollment_phase"] = self.get_enrollment_phase()
        return results

    def predict_ensemble(self, features: List[Dict]) -> Dict:
        """Get ensemble prediction from all models with progressive enrollment."""
        predictions = {}
        enrollment = self.get_enrollment_phase()
        active_models = enrollment.get("active_models", list(self.model_weights.keys()))

        # BehavioralTransformerEncoder prediction (primary)
        if "transformer" in active_models and self.transformer_model is not None:
            try:
                tf_score, tf_conf = self.transformer_model.predict(features)
                predictions["transformer"] = {"score": tf_score, "confidence": tf_conf}
            except Exception:
                logger.exception("Transformer ensemble prediction failed")
                predictions["transformer"] = {"score": 0.5, "confidence": 0.0}

        # GRU prediction (legacy)
        if "gru" in active_models:
            try:
                gru_score, gru_conf = self.gru_model.predict(features)
                predictions["gru"] = {"score": gru_score, "confidence": gru_conf}
            except Exception:
                logger.exception("GRU ensemble prediction failed")
                predictions["gru"] = {"score": 0.5, "confidence": 0.0}

        # Autoencoder anomaly score
        if "autoencoder" in active_models:
            try:
                ae_anomaly = self.autoencoder.predict_anomaly_score(features)
                predictions["autoencoder"] = {"anomaly_score": ae_anomaly}
            except Exception:
                logger.exception("Autoencoder ensemble prediction failed")
                predictions["autoencoder"] = {"anomaly_score": 0.5}

        # SVM outlier score
        if "svm" in active_models:
            try:
                svm_outlier = self.svm_detector.predict_outlier_score(features)
                predictions["svm"] = {"outlier_score": svm_outlier}
            except Exception:
                logger.exception("SVM ensemble prediction failed")
                predictions["svm"] = {"outlier_score": 0.5}

        # k-NN prediction
        if "knn" in active_models:
            try:
                knn_score, knn_conf = self.knn_classifier.predict(features[-1])
                predictions["knn"] = {"score": knn_score, "confidence": knn_conf}
            except Exception:
                logger.exception("k-NN ensemble prediction failed")
                predictions["knn"] = {"score": 0.5, "confidence": 0.0}

        # Passive-Aggressive prediction
        if "pa" in active_models:
            try:
                pa_score, pa_conf = self.pa_classifier.predict(features)
                predictions["pa"] = {"score": pa_score, "confidence": pa_conf}
            except Exception:
                logger.exception("Passive-aggressive ensemble prediction failed")
                predictions["pa"] = {"score": 0.5, "confidence": 0.0}

        # Isolation Forest anomaly score
        if "isolation" in active_models:
            try:
                if_anomaly = self.isolation_forest.predict_anomaly_score(features)
                predictions["isolation"] = {"anomaly_score": if_anomaly}
            except Exception:
                logger.exception("Isolation forest ensemble prediction failed")
                predictions["isolation"] = {"anomaly_score": 0.5}

        # Calculate weighted ensemble score
        ensemble_score = self._calculate_ensemble_score(predictions)
        ensemble_score["enrollment_phase"] = enrollment["phase"]

        predictions["ensemble"] = ensemble_score
        return predictions

    def predict_per_transaction(
        self,
        features: List[Dict],
        transaction_amount: float = 0,
        keystroke_features: Dict = None,
        mouse_features: Dict = None,
        session_context: Dict = None,
    ) -> Dict:
        """Per-transaction behavioral risk scoring for banking.

        Returns separate risk scores for the transaction including
        behavioral authenticity, duress probability, and step-up recommendation.
        """
        # Get base ensemble prediction
        ensemble_result = self.predict_ensemble(features)
        auth_score = ensemble_result.get("ensemble", {}).get("authenticity_score", 0.5)

        # Duress detection
        duress_result = {"duress_score": 0.0, "alert_level": "normal"}
        if self.duress_detector and keystroke_features and mouse_features:
            duress_result = self.duress_detector.compute_duress_score(
                self.user_id,
                keystroke_features or {},
                mouse_features or {},
                session_context,
            )

        # Step-up decision
        risk_score = 1.0 - auth_score
        duress_score = duress_result.get("duress_score", 0.0)

        step_up_required = False
        step_up_reasons = []

        if risk_score > 0.6:
            step_up_required = True
            step_up_reasons.append("behavioral_risk_elevated")
        if transaction_amount >= 50000 and risk_score > 0.3:
            step_up_required = True
            step_up_reasons.append("high_value_with_moderate_risk")
        if duress_score > 0.75:
            step_up_reasons.append("duress_detected_silent_alert")
            # NOTE: Duress does NOT trigger visible step-up to protect user

        return {
            "authenticity_score": round(auth_score, 4),
            "risk_score": round(risk_score, 4),
            "duress": duress_result,
            "step_up_required": step_up_required,
            "step_up_reasons": step_up_reasons,
            "transaction_amount": transaction_amount,
            "enrollment_phase": self.enrollment_phase,
            "model_predictions": {
                k: v for k, v in ensemble_result.items() if k != "ensemble"
            },
            "ensemble": ensemble_result.get("ensemble", {}),
        }

    def _calculate_ensemble_score(self, predictions: Dict) -> Dict:
        """Calculate weighted ensemble authentication score"""
        scores = []
        weights = []

        # Transformer score (primary)
        if "transformer" in predictions and predictions["transformer"]["confidence"] > 0.1:
            scores.append(predictions["transformer"]["score"])
            weights.append(self.model_weights["transformer"] * predictions["transformer"]["confidence"])

        # GRU score (legacy)
        if "gru" in predictions and predictions["gru"]["confidence"] > 0.1:
            scores.append(predictions["gru"]["score"])
            weights.append(self.model_weights["gru"] * predictions["gru"]["confidence"])

        # Autoencoder (convert anomaly to authenticity)
        if "autoencoder" in predictions:
            auth_score = 1 - predictions["autoencoder"]["anomaly_score"]
            scores.append(auth_score)
            weights.append(self.model_weights["autoencoder"])

        # SVM (convert outlier to authenticity)
        if "svm" in predictions:
            auth_score = 1 - predictions["svm"]["outlier_score"]
            scores.append(auth_score)
            weights.append(self.model_weights["svm"])

        # k-NN score
        if "knn" in predictions and predictions["knn"]["confidence"] > 0.1:
            scores.append(predictions["knn"]["score"])
            weights.append(self.model_weights["knn"] * predictions["knn"]["confidence"])

        # Passive-Aggressive score
        if "pa" in predictions and predictions["pa"]["confidence"] > 0.1:
            scores.append(predictions["pa"]["score"])
            weights.append(self.model_weights["pa"] * predictions["pa"]["confidence"])

        # Isolation Forest (convert anomaly to authenticity)
        if "isolation" in predictions:
            auth_score = 1 - predictions["isolation"]["anomaly_score"]
            scores.append(auth_score)
            weights.append(self.model_weights["isolation"])

        # Calculate weighted average
        if scores and weights:
            raw_score = np.average(scores, weights=weights)
            # Apply Temperature Scaling for probability calibration
            T = 1.5
            eps = 1e-7
            p = np.clip(raw_score, eps, 1 - eps)
            logit = np.log(p / (1 - p))
            weighted_score = 1 / (1 + np.exp(-logit / T))

            confidence = np.mean([abs(s - 0.5) * 2 for s in scores])
            consensus = np.std(scores)  # Lower std = higher consensus
        else:
            weighted_score = 0.5
            confidence = 0.0
            consensus = 1.0

        return {
            "authenticity_score": float(weighted_score),
            "confidence": float(confidence),
            "consensus": float(1 - min(consensus, 1.0)),
            "num_models": len(scores),
        }

    def update_models(self, features: Dict, is_genuine: bool):
        """Update models with new feedback"""
        self.knn_classifier.update(features, is_genuine)
        label = 1 if is_genuine else 0
        self.pa_classifier.partial_fit([features], [label])

    def save_all_models(self):
        """Save all trained models"""
        MODEL_SCHEMA_VERSION = "2.0.0"
        base_path = os.path.join(self.models_path, f"model_v{MODEL_SCHEMA_VERSION}")

        self.gru_model.save(base_path)
        self.autoencoder.save(base_path)
        self.svm_detector.save(base_path)
        self.knn_classifier.save(base_path)
        self.pa_classifier.save(base_path)
        self.isolation_forest.save(base_path)

        if self.transformer_model is not None:
            self.transformer_model.save(base_path)

        if self.duress_detector:
            self.duress_detector.save(base_path)

    def load_all_models(self):
        """Load all saved models"""
        MODEL_SCHEMA_VERSION = "2.0.0"
        base_path = os.path.join(self.models_path, f"model_v{MODEL_SCHEMA_VERSION}")

        results = {
            "gru": self.gru_model.load(base_path),
            "autoencoder": self.autoencoder.load(base_path),
            "svm": self.svm_detector.load(base_path),
            "knn": self.knn_classifier.load(base_path),
            "pa": self.pa_classifier.load(base_path),
            "isolation": self.isolation_forest.load(base_path),
        }

        if self.transformer_model is not None:
            results["transformer"] = self.transformer_model.load(base_path)

        if self.duress_detector:
            results["duress"] = self.duress_detector.load(base_path)

        return results
