import numpy as np

try:
    import tensorflow as tf
    from tensorflow.keras.models import Model, Sequential
    from tensorflow.keras.layers import (
        GRU,
        LSTM,
        Dense,
        Dropout,
        Input,
        RepeatVector,
        TimeDistributed,
    )
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping

    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    tf = None

from sklearn.svm import OneClassSVM
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import NearestNeighbors
from sklearn.linear_model import PassiveAggressiveClassifier
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score
import joblib
import os
import hashlib
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from collections import deque
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning, module="sklearn")
warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="tensorflow")
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


class GRUSequenceModel(FeatureConsistencyMixin):
    """GRU model for sequential behavioral data analysis"""

    def __init__(
        self, sequence_length: int = 50, feature_dim: int = 20, hidden_units: int = 64
    ):
        self.sequence_length = sequence_length
        self.feature_dim = feature_dim
        self.hidden_units = hidden_units
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names = None  # Store feature names for consistency
        self.onnx_session = None

    def build_model(self):
        """Build the GRU model architecture"""
        model = Sequential(
            [
                Input(shape=(self.sequence_length, self.feature_dim)),
                GRU(self.hidden_units, return_sequences=True, dropout=0.2),
                GRU(self.hidden_units // 2, return_sequences=False, dropout=0.2),
                Dense(32, activation="relu"),
                Dropout(0.3),
                Dense(16, activation="relu"),
                Dense(1, activation="sigmoid"),  # Binary classification
            ]
        )

        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss="binary_crossentropy",
            metrics=["accuracy", "precision", "recall"],
        )

        self.model = model
        return model

    def prepare_sequences(self, features: List[Dict]) -> np.ndarray:
        """Convert feature dictionaries to sequences"""
        if not features:
            return np.array([])

        # Ensure feature consistency
        features = self._ensure_feature_consistency(features)

        # Convert to matrix
        data_matrix = np.array(
            [[f[name] for name in self.feature_names] for f in features]
        )

        # Normalize features
        if not self.is_trained:
            data_matrix = self.scaler.fit_transform(data_matrix)
        else:
            data_matrix = self.scaler.transform(data_matrix)

        # Create sequences
        sequences = []
        for i in range(len(data_matrix) - self.sequence_length + 1):
            sequences.append(data_matrix[i : i + self.sequence_length])

        return np.array(sequences)

    def train(
        self, genuine_features: List[Dict], imposter_features: List[Dict] = None
    ) -> Dict:
        """Train the GRU model"""
        # Prepare genuine data
        genuine_sequences = self.prepare_sequences(genuine_features)

        if len(genuine_sequences) == 0:
            raise ValueError("Insufficient data for training")

        # Create labels (1 for genuine, 0 for imposter)
        genuine_labels = np.ones(len(genuine_sequences))

        X = genuine_sequences
        y = genuine_labels

        # Add imposter data if available
        if imposter_features:
            imposter_sequences = self.prepare_sequences(imposter_features)
            if len(imposter_sequences) > 0:
                imposter_labels = np.zeros(len(imposter_sequences))
                X = np.concatenate([genuine_sequences, imposter_sequences])
                y = np.concatenate([genuine_labels, imposter_labels])

        # Build model if not exists
        if self.model is None:
            self.build_model()

        # Train model
        early_stopping = EarlyStopping(
            monitor="loss", patience=10, restore_best_weights=True
        )

        history = self.model.fit(
            X,
            y,
            epochs=100,
            batch_size=32,
            validation_split=0.2,
            callbacks=[early_stopping],
            verbose=0,
        )

        self.is_trained = True

        # Calculate training metrics
        predictions = self.model.predict(X)
        binary_preds = (predictions > 0.5).astype(int).flatten()

        metrics = {
            "accuracy": float(accuracy_score(y, binary_preds)),
            "precision": float(precision_score(y, binary_preds, zero_division=0)),
            "recall": float(recall_score(y, binary_preds, zero_division=0)),
            "loss": float(history.history["loss"][-1]),
        }

        return metrics

    def predict(self, features: List[Dict]) -> Tuple[float, float]:
        """Predict authenticity score and confidence"""
        if not self.is_trained or self.model is None:
            return 0.5, 0.0

        sequences = self.prepare_sequences(features)
        if len(sequences) == 0:
            return 0.5, 0.0

        if self.onnx_session:
            inputs = {
                self.onnx_session.get_inputs()[0]
                .name: sequences[-1:]
                .astype(np.float32)
            }
            prediction = self.onnx_session.run(None, inputs)[0][0][0]
        else:
            prediction = self.model.predict(sequences[-1:], verbose=0)[0][0]

        confidence = abs(prediction - 0.5) * 2  # Convert to confidence scale

        return float(prediction), float(confidence)

    def save(self, filepath: str):
        """Save the model and scaler"""
        if self.model is not None:
            self.model.save(f"{filepath}_gru.h5")
            joblib.dump(
                {"scaler": self.scaler, "feature_names": self.feature_names},
                f"{filepath}_gru_scaler.pkl",
            )
            try:
                import tf2onnx

                spec = (
                    tf.TensorSpec(
                        (None, self.sequence_length, self.feature_dim),
                        tf.float32,
                        name="input",
                    ),
                )
                tf2onnx.convert.from_keras(
                    self.model, input_signature=spec, output_path=f"{filepath}_gru.onnx"
                )
            except Exception as e:
                logger.error("Failed to export GRU model to ONNX: %s", e)

    def load(self, filepath: str):
        """Load the model and scaler"""
        try:
            self.model = tf.keras.models.load_model(f"{filepath}_gru.h5")
            data = joblib.load(f"{filepath}_gru_scaler.pkl")
            self.scaler = data["scaler"]
            self.feature_names = data["feature_names"]
            self.is_trained = True
            try:
                import onnxruntime as ort

                if os.path.exists(f"{filepath}_gru.onnx"):
                    self.onnx_session = ort.InferenceSession(f"{filepath}_gru.onnx")
            except Exception as e:
                logger.warning(
                    "Could not load ONNX session for GRU; falling back to TensorFlow: %s",
                    e,
                )
            return True
        except Exception:
            logger.exception("Failed to load GRU model artifacts from %s", filepath)
            return False


