import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import logging
logger = logging.getLogger(__name__)

from app.models.base import FeatureConsistencyMixin
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score
import joblib
import os
try:
    import tensorflow as tf
    from tensorflow.keras.models import Model, Sequential
    from tensorflow.keras.layers import GRU, LSTM, Dense, Dropout, Input, RepeatVector, TimeDistributed
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping
except ImportError:
    tf = None

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
            metrics=["accuracy"],
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
                # import tf2onnx
                #
                # spec = (
                #     tf.TensorSpec(
                #         (None, self.sequence_length, self.feature_dim),
                #         tf.float32,
                #         name="input",
                #     ),
                # )
                # tf2onnx.convert.from_keras(
                #     self.model, input_signature=spec, output_path=f"{filepath}_gru.onnx"
                # )
                pass
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
            metrics=["accuracy"],
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


