# ML Model Card — BehaviorGuard Ensemble

## Overview

BehaviorGuard uses an **8-model ensemble** for continuous behavioral authentication.
Each model specializes in a different behavioral signal, and their scores are fused
via a weighted-average combiner for the final authentication decision.

## Models

| # | Model | Architecture | Signal | Training | Scoring |
|---|-------|-------------|--------|----------|---------|
| 1 | Keystroke Dynamics | GRU (2-layer, hidden=128) | Key dwell/flight time distributions | Per-user, ≥30 calibration samples | Mahalanobis distance → [0,1] |
| 2 | Mouse Biometrics | Autoencoder (3-layer, latent=32) | Velocity, curvature, acceleration | Per-user, ≥30 samples | Reconstruction error → [0,1] |
| 3 | One-Class SVM | sklearn OneClassSVM (RBF kernel) | Merged keystroke + mouse features | Per-user, ≥50 samples | Decision boundary distance |
| 4 | Isolation Forest | sklearn IsolationForest (n=100) | All behavioral features | Per-user, ≥30 samples | Anomaly score [-1,1] → [0,1] |
| 5 | Siamese Network | Twin MLP + contrastive loss | Maker-Checker behavioral verify | User pair, ≥20 paired samples | Similarity distance |
| 6 | SimCLR | Contrastive encoder (projection head) | Passive enrollment representation | Pre-trained backbone + fine-tune | Cosine similarity |
| 7 | Duress Detector | Statistical thresholding | Stress indicators in typing rhythm | Per-user baseline, ≥50 samples | Deviation z-score |
| 8 | Liveness Detector | Heuristic + statistical | Bot/replay detection (timing) | Global model | Binary classifier |

## Feature Pipeline

```
Browser JS Collector
    ↓
/api/v1/behavioral/data (POST, JWT-authenticated)
    ↓
BehavioralFeatureExtractor (app/feature_extractor.py)
    ↓ 48 raw features → top-20 per-user (BioCatch-style selector)
    ↓
MLEnsemble.score(user_id, features)
    ↓ weighted average across 8 models
    ↓
Risk Level: low (<0.35) | medium (0.35–0.65) | high (>0.65)
```

## Drift Detection

- **Algorithm:** ADWIN (Adaptive Windowing) via `app/models/adwin_drift.py`
- **Trigger:** When the distribution of a user's feature vector changes beyond α=0.05
- **Response:** Flags `drift_detected=True` in `model_metadata`, triggers model retrain

## Per-User Feature Selection

Inspired by BioCatch's approach:
1. Extract all 48 behavioral features
2. Compute mutual information between each feature and the user's identity
3. Select top-20 features with highest discriminative power for that user
4. Store feature mask in `model_metadata` for inference

## Training

- **Mode:** Online per-user training; no batch pre-training required
- **Cold start:** System operates in "enrollment mode" for users with <30 samples
- **Retrain trigger:** Drift detection, or manual via admin API
- **Storage:** `models/saved/{user_id}/` (sklearn joblib + PyTorch state_dict)

## Known Limitations

1. **Cold start:** Users with <30 behavioral samples get permissive scoring (allow with monitoring)
2. **GAN model not integrated:** `gan_adversarial.py` exists but is not wired into the ensemble scorer
3. **No GPU required:** All models are CPU-efficient by design for real-time (<50ms) inference
4. **SQLite constraint:** Model metadata is stored in SQLite; PostgreSQL recommended for multi-instance

## Metrics & Thresholds

| Metric | Default Threshold | Config Key |
|--------|------------------|------------|
| Anomaly score | 0.80 | `ANOMALY_SCORE_THRESHOLD` |
| Confidence score | 0.70 | `CONFIDENCE_THRESHOLD` |
| High risk | >0.65 | `RISK_HIGH_THRESHOLD` |
| Medium risk | 0.35–0.65 | `RISK_MEDIUM_THRESHOLD` |
| Step-up trigger | >0.60 | `STEP_UP_RISK_SCORE_THRESHOLD` |
| Consecutive anomalies | 3 | `CONSECUTIVE_ANOMALIES_LIMIT` |