class AutoencoderAnomalyDetector(FeatureConsistencyMixin):
    """Autoencoder for detecting behavioral anomalies"""

    def __init__(self, feature_dim: int = 20, encoding_dim: int = 8):
        self.feature_dim = feature_dim
        self.encoding_dim = encoding_dim
        self.model = None
        self.scaler = MinMaxScaler()
        self.threshold = None
        self.is_trained = False
        self.feature_names = None

    def build_model(self):
        """Build the autoencoder architecture"""
        # Encoder
        input_layer = Input(shape=(self.feature_dim,))
        encoded = Dense(self.encoding_dim * 2, activation="relu")(input_layer)
        encoded = Dropout(0.2)(encoded)
        encoded = Dense(self.encoding_dim, activation="relu")(encoded)

        # Decoder
        decoded = Dense(self.encoding_dim * 2, activation="relu")(encoded)
        decoded = Dropout(0.2)(decoded)
        decoded = Dense(self.feature_dim, activation="sigmoid")(decoded)

        # Autoencoder model
        autoencoder = Model(input_layer, decoded)
        autoencoder.compile(
            optimizer=Adam(learning_rate=0.001), loss="mse", metrics=["mae"]
        )

        self.model = autoencoder
        return autoencoder

    def prepare_data(self, features: List[Dict]) -> np.ndarray:
        """Convert feature dictionaries to matrix"""
        if not features:
            return np.array([])

        # Ensure feature consistency
        features = self._ensure_feature_consistency(features)

        data_matrix = np.array(
            [[f[name] for name in self.feature_names] for f in features]
        )

        if not self.is_trained:
            data_matrix = self.scaler.fit_transform(data_matrix)
        else:
            data_matrix = self.scaler.transform(data_matrix)

        return data_matrix

    def train(self, genuine_features: List[Dict]) -> Dict:
        """Train the autoencoder on genuine user data"""
        X = self.prepare_data(genuine_features)

        if len(X) == 0:
            raise ValueError("Insufficient data for training")

        # Update feature_dim based on actual features
        self.feature_dim = len(self.feature_names)

        if self.model is None:
            self.build_model()

        # Train autoencoder
        early_stopping = EarlyStopping(
            monitor="loss", patience=15, restore_best_weights=True
        )

        history = self.model.fit(
            X,
            X,  # Autoencoder learns to reconstruct input
            epochs=100,
            batch_size=32,
            validation_split=0.2,
            callbacks=[early_stopping],
            verbose=0,
        )

        # Calculate reconstruction errors on training data
        reconstructions = self.model.predict(X, verbose=0)
        reconstruction_errors = np.mean(np.square(X - reconstructions), axis=1)

        # Set threshold at 95th percentile of training errors
        self.threshold = np.percentile(reconstruction_errors, 95)
        self.is_trained = True

        metrics = {
            "loss": float(history.history["loss"][-1]),
            "threshold": float(self.threshold),
            "mean_reconstruction_error": float(np.mean(reconstruction_errors)),
        }

        return metrics

    def predict_anomaly_score(self, features: List[Dict]) -> float:
        """Predict anomaly score for new data"""
        if not self.is_trained or self.model is None:
            return 0.5

        X = self.prepare_data(features)
        if len(X) == 0:
            return 0.5

        # Calculate reconstruction error for most recent data
        reconstruction = self.model.predict(X[-1:], verbose=0)
        error = np.mean(np.square(X[-1:] - reconstruction))

        # Normalize error to [0, 1] scale
        if self.threshold > 0:
            anomaly_score = min(error / self.threshold, 1.0)
        else:
            anomaly_score = 0.0

        return float(anomaly_score)

    def save(self, filepath: str):
        """Save the model and scaler"""
        if self.model is not None:
            self.model.save(f"{filepath}_autoencoder.h5")
            joblib.dump(
                {
                    "scaler": self.scaler,
                    "threshold": self.threshold,
                    "feature_names": self.feature_names,
                },
                f"{filepath}_autoencoder_params.pkl",
            )

    def load(self, filepath: str):
        """Load the model and scaler"""
        try:
            self.model = tf.keras.models.load_model(f"{filepath}_autoencoder.h5")
            params = joblib.load(f"{filepath}_autoencoder_params.pkl")
            self.scaler = params["scaler"]
            self.threshold = params["threshold"]
            self.feature_names = params["feature_names"]
            if self.feature_names:
                self.feature_dim = len(self.feature_names)
            self.is_trained = True
            return True
        except Exception:
            logger.exception("Failed to load autoencoder artifacts from %s", filepath)
            return False


