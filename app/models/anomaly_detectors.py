import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import logging
import joblib
logger = logging.getLogger(__name__)

from app.models.base import FeatureConsistencyMixin
from sklearn.svm import OneClassSVM
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler, MinMaxScaler
try:
    import tensorflow as tf
    from tensorflow.keras.models import Model, Sequential
    from tensorflow.keras.layers import GRU, LSTM, Dense, Dropout, Input, RepeatVector, TimeDistributed
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping
except ImportError:
    tf = None

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


