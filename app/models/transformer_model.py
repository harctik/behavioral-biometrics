"""
BehavioralTransformerEncoder — Self-Attention for Keystroke Dynamics.

Replaces GRU as the primary sequence model in the behavioral ensemble.
Self-attention captures long-range dependencies that recurrent gates miss:
  - Typing rhythm at position 1 correlates with position 38 (same person)
  - Attention discovers which keystroke pairs are most discriminative per user
  - Fully parallelizable during training — no sequential bottleneck

Architecture:
    Input: (batch, seq_len=200, features=4)
        Each event = [hold_time, flight_time, key_position, timestamp_delta]
    → Linear projection to d_model=64
    → Sinusoidal Positional Encoding (keystroke order matters)
    → Transformer Encoder (4 heads, 2 layers, ff_dim=128, dropout=0.1)
    → Mean pooling over sequence → single vector
    → Classification head → risk score [0, 1]

4 attention heads learn different patterns:
    Head 1: consecutive digraph patterns (immediate pairs)
    Head 2: rhythm periodicity (similar positions)
    Head 3: outlier keystrokes (deviations from norm)
    Head 4: session-level consistency (first vs last)

Dual-purpose architecture:
    1. Real-time risk scoring (classification head)
    2. SimCLR enrollment embedding (embedding head → 128-dim)
    Same encoder backbone, shared weights, two output heads.

Banking Feature: Processes 200-token session windows for
continuous behavioral analysis during transaction flows.
Supports ONNX export for edge deployment and INT8 quantization.
"""

from __future__ import annotations

import math
import logging
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


# ── Sinusoidal Positional Encoding ────────────────────────────────────────────
# Uses sine/cosine functions (Vaswani et al. 2017) instead of learnable
# positions because behavioral sequences have variable lengths and this
# generalizes better than trained embeddings for OOD sequence lengths.