class OneClassSVMDetector(FeatureConsistencyMixin):
    """One-Class SVM for outlier detection"""

    def __init__(self, nu: float = 0.1, gamma: str = "scale"):
        self.model = OneClassSVM(nu=nu, gamma=gamma)
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

        if not self.is_trained:
            data_matrix = self.scaler.fit_transform(data_matrix)
        else:
            data_matrix = self.scaler.transform(data_matrix)

        return data_matrix

    def train(self, genuine_features: List[Dict]) -> Dict:
        """Train One-Class SVM on genuine data"""
        X = self.prepare_data(genuine_features)

        if len(X) == 0:
            raise ValueError("Insufficient data for training")

        self.model.fit(X)
        self.is_trained = True

        # Calculate training metrics
        predictions = self.model.predict(X)
        inlier_ratio = np.sum(predictions == 1) / len(predictions)

        return {
            "inlier_ratio": float(inlier_ratio),
            "support_vectors": int(len(self.model.support_vectors_)),
        }

    def predict_outlier_score(self, features: List[Dict]) -> float:
        """Predict outlier score (higher = more likely outlier)"""
        if not self.is_trained:
            return 0.5

        X = self.prepare_data(features)
        if len(X) == 0:
            return 0.5

        # Get decision score for most recent data
        decision_score = self.model.decision_function(X[-1:])

        # Convert to [0, 1] scale (0 = outlier, 1 = inlier)
        # SVM decision scores are typically in range [-2, 2]
        normalized_score = (decision_score[0] + 2) / 4
        outlier_score = 1 - max(0, min(1, normalized_score))

        return float(outlier_score)

    def save(self, filepath: str):
        """Save the model and scaler"""
        joblib.dump(
            {
                "model": self.model,
                "scaler": self.scaler,
                "is_trained": self.is_trained,
                "feature_names": self.feature_names,
            },
            f"{filepath}_svm.pkl",
        )

    def load(self, filepath: str):
        """Load the model and scaler"""
        try:
            data = joblib.load(f"{filepath}_svm.pkl")
            self.model = data["model"]
            self.scaler = data["scaler"]
            self.is_trained = data["is_trained"]
            self.feature_names = data.get("feature_names", None)
            return True
        except Exception:
            logger.exception("Failed to load SVM artifacts from %s", filepath)
            return False


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
        features = self._ensure_feature_consistency(features)

        if is_genuine:
            self.genuine_buffer.append(features)
        else:
            self.imposter_buffer.append(features)

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
        features = self._ensure_feature_consistency(features)

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


