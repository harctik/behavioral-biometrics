"""
Siamese Network for cross-session identity matching.

Corporate Banking Feature: Detects account sharing and credential
handoffs by comparing behavioral embeddings across sessions.

RBI Compliance: Maker-Checker dual-control mandate — independently
verify that the Maker and Checker are different individuals by
comparing their behavioral embeddings.

Inference target: 15ms per comparison.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import numpy as np
from sklearn.preprocessing import StandardScaler
from typing import List, Dict, Tuple, Optional
import joblib
import logging

logger = logging.getLogger(__name__)


class SiameseEncoder(nn.Module):
    """Shared-weight encoder for behavioral embedding extraction."""

    def __init__(self, input_dim: int = 38, embedding_dim: int = 64):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.BatchNorm1d(128),
            nn.Dropout(0.2),
            nn.Linear(128, 96),
            nn.ReLU(),
            nn.BatchNorm1d(96),
            nn.Dropout(0.1),
            nn.Linear(96, embedding_dim),
        )

    def forward(self, x):
        return self.encoder(x)


class SiameseNetwork(nn.Module):
    """Siamese Network for behavioral identity matching.

    Uses contrastive loss to learn embeddings where:
    - Same user sessions are close together
    - Different user sessions are far apart

    Use Cases:
    - Cross-session identity verification
    - Maker-Checker dual verification (corporate banking)
    - Account sharing / credential handoff detection
    """

    def __init__(self, input_dim: int = 38, embedding_dim: int = 64):
        super().__init__()
        self.encoder = SiameseEncoder(input_dim, embedding_dim)
        self.embedding_dim = embedding_dim
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names: Optional[List[str]] = None
        self.similarity_threshold = 0.75

    def forward(self, x1, x2):
        """Forward pass — encode both inputs with shared weights."""
        emb1 = self.encoder(x1)
        emb2 = self.encoder(x2)
        return emb1, emb2

    def contrastive_loss(
        self,
        emb1: torch.Tensor,
        emb2: torch.Tensor,
        label: torch.Tensor,
        margin: float = 1.0,
    ) -> torch.Tensor:
        """Contrastive loss for Siamese training.

        label=1: same user (should be close)
        label=0: different users (should be far apart)
        """
        distance = F.pairwise_distance(emb1, emb2)
        # Same user: minimize distance
        # Different user: maximize distance up to margin
        loss = label * distance.pow(2) + (1 - label) * F.relu(margin - distance).pow(2)
        return loss.mean()

    def _ensure_feature_consistency(self, features: List[Dict]) -> List[Dict]:
        """Ensure all feature dicts have the same keys."""
        if not features:
            return features
        if self.feature_names is None:
            self.feature_names = sorted(set().union(*(f.keys() for f in features)))
        return [
            {name: f.get(name, 0.0) for name in self.feature_names} for f in features
        ]

    def prepare_data(
        self, features: List[Dict], fit_scaler: bool = False
    ) -> np.ndarray:
        """Convert feature dicts to scaled numpy matrix."""
        features = self._ensure_feature_consistency(features)
        if not features:
            return np.array([])
        matrix = np.array([[f[name] for name in self.feature_names] for f in features])
        if fit_scaler:
            matrix = self.scaler.fit_transform(matrix)
        elif self.is_trained:
            matrix = self.scaler.transform(matrix)
        return matrix

    def train_model(
        self,
        same_user_pairs: List[Tuple[List[Dict], List[Dict]]],
        diff_user_pairs: List[Tuple[List[Dict], List[Dict]]],
        epochs: int = 50,
    ) -> Dict:
        """Train Siamese network on session pairs.

        Args:
            same_user_pairs: List of (session_A_features, session_B_features) from same user
            diff_user_pairs: List of (session_A_features, session_B_features) from different users
        """
        logger.info("Starting Siamese network training...")

        # Aggregate all features for scaler fitting
        all_features = []
        for a, b in same_user_pairs + diff_user_pairs:
            all_features.extend(a)
            all_features.extend(b)
        self.prepare_data(all_features, fit_scaler=True)

        # Build training pairs
        pairs_a, pairs_b, labels = [], [], []
        for a_feats, b_feats in same_user_pairs:
            a_data = self.prepare_data(a_feats)
            b_data = self.prepare_data(b_feats)
            if len(a_data) > 0 and len(b_data) > 0:
                pairs_a.append(np.mean(a_data, axis=0))
                pairs_b.append(np.mean(b_data, axis=0))
                labels.append(1.0)

        for a_feats, b_feats in diff_user_pairs:
            a_data = self.prepare_data(a_feats)
            b_data = self.prepare_data(b_feats)
            if len(a_data) > 0 and len(b_data) > 0:
                pairs_a.append(np.mean(a_data, axis=0))
                pairs_b.append(np.mean(b_data, axis=0))
                labels.append(0.0)

        if not pairs_a:
            return {"error": "No valid training pairs"}

        X_a = torch.FloatTensor(np.array(pairs_a))
        X_b = torch.FloatTensor(np.array(pairs_b))
        Y = torch.FloatTensor(labels)

        optimizer = torch.optim.Adam(self.parameters(), lr=0.001)

        self.train()
        best_loss = float("inf")
        for epoch in range(epochs):
            optimizer.zero_grad()
            emb_a, emb_b = self(X_a, X_b)
            loss = self.contrastive_loss(emb_a, emb_b, Y)
            loss.backward()
            optimizer.step()

            if epoch % 10 == 0:
                logger.info(f"Siamese Epoch {epoch}, Loss: {loss.item():.4f}")
            if loss.item() < best_loss:
                best_loss = loss.item()

        self.is_trained = True
        logger.info("Siamese network training completed")

        return {
            "final_loss": float(best_loss),
            "training_pairs": len(pairs_a),
            "same_user_pairs": len(same_user_pairs),
            "diff_user_pairs": len(diff_user_pairs),
        }

    def predict_identity_match(
        self,
        session_a_features: List[Dict],
        session_b_features: List[Dict],
    ) -> Dict:
        """Compare behavioral profiles from two sessions.

        Returns similarity score and whether they match (same person).
        Used for:
        - Cross-session identity verification
        - Maker-Checker dual verification
        - Account sharing detection
        """
        if not self.is_trained:
            return {"similarity": 0.5, "is_match": False, "confidence": 0.0}

        a_data = self.prepare_data(session_a_features)
        b_data = self.prepare_data(session_b_features)

        if len(a_data) == 0 or len(b_data) == 0:
            return {"similarity": 0.5, "is_match": False, "confidence": 0.0}

        # Average feature vectors for each session
        a_mean = torch.FloatTensor(np.mean(a_data, axis=0)).unsqueeze(0)
        b_mean = torch.FloatTensor(np.mean(b_data, axis=0)).unsqueeze(0)

        self.eval()
        with torch.no_grad():
            emb_a, emb_b = self(a_mean, b_mean)
            # Cosine similarity
            similarity = F.cosine_similarity(emb_a, emb_b).item()
            # Euclidean distance (normalized)
            distance = F.pairwise_distance(emb_a, emb_b).item()

        # Convert to [0, 1] similarity score
        similarity_score = (similarity + 1.0) / 2.0  # Cosine sim is [-1, 1]
        confidence = abs(similarity_score - 0.5) * 2.0

        return {
            "similarity": round(float(similarity_score), 4),
            "distance": round(float(distance), 4),
            "is_match": similarity_score >= self.similarity_threshold,
            "confidence": round(float(confidence), 4),
        }

    def verify_maker_checker(
        self,
        maker_features: List[Dict],
        checker_features: List[Dict],
    ) -> Dict:
        """Corporate banking: Verify Maker and Checker are different people.

        RBI dual-control mandate: Transactions above Rs. 10,00,000 require
        two authorized persons. This verifies their behavioral profiles
        are genuinely different — detecting one person controlling both accounts.
        """
        result = self.predict_identity_match(maker_features, checker_features)

        # For maker-checker, we WANT them to be DIFFERENT people
        is_compliance_violation = result["is_match"]  # Same person = violation

        return {
            "maker_checker_verified": not is_compliance_violation,
            "behavioral_similarity": result["similarity"],
            "compliance_violation": is_compliance_violation,
            "confidence": result["confidence"],
            "violation_type": "same_person_dual_control"
            if is_compliance_violation
            else None,
            "recommendation": (
                "ALERT: Same behavioral profile on Maker and Checker accounts. "
                "Escalate to third-level authorization."
                if is_compliance_violation
                else "Maker and Checker behavioral profiles are distinct. Proceeding."
            ),
        }

    def save(self, path: str):
        """Save Siamese network state."""
        torch.save(
            {
                "state_dict": self.state_dict(),
                "scaler": self.scaler,
                "feature_names": self.feature_names,
                "embedding_dim": self.embedding_dim,
                "similarity_threshold": self.similarity_threshold,
                "is_trained": self.is_trained,
            },
            path,
        )

    def load(self, path: str) -> bool:
        """Load Siamese network state."""
        try:
            checkpoint = torch.load(path, weights_only=False)
            self.load_state_dict(checkpoint["state_dict"])
            self.scaler = checkpoint["scaler"]
            self.feature_names = checkpoint.get("feature_names")
            self.similarity_threshold = checkpoint.get("similarity_threshold", 0.75)
            self.is_trained = checkpoint.get("is_trained", True)
            return True
        except Exception:
            logger.exception("Failed to load Siamese network from %s", path)
            return False