class SinusoidalPositionalEncoding(nn.Module):
    """Sinusoidal positional encoding for keystroke sequence ordering.

    Keystroke position matters: the rhythm of the first character in a
    password vs the last character is diagnostically different. The model
    needs to know WHERE in the sequence each event occurred.
    """

    def __init__(self, d_model: int, max_len: int = 512, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2, dtype=torch.float32)
            * -(math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # (1, max_len, d_model)
        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Add positional encoding to input embeddings.

        Args:
            x: (batch, seq_len, d_model)
        """
        x = x + self.pe[:, : x.size(1)]
        return self.dropout(x)


# ── Behavioral Transformer Encoder ───────────────────────────────────────────

class BehavioralTransformerEncoder(nn.Module):
    """4-head Transformer Encoder for behavioral biometric sequences.

    Processes keystroke event sequences with self-attention to capture
    long-range typing rhythm dependencies that GRU/LSTM miss.

    Why 4 heads:
        - Head 1: consecutive digraph patterns
        - Head 2: rhythm periodicity across positions
        - Head 3: outlier keystroke detection
        - Head 4: session-level consistency (start vs end)
        (The model discovers these patterns — not hard-coded.)

    Dual-output architecture:
        1. risk_head → scalar [0,1] for real-time authentication scoring
        2. embedding_head → 128-dim vector for SimCLR contrastive enrollment
    """

    DEFAULT_SEQ_LEN = 200
    DEFAULT_FEATURE_DIM = 4  # hold_time, flight_time, key_position, timestamp_delta

    def __init__(
        self,
        sequence_length: int = DEFAULT_SEQ_LEN,
        feature_dim: int = DEFAULT_FEATURE_DIM,
        d_model: int = 64,
        nhead: int = 4,
        num_layers: int = 2,
        dim_feedforward: int = 128,
        dropout: float = 0.1,
        embedding_dim: int = 128,
    ):
        super().__init__()
        self.sequence_length = sequence_length
        self.feature_dim = feature_dim
        self.d_model = d_model
        self.nhead = nhead
        self.embedding_dim = embedding_dim

        # ── Input projection ─────────────────────────────────────────────
        # Linear projection from raw feature space to d_model
        self.input_projection = nn.Sequential(
            nn.Linear(feature_dim, d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),
        )

        # ── Positional Encoding ──────────────────────────────────────────
        self.positional_encoding = SinusoidalPositionalEncoding(
            d_model=d_model, max_len=max(sequence_length, 512), dropout=dropout
        )

        # ── Transformer Encoder Stack ────────────────────────────────────
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,  # Pre-LN for training stability
        )
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer, num_layers=num_layers
        )

        # ── Output layer norm ────────────────────────────────────────────
        self.output_norm = nn.LayerNorm(d_model)

        # ── Classification Head (real-time risk scoring) ─────────────────
        self.risk_head = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, 1),
            nn.Sigmoid(),
        )

        # ── Embedding Head (SimCLR contrastive enrollment) ───────────────
        self.embedding_head = nn.Sequential(
            nn.Linear(d_model, embedding_dim),
            nn.GELU(),
            nn.Linear(embedding_dim, embedding_dim),
        )

        # ── Data preprocessing ───────────────────────────────────────────
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names: Optional[List[str]] = None
        self.training_metrics: Dict[str, Any] = {}

    def _pool(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        """Mean pooling over the sequence dimension.

        Collapses (batch, seq_len, d_model) → (batch, d_model).
        Uses attention mask to exclude padding tokens if provided.
        """
        if mask is not None:
            # mask shape: (batch, seq_len), True = valid token
            mask_expanded = mask.unsqueeze(-1).float()  # (batch, seq_len, 1)
            x = x * mask_expanded
            return x.sum(dim=1) / mask_expanded.sum(dim=1).clamp(min=1)
        return x.mean(dim=1)

    def forward(
        self,
        x: torch.Tensor,
        src_key_padding_mask: Optional[torch.Tensor] = None,
        return_embeddings: bool = False,
    ) -> torch.Tensor:
        """Forward pass through the Behavioral Transformer.

        Args:
            x: Input tensor of shape (batch, seq_len, feature_dim)
            src_key_padding_mask: Boolean mask where True = padding (ignored).
            return_embeddings: If True, return 128-dim embeddings for SimCLR
                               instead of risk scores.

        Returns:
            If return_embeddings=False: (batch, 1) risk scores in [0, 1]
            If return_embeddings=True:  (batch, embedding_dim) L2-normalized
        """
        # Input projection: (batch, seq, feat_dim) → (batch, seq, d_model)
        x = self.input_projection(x)

        # Add positional encoding
        x = self.positional_encoding(x)

        # Transformer encoder with self-attention
        x = self.transformer_encoder(x, src_key_padding_mask=src_key_padding_mask)

        # Layer norm
        x = self.output_norm(x)

        # Mean pooling: (batch, seq, d_model) → (batch, d_model)
        valid_mask = ~src_key_padding_mask if src_key_padding_mask is not None else None
        pooled = self._pool(x, valid_mask)

        if return_embeddings:
            # SimCLR path — L2-normalized embeddings
            embeddings = self.embedding_head(pooled)
            return F.normalize(embeddings, dim=-1)
        else:
            # Risk scoring path
            return self.risk_head(pooled)

    # ── Attention visualization (for faculty demo) ───────────────────────

    def get_attention_weights(self, x: torch.Tensor) -> List[torch.Tensor]:
        """Extract attention weights from each layer for visualization.

        Returns list of (batch, nhead, seq_len, seq_len) tensors.
        Useful for showing faculty which keystroke pairs the model attends to.
        """
        self.eval()
        attention_maps = []

        with torch.no_grad():
            h = self.input_projection(x)
            h = self.positional_encoding(h)

            for layer in self.transformer_encoder.layers:
                # Access multi-head attention
                attn_output, attn_weights = layer.self_attn(
                    h, h, h, need_weights=True, average_attn_weights=False
                )
                attention_maps.append(attn_weights)
                # Full forward through the layer to get correct output for next layer
                h = layer(h)

        return attention_maps

    # ── Data preparation ─────────────────────────────────────────────────

    def prepare_sequences(
        self, features: List[Dict], fit_scaler: bool = False
    ) -> torch.Tensor:
        """Convert feature dictionaries to padded sequences.

        Args:
            features: List of feature dicts (one per keystroke event).
            fit_scaler: If True, fit the scaler on this data.

        Returns:
            Tensor of shape (num_sequences, sequence_length, feature_dim)
        """
        if not features:
            return torch.empty(0, self.sequence_length, self.feature_dim)

        # Establish feature name ordering
        if self.feature_names is None:
            all_keys = set()
            for f in features:
                all_keys.update(f.keys())
            self.feature_names = sorted(all_keys)

        # Convert to matrix
        data_matrix = np.array(
            [[f.get(name, 0.0) for name in self.feature_names] for f in features],
            dtype=np.float32,
        )

        # Normalize
        if fit_scaler or not self.is_trained:
            data_matrix = self.scaler.fit_transform(data_matrix)
        else:
            data_matrix = self.scaler.transform(data_matrix)

        # Create sliding window sequences
        sequences = []
        if len(data_matrix) >= self.sequence_length:
            for i in range(len(data_matrix) - self.sequence_length + 1):
                sequences.append(data_matrix[i : i + self.sequence_length])
        else:
            # Pad short sequences with zeros
            padded = np.zeros((self.sequence_length, data_matrix.shape[1]), dtype=np.float32)
            padded[: len(data_matrix)] = data_matrix
            sequences.append(padded)

        return torch.FloatTensor(np.array(sequences))

    # ── Training ─────────────────────────────────────────────────────────

    def train_model(
        self,
        genuine_features: List[Dict],
        imposter_features: Optional[List[Dict]] = None,
        epochs: int = 100,
        lr: float = 1e-3,
        batch_size: int = 32,
    ) -> Dict[str, Any]:
        """Train the Behavioral Transformer on user data.

        Args:
            genuine_features: List of feature dicts from the genuine user.
            imposter_features: Optional imposter data for contrastive training.
            epochs: Number of training epochs.
            lr: Learning rate.
            batch_size: Training batch size.

        Returns:
            Training metrics dict.
        """
        logger.info(
            "Starting BehavioralTransformerEncoder training "
            "(d_model=%d, heads=%d, layers=2, ff=%d)...",
            self.d_model, self.nhead, self.d_model * 2,
        )

        # Prepare data
        genuine_sequences = self.prepare_sequences(genuine_features, fit_scaler=True)
        if len(genuine_sequences) == 0:
            return {"error": "Insufficient genuine data for sequences"}

        labels = torch.ones(len(genuine_sequences), 1)

        if imposter_features:
            imposter_sequences = self.prepare_sequences(imposter_features)
            if len(imposter_sequences) > 0:
                genuine_sequences = torch.cat([genuine_sequences, imposter_sequences])
                labels = torch.cat([labels, torch.zeros(len(imposter_sequences), 1)])

        dataset = TensorDataset(genuine_sequences, labels)
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        # Training setup
        optimizer = optim.AdamW(self.parameters(), lr=lr, weight_decay=1e-4)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
        criterion = nn.BCELoss()

        # Training loop
        super().train()
        best_loss = float("inf")
        loss_history = []

        for epoch in range(epochs):
            total_loss = 0.0
            for sequences, batch_labels in dataloader:
                optimizer.zero_grad()
                outputs = self(sequences)  # (batch, 1)
                loss = criterion(outputs, batch_labels)
                loss.backward()

                # Gradient clipping for training stability
                torch.nn.utils.clip_grad_norm_(self.parameters(), max_norm=1.0)

                optimizer.step()
                total_loss += loss.item()

            scheduler.step()
            avg_loss = total_loss / len(dataloader)
            loss_history.append(avg_loss)

            if avg_loss < best_loss:
                best_loss = avg_loss

            if epoch % 20 == 0:
                logger.info(
                    "Epoch %d/%d — loss: %.4f, lr: %.6f",
                    epoch, epochs, avg_loss, scheduler.get_last_lr()[0],
                )

        self.is_trained = True
        self.training_metrics = {
            "final_loss": best_loss,
            "epochs": epochs,
            "sequences": len(genuine_sequences),
            "d_model": self.d_model,
            "nhead": self.nhead,
            "parameters": sum(p.numel() for p in self.parameters()),
        }

        logger.info(
            "BehavioralTransformerEncoder training complete — "
            "loss=%.4f, params=%d, sequences=%d",
            best_loss,
            self.training_metrics["parameters"],
            len(genuine_sequences),
        )

        return self.training_metrics

    # ── SimCLR contrastive training ──────────────────────────────────────

    def train_contrastive(
        self,
        features: List[Dict],
        temperature: float = 0.5,
        epochs: int = 100,
        batch_size: int = 32,
    ) -> np.ndarray:
        """Train using NT-Xent contrastive loss for enrollment embeddings.

        Uses the same encoder backbone as risk scoring, with the
        embedding_head producing 128-dim L2-normalized vectors.

        Returns:
            Mean embedding for the user (128-dim).
        """
        logger.info("Starting contrastive enrollment training...")

        sequences = self.prepare_sequences(features, fit_scaler=True)
        if len(sequences) == 0:
            return np.zeros(self.embedding_dim)

        optimizer = optim.AdamW(self.parameters(), lr=1e-3, weight_decay=1e-4)

        super().train()
        for epoch in range(epochs):
            total_loss = 0.0
            # Create augmented pairs
            for i in range(0, len(sequences), batch_size):
                batch = sequences[i : i + batch_size]
                if len(batch) < 2:
                    continue

                optimizer.zero_grad()

                # Augmentation: add small Gaussian noise to create views
                noise_scale = 0.02
                view1 = batch + torch.randn_like(batch) * noise_scale
                view2 = batch + torch.randn_like(batch) * noise_scale

                # Get embeddings from both views
                z1 = self(view1, return_embeddings=True)  # (batch, 128)
                z2 = self(view2, return_embeddings=True)

                # NT-Xent loss
                B = z1.shape[0]
                similarity = torch.mm(z1, z2.T) / temperature  # (B, B)
                labels = torch.arange(B)
                loss = F.cross_entropy(similarity, labels)

                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.parameters(), max_norm=1.0)
                optimizer.step()
                total_loss += loss.item()

            if epoch % 20 == 0:
                logger.info("Contrastive epoch %d — loss: %.4f", epoch, total_loss)

        # Generate final embedding
        self.eval()
        with torch.no_grad():
            embeddings = self(sequences, return_embeddings=True)
            mean_embedding = embeddings.mean(dim=0).numpy()

        self.is_trained = True
        logger.info(
            "Contrastive training complete — embedding dim=%d, norm=%.4f",
            len(mean_embedding), np.linalg.norm(mean_embedding),
        )
        return mean_embedding

    # ── Prediction ───────────────────────────────────────────────────────

    def predict(self, features: List[Dict]) -> Tuple[float, float]:
        """Predict authenticity score and confidence for a feature sequence.

        Returns:
            (score, confidence) — score in [0,1], confidence in [0,1].
        """
        if not self.is_trained:
            return 0.5, 0.0

        self.eval()
        with torch.no_grad():
            sequences = self.prepare_sequences(features)
            if len(sequences) == 0:
                return 0.5, 0.0

            # Use the last (most recent) sequence
            output = self(sequences[-1:])  # (1, 1)
            score = output.item()
            confidence = abs(score - 0.5) * 2.0

        return float(score), float(confidence)

    def get_embedding(self, features: List[Dict]) -> np.ndarray:
        """Get 128-dim behavioral embedding for the given features.

        Used for SimCLR comparison during re-verification.
        """
        self.eval()
        with torch.no_grad():
            sequences = self.prepare_sequences(features)
            if len(sequences) == 0:
                return np.zeros(self.embedding_dim)

            embeddings = self(sequences, return_embeddings=True)
            return embeddings.mean(dim=0).numpy()

    # ── Persistence ──────────────────────────────────────────────────────

    def save(self, filepath: str):
        """Save model state, scaler, and metadata."""
        torch.save(
            {
                "state_dict": self.state_dict(),
                "scaler": self.scaler,
                "sequence_length": self.sequence_length,
                "feature_dim": self.feature_dim,
                "d_model": self.d_model,
                "nhead": self.nhead,
                "embedding_dim": self.embedding_dim,
                "feature_names": self.feature_names,
                "is_trained": self.is_trained,
                "training_metrics": self.training_metrics,
            },
            f"{filepath}_transformer.pt",
        )
        logger.info("Saved BehavioralTransformerEncoder to %s_transformer.pt", filepath)

    def load(self, filepath: str) -> bool:
        """Load model state and metadata."""
        try:
            checkpoint = torch.load(
                f"{filepath}_transformer.pt", weights_only=False
            )
            self.load_state_dict(checkpoint["state_dict"])
            self.scaler = checkpoint["scaler"]
            self.sequence_length = checkpoint.get("sequence_length", self.DEFAULT_SEQ_LEN)
            self.feature_dim = checkpoint.get("feature_dim", self.DEFAULT_FEATURE_DIM)
            self.d_model = checkpoint.get("d_model", 64)
            self.nhead = checkpoint.get("nhead", 4)
            self.embedding_dim = checkpoint.get("embedding_dim", 128)
            self.feature_names = checkpoint.get("feature_names")
            self.is_trained = checkpoint.get("is_trained", True)
            self.training_metrics = checkpoint.get("training_metrics", {})
            logger.info("Loaded BehavioralTransformerEncoder from %s_transformer.pt", filepath)
            return True
        except Exception:
            logger.warning(
                "Failed to load BehavioralTransformerEncoder from %s_transformer.pt",
                filepath,
            )
            return False

    def export_onnx(self, path: str) -> bool:
        """Export model to ONNX format for edge deployment.

        Banking Performance: Enables INT8 quantization via
        onnxruntime.quantization for <15ms inference.
        """
        self.eval()
        dummy_input = torch.randn(1, self.sequence_length, self.feature_dim)
        try:
            torch.onnx.export(
                self,
                dummy_input,
                path,
                input_names=["behavioral_sequence"],
                output_names=["risk_score"],
                dynamic_axes={
                    "behavioral_sequence": {0: "batch_size", 1: "seq_len"},
                    "risk_score": {0: "batch_size"},
                },
                opset_version=14,
            )
            logger.info("Exported BehavioralTransformerEncoder to ONNX: %s", path)
            return True
        except Exception:
            logger.exception("ONNX export failed for BehavioralTransformerEncoder")
            return False

    # ── Summary ──────────────────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        """Architecture summary for logging and faculty presentation."""
        total_params = sum(p.numel() for p in self.parameters())
        trainable_params = sum(p.numel() for p in self.parameters() if p.requires_grad)

        return {
            "model": "BehavioralTransformerEncoder",
            "architecture": {
                "d_model": self.d_model,
                "nhead": self.nhead,
                "num_layers": 2,
                "dim_feedforward": self.d_model * 2,
                "dropout": 0.1,
                "positional_encoding": "sinusoidal",
                "pooling": "mean",
            },
            "input": {
                "sequence_length": self.sequence_length,
                "feature_dim": self.feature_dim,
                "features_per_event": ["hold_time", "flight_time", "key_position", "timestamp_delta"],
            },
            "outputs": {
                "risk_head": "scalar [0, 1]",
                "embedding_head": f"{self.embedding_dim}-dim L2-normalized",
            },
            "parameters": {
                "total": total_params,
                "trainable": trainable_params,
            },
            "is_trained": self.is_trained,
            "training_metrics": self.training_metrics,
        }