class IsolationForestDetector(FeatureConsistencyMixin):
    """Isolation Forest for anomaly detection"""

    def __init__(self, contamination: float = 0.1, n_estimators: int = 100):
        self.model = IsolationForest(
            contamination=contamination, n_estimators=n_estimators, random_state=42
        )
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

        if not self.is_trained:
            data_matrix = self.scaler.fit_transform(data_matrix)
        else:
            data_matrix = self.scaler.transform(data_matrix)

        return data_matrix

    def train(self, genuine_features: List[Dict]) -> Dict:
        """Train Isolation Forest on genuine data"""
        X = self.prepare_data(genuine_features)

        if len(X) == 0:
            raise ValueError("Insufficient data for training")

        self.model.fit(X)
        self.is_trained = True

        # Calculate training metrics
        predictions = self.model.predict(X)
        inlier_ratio = np.sum(predictions == 1) / len(predictions)

        return {
            "inlier_ratio": float(inlier_ratio),
            "n_estimators": self.model.n_estimators,
        }

    def predict_anomaly_score(self, features: List[Dict]) -> float:
        """Predict anomaly score"""
        if not self.is_trained:
            return 0.5

        X = self.prepare_data(features)
        if len(X) == 0:
            return 0.5

        # Get anomaly score for most recent data
        anomaly_score = self.model.decision_function(X[-1:])

        # Convert to [0, 1] scale (0 = normal, 1 = anomaly)
        # Isolation Forest scores are typically in range [-1, 1]
        normalized_score = (anomaly_score[0] + 1) / 2
        anomaly_score = 1 - max(0, min(1, normalized_score))

        return float(anomaly_score)

    def save(self, filepath: str):
        """Save the model and scaler"""
        joblib.dump(
            {
                "model": self.model,
                "scaler": self.scaler,
                "is_trained": self.is_trained,
                "feature_names": self.feature_names,
            },
            f"{filepath}_isolation.pkl",
        )

    def load(self, filepath: str):
        """Load the model and scaler"""
        try:
            data = joblib.load(f"{filepath}_isolation.pkl")
            self.model = data["model"]
            self.scaler = data["scaler"]
            self.is_trained = data["is_trained"]
            self.feature_names = data.get("feature_names", None)
            return True
        except Exception:
            logger.exception(
                "Failed to load isolation forest artifacts from %s", filepath
            )
            return False


class LSTMSequenceModel(FeatureConsistencyMixin):
    """LSTM model for sequential behavioral data analysis"""

    def __init__(
        self, sequence_length: int = 50, feature_dim: int = 20, hidden_units: int = 64
    ):
        self.sequence_length = sequence_length
        self.feature_dim = feature_dim
        self.hidden_units = hidden_units
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names = None

    def build_model(self):
        """Build the LSTM model architecture"""
        model = Sequential(
            [
                Input(shape=(self.sequence_length, self.feature_dim)),
                LSTM(self.hidden_units, return_sequences=True, dropout=0.2),
                LSTM(self.hidden_units // 2, return_sequences=False, dropout=0.2),
                Dense(32, activation="relu"),
                Dropout(0.3),
                Dense(16, activation="relu"),
                Dense(1, activation="sigmoid"),
            ]
        )

        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss="binary_crossentropy",
            metrics=["accuracy", "precision", "recall"],
        )

        self.model = model
        return model

    def prepare_sequences(self, features: List[Dict]) -> np.ndarray:
        if not features:
            return np.array([])
        features = self._ensure_feature_consistency(features)
        data_matrix = np.array(
            [[f[name] for name in self.feature_names] for f in features]
        )

        if not self.is_trained:
            data_matrix = self.scaler.fit_transform(data_matrix)
        else:
            data_matrix = self.scaler.transform(data_matrix)

        sequences = []
        for i in range(len(data_matrix) - self.sequence_length + 1):
            sequences.append(data_matrix[i : i + self.sequence_length])

        return np.array(sequences)

    def train(
        self, genuine_features: List[Dict], imposter_features: List[Dict] = None
    ) -> Dict:
        genuine_sequences = self.prepare_sequences(genuine_features)

        if len(genuine_sequences) == 0:
            raise ValueError("Insufficient data for training")

        genuine_labels = np.ones(len(genuine_sequences))
        X = genuine_sequences
        y = genuine_labels

        if imposter_features:
            imposter_sequences = self.prepare_sequences(imposter_features)
            if len(imposter_sequences) > 0:
                imposter_labels = np.zeros(len(imposter_sequences))
                X = np.concatenate([genuine_sequences, imposter_sequences])
                y = np.concatenate([genuine_labels, imposter_labels])

        if self.model is None:
            self.build_model()

        early_stopping = EarlyStopping(
            monitor="loss", patience=10, restore_best_weights=True
        )

        history = self.model.fit(
            X,
            y,
            epochs=100,
            batch_size=32,
            validation_split=0.2,
            callbacks=[early_stopping],
            verbose=0,
        )

        self.is_trained = True
        predictions = self.model.predict(X)
        binary_preds = (predictions > 0.5).astype(int).flatten()

        return {
            "accuracy": float(accuracy_score(y, binary_preds)),
            "precision": float(precision_score(y, binary_preds, zero_division=0)),
            "recall": float(recall_score(y, binary_preds, zero_division=0)),
            "loss": float(history.history["loss"][-1]),
        }

    def predict(self, features: List[Dict]) -> Tuple[float, float]:
        if not self.is_trained or self.model is None:
            return 0.5, 0.0

        sequences = self.prepare_sequences(features)
        if len(sequences) == 0:
            return 0.5, 0.0

        prediction = self.model.predict(sequences[-1:], verbose=0)[0][0]
        confidence = abs(prediction - 0.5) * 2

        return float(prediction), float(confidence)

    def save(self, filepath: str):
        if self.model is not None:
            self.model.save(f"{filepath}_lstm.h5")
            joblib.dump(
                {"scaler": self.scaler, "feature_names": self.feature_names},
                f"{filepath}_lstm_scaler.pkl",
            )

    def load(self, filepath: str):
        try:
            self.model = tf.keras.models.load_model(f"{filepath}_lstm.h5")
            data = joblib.load(f"{filepath}_lstm_scaler.pkl")
            self.scaler = data["scaler"]
            self.feature_names = data["feature_names"]
            self.is_trained = True
            return True
        except Exception:
            logger.exception("Failed to load LSTM artifacts from %s", filepath)
            return False


class VariationalAutoencoder(FeatureConsistencyMixin):
    """Variational Autoencoder for enhanced anomaly detection"""

    def __init__(self, feature_dim: int = 20, latent_dim: int = 8):
        self.feature_dim = feature_dim
        self.latent_dim = latent_dim
        self.encoder = None
        self.decoder = None
        self.autoencoder = None
        self.scaler = StandardScaler()
        self.threshold = None
        self.is_trained = False
        self.feature_names = None

    def build_model(self):
        # Encoder
        inputs = Input(shape=(self.feature_dim,))
        h = Dense(32, activation="relu")(inputs)
        h = Dense(16, activation="relu")(h)

        z_mean = Dense(self.latent_dim)(h)
        z_log_var = Dense(self.latent_dim)(h)

        def sampling(args):
            z_mean, z_log_var = args
            epsilon = tf.random.normal(shape=(tf.shape(z_mean)[0], self.latent_dim))
            return z_mean + tf.exp(0.5 * z_log_var) * epsilon

        z = tf.keras.layers.Lambda(sampling, output_shape=(self.latent_dim,))(
            [z_mean, z_log_var]
        )

        # Decoder
        decoder_h = Dense(16, activation="relu")(z)
        decoder_h = Dense(32, activation="relu")(decoder_h)
        outputs = Dense(self.feature_dim, activation="sigmoid")(decoder_h)

        self.autoencoder = Model(inputs, outputs)

        # VAE model
        self.encoder = Model(inputs, z_mean)

        decoder_input = Input(shape=(self.latent_dim,))
        decoder_h = self.autoencoder.layers[-3](decoder_input)
        decoder_h = self.autoencoder.layers[-2](decoder_h)
        decoder_outputs = self.autoencoder.layers[-1](decoder_h)
        self.decoder = Model(decoder_input, decoder_outputs)

        self.autoencoder.compile(optimizer=Adam(learning_rate=0.001), loss="mse")

        return self.autoencoder

    def prepare_data(self, features: List[Dict]) -> np.ndarray:
        if not features:
            return np.array([])
        features = self._ensure_feature_consistency(features)
        data_matrix = np.array(
            [[f[name] for name in self.feature_names] for f in features]
        )

        if not self.is_trained:
            data_matrix = self.scaler.fit_transform(data_matrix)
        else:
            data_matrix = self.scaler.transform(data_matrix)

        return data_matrix

    def train(self, genuine_features: List[Dict]) -> Dict:
        X = self.prepare_data(genuine_features)

        if len(X) == 0:
            raise ValueError("Insufficient data for training")

        self.feature_dim = len(self.feature_names)

        if self.autoencoder is None:
            self.build_model()

        early_stopping = EarlyStopping(
            monitor="loss", patience=15, restore_best_weights=True
        )

        history = self.autoencoder.fit(
            X,
            X,
            epochs=100,
            batch_size=32,
            validation_split=0.2,
            callbacks=[early_stopping],
            verbose=0,
        )

        reconstructions = self.autoencoder.predict(X, verbose=0)
        reconstruction_errors = np.mean(np.square(X - reconstructions), axis=1)

        self.threshold = np.percentile(reconstruction_errors, 95)
        self.is_trained = True

        return {
            "loss": float(history.history["loss"][-1]),
            "threshold": float(self.threshold),
            "mean_reconstruction_error": float(np.mean(reconstruction_errors)),
        }

    def predict_anomaly_score(self, features: List[Dict]) -> float:
        if not self.is_trained or self.autoencoder is None:
            return 0.5

        X = self.prepare_data(features)
        if len(X) == 0:
            return 0.5

        reconstruction = self.autoencoder.predict(X[-1:], verbose=0)
        error = np.mean(np.square(X[-1:] - reconstruction))

        if self.threshold > 0:
            anomaly_score = min(error / self.threshold, 1.0)
        else:
            anomaly_score = 0.0

        return float(anomaly_score)

    def save(self, filepath: str):
        if self.autoencoder is not None:
            self.autoencoder.save(f"{filepath}_vae.h5")
            joblib.dump(
                {
                    "scaler": self.scaler,
                    "threshold": self.threshold,
                    "feature_names": self.feature_names,
                    "latent_dim": self.latent_dim,
                },
                f"{filepath}_vae_params.pkl",
            )

    def load(self, filepath: str):
        try:
            self.autoencoder = tf.keras.models.load_model(f"{filepath}_vae.h5")
            self.encoder = Model(
                self.autoencoder.input, self.autoencoder.layers[-3].output
            )
            params = joblib.load(f"{filepath}_vae_params.pkl")
            self.scaler = params["scaler"]
            self.threshold = params["threshold"]
            self.feature_names = params["feature_names"]
            self.latent_dim = params.get("latent_dim", 8)
            if self.feature_names:
                self.feature_dim = len(self.feature_names)
            self.is_trained = True
            return True
        except Exception:
            logger.exception("Failed to load VAE artifacts from %s", filepath)
            return False


class BehavioralAnalytics:
    """Advanced behavioral analytics for user comparison and insights"""

    def __init__(self):
        self.population_stats = {}
        self.user_baseline = {}

    def compute_population_stats(self, all_users_data: List[Dict]):
        """Compute population-level statistics for comparison"""
        if not all_users_data:
            return

        all_features = []
        for user_data in all_users_data:
            all_features.extend(user_data.get("features", []))

        if not all_features:
            return

        feature_names = set()
        for f in all_features:
            feature_names.update(f.keys())

        for feature in feature_names:
            values = [f.get(feature, 0) for f in all_features if f.get(feature, 0) > 0]
            if values:
                self.population_stats[feature] = {
                    "mean": np.mean(values),
                    "std": np.std(values),
                    "median": np.median(values),
                    "q25": np.percentile(values, 25),
                    "q75": np.percentile(values, 75),
                }

    def compare_to_population(self, user_features: List[Dict]) -> Dict:
        """Compare user behavior to population norms"""
        if not self.population_stats:
            return {"similarity": 0.5, "deviations": []}

        deviations = []
        for feature, stats in self.population_stats.items():
            user_values = [
                f.get(feature, 0) for f in user_features if f.get(feature, 0) > 0
            ]
            if user_values:
                user_mean = np.mean(user_values)
                z_score = (
                    (user_mean - stats["mean"]) / stats["std"]
                    if stats["std"] > 0
                    else 0
                )
                if abs(z_score) > 2:
                    deviations.append(
                        {
                            "feature": feature,
                            "z_score": float(z_score),
                            "direction": "above" if z_score > 0 else "below",
                        }
                    )

        similarity = max(0, 1 - len(deviations) * 0.1)

        return {
            "similarity": float(similarity),
            "deviations": deviations[:5],
            "unique_patterns": len(deviations),
        }

    def detect_stress_indicators(self, features: Dict) -> Dict:
        """Detect potential stress from behavioral changes"""
        indicators = []
        confidence = 0.0

        # Speed variance increase
        if features.get("speed_variance", 0) > 8:
            indicators.append("high_speed_variance")
            confidence += 0.2

        # Rhythm consistency decrease
        if features.get("rhythm_consistency", 1) < 0.5:
            indicators.append("low_rhythm_consistency")
            confidence += 0.25

        # Increased pause ratio
        if features.get("pause_ratio", 0) > 0.4:
            indicators.append("increased_pauses")
            confidence += 0.2

        # Flight time variability
        if features.get("flight_time_cv", 0) > 0.5:
            indicators.append("high_flight_variability")
            confidence += 0.2

        # Mouse movement irregularity
        if features.get("movement_efficiency", 1) < 0.6:
            indicators.append("irregular_mouse_movement")
            confidence += 0.15

        return {
            "stress_detected": confidence > 0.4,
            "confidence": min(confidence, 1.0),
            "indicators": indicators,
            "recommendation": "Consider additional verification"
            if confidence > 0.5
            else "Monitor closely",
        }

    def detect_fatigue_indicators(self, features: Dict) -> Dict:
        """Detect potential fatigue from behavioral patterns"""
        indicators = []
        confidence = 0.0

        # Reduced typing speed
        if features.get("typing_speed_wpm", 60) < 25:
            indicators.append("slow_typing_speed")
            confidence += 0.25

        # Increased hold time
        if features.get("hold_time_mean", 100) > 150:
            indicators.append("long_key_hold_time")
            confidence += 0.2

        # Reduced mouse velocity
        if features.get("velocity_mean", 3) < 1:
            indicators.append("slow_mouse_movement")
            confidence += 0.2

        # Increased click duration
        if features.get("click_duration_mean", 100) > 180:
            indicators.append("long_click_duration")
            confidence += 0.2

        # Reduced movement efficiency
        if features.get("movement_efficiency", 0.8) < 0.5:
            indicators.append("inefficient_movement")
            confidence += 0.15

        return {
            "fatigue_detected": confidence > 0.4,
            "confidence": min(confidence, 1.0),
            "indicators": indicators,
            "recommendation": "Suggest break"
            if confidence > 0.6
            else "Continue monitoring",
        }


class DeviceFingerprint:
    """Device fingerprinting for enhanced security"""

    def __init__(self):
        self.fingerprints = {}

    def generate_fingerprint(self, request_headers: Dict, ip_address: str) -> str:
        """Generate device fingerprint from request"""
        components = [
            ip_address,
            request_headers.get("User-Agent", ""),
            request_headers.get("Accept-Language", ""),
            request_headers.get("Accept-Encoding", ""),
        ]

        fingerprint = hashlib.sha256("|".join(components).encode()).hexdigest()
        return fingerprint

    def store_fingerprint(self, user_id: int, fingerprint: str):
        """Store device fingerprint for user"""
        if user_id not in self.fingerprints:
            self.fingerprints[user_id] = []

        if fingerprint not in self.fingerprints[user_id]:
            self.fingerprints[user_id].append(fingerprint)

    def is_known_device(self, user_id: int, fingerprint: str) -> bool:
        """Check if device fingerprint is known"""
        return fingerprint in self.fingerprints.get(user_id, [])

    def get_device_count(self, user_id: int) -> int:
        """Get number of known devices for user"""
        return len(self.fingerprints.get(user_id, []))


class SessionSecurityMonitor:
    """Monitor session for hijacking attempts"""

    def __init__(self):
        self.session_profiles = {}

    def create_session_profile(
        self, session_id: str, ip_address: str, user_agent: str, initial_behavior: Dict
    ):
        """Create behavioral profile for session"""
        self.session_profiles[session_id] = {
            "ip_address": ip_address,
            "user_agent": user_agent,
            "initial_behavior": initial_behavior,
            "ip_changes": 0,
            "behavioral_anomalies": 0,
            "created_at": datetime.now(),
        }

    def detect_ip_change(self, session_id: str, new_ip: str) -> bool:
        """Detect IP address change in session"""
        if session_id not in self.session_profiles:
            return False

        profile = self.session_profiles[session_id]
        if profile["ip_address"] != new_ip:
            profile["ip_changes"] += 1
            return True
        return False

    def detect_behavioral_deviation(
        self, session_id: str, current_behavior: Dict
    ) -> float:
        """Detect deviation from initial behavioral profile"""
        if session_id not in self.session_profiles:
            return 0.0

        profile = self.session_profiles[session_id]
        initial = profile["initial_behavior"]

        deviations = []
        for key in initial:
            if key in current_behavior:
                diff = abs(current_behavior[key] - initial[key])
                max_val = max(abs(current_behavior[key]), abs(initial[key]), 1)
                deviations.append(diff / max_val)

        if deviations:
            avg_deviation = np.mean(deviations)
            if avg_deviation > 0.3:
                profile["behavioral_anomalies"] += 1
            return avg_deviation
        return 0.0

    def get_session_risk_score(self, session_id: str) -> Dict:
        """Calculate session risk score"""
        if session_id not in self.session_profiles:
            return {"risk_level": "unknown", "score": 0.0}

        profile = self.session_profiles[session_id]

        ip_risk = min(profile["ip_changes"] * 0.3, 1.0)
        behavior_risk = min(profile["behavioral_anomalies"] * 0.2, 1.0)

        total_risk = (ip_risk + behavior_risk) / 2

        risk_level = "low"
        if total_risk > 0.6:
            risk_level = "high"
        elif total_risk > 0.3:
            risk_level = "medium"

        return {
            "risk_level": risk_level,
            "score": float(total_risk),
            "ip_changes": profile["ip_changes"],
            "behavioral_anomalies": profile["behavioral_anomalies"],
        }


class RiskBasedAuthenticator:
    """Risk-based authentication with adaptive scoring"""

    def __init__(self):
        self.risk_weights = {
            "device_known": 0.15,
            "time_pattern": 0.10,
            "location": 0.15,
            "behavioral_match": 0.40,
            "session_age": 0.10,
            "anomaly_score": 0.10,
        }

    def calculate_risk_score(self, context: Dict) -> Dict:
        """Calculate overall risk score"""
        risk_factors = []

        # Device factor
        if context.get("device_known", False):
            risk_factors.append(0.0)
        else:
            risk_factors.append(0.8)

        # Time pattern factor (unusual hours)
        current_hour = datetime.now().hour
        if 9 <= current_hour <= 18:
            time_risk = 0.2
        else:
            time_risk = 0.6
        risk_factors.append(time_risk)

        # Location factor
        location_risk = context.get("location_risk", 0.5)
        risk_factors.append(location_risk)

        # Behavioral match
        behavior_score = context.get("behavioral_score", 0.5)
        behavior_risk = 1 - behavior_score
        risk_factors.append(behavior_risk)

        # Session age (newer = higher risk)
        session_age = context.get("session_age_minutes", 0)
        if session_age < 5:
            age_risk = 0.7
        elif session_age < 30:
            age_risk = 0.4
        else:
            age_risk = 0.2
        risk_factors.append(age_risk)

        # Anomaly score
        anomaly_risk = context.get("anomaly_score", 0.5)
        risk_factors.append(anomaly_risk)

        # Weighted average
        total_risk = sum(
            rf * rw for rf, rw in zip(risk_factors, self.risk_weights.values())
        )

        # Determine action
        if total_risk > 0.7:
            action = "block"
        elif total_risk > 0.5:
            action = "challenge"
        elif total_risk > 0.3:
            action = "monitor"
        else:
            action = "allow"

        return {
            "risk_score": float(total_risk),
            "risk_level": "high"
            if total_risk > 0.6
            else "medium"
            if total_risk > 0.3
            else "low",
            "action": action,
            "factors": {
                "device": risk_factors[0],
                "time": risk_factors[1],
                "location": risk_factors[2],
                "behavior": risk_factors[3],
                "session_age": risk_factors[4],
                "anomaly": risk_factors[5],
            },
        }


class AuditLogger:
    """Comprehensive audit logging for security compliance"""

    def __init__(self, log_file: str = "audit.log"):
        self.log_file = log_file
        self.setup_logger()

    def setup_logger(self):
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)

        handler = RotatingFileHandler(
            self.log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )
        self.logger.addHandler(handler)

    def log_authentication(
        self, event_type: str, user_id: int, session_id: str, details: Dict
    ):
        """Log authentication event"""
        self.logger.info(
            f"AUTH | {event_type} | User:{user_id} | Session:{session_id} | "
            f"IP:{details.get('ip_address', 'N/A')} | "
            f"Success:{details.get('success', 'N/A')}"
        )

    def log_behavioral_analysis(
        self, user_id: int, session_id: str, auth_score: float, anomaly_detected: bool
    ):
        """Log behavioral analysis result"""
        self.logger.info(
            f"BEHAVIOR | User:{user_id} | Session:{session_id} | "
            f"Score:{auth_score:.3f} | Anomaly:{anomaly_detected}"
        )

    def log_risk_event(
        self, user_id: int, session_id: str, risk_score: float, action: str
    ):
        """Log risk event"""
        self.logger.warning(
            f"RISK | User:{user_id} | Session:{session_id} | "
            f"Score:{risk_score:.3f} | Action:{action}"
        )

    def log_session_event(
        self, event_type: str, user_id: int, session_id: str, details: Dict
    ):
        """Log session event"""
        self.logger.info(
            f"SESSION | {event_type} | User:{user_id} | Session:{session_id} | "
            f"{details}"
        )


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
