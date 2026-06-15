# ML Model Card — BehaviorGuard Ensemble

## Overview

BehaviorGuard uses a **13-engine ensemble** for continuous behavioral authentication.
Each engine specializes in a different behavioral signal, and their scores are fused
via a **Bayesian belief-update framework** for the final authentication decision.

## Engines

| # | Engine | Architecture | Signal | Training | Scoring |
|---|--------|-------------|--------|----------|---------| 
| 1 | Keystroke Dynamics | GRU (2-layer, hidden=128) | Key dwell/flight time distributions | Per-user, ≥30 calibration samples | Mahalanobis distance → [0,1] |
| 2 | Mouse Biometrics | Autoencoder (3-layer, latent=32) | Velocity, curvature, acceleration | Per-user, ≥30 samples | Reconstruction error → [0,1] |
| 3 | One-Class SVM | sklearn OneClassSVM (RBF kernel) | Merged keystroke + mouse features | Per-user, ≥50 samples | Decision boundary distance |
| 4 | Isolation Forest | sklearn IsolationForest (n=100) | All behavioral features | Per-user, ≥30 samples | Anomaly score [-1,1] → [0,1] |
| 5 | Siamese Network | Twin MLP + contrastive loss | Maker-Checker behavioral verify | User pair, ≥20 paired samples | Similarity distance |
| 6 | SimCLR | Contrastive encoder (projection head) | Passive enrollment representation | Pre-trained backbone + fine-tune | Cosine similarity |
| 7 | Duress Detector | 43-feature statistical analysis | Stress/coercion indicators | Per-user baseline, ≥50 samples | Deviation z-score |
| 8 | Liveness Detector | Heuristic + statistical | Bot/replay detection (timing) | Global model | Binary classifier |
| 9 | Cognitive Engine | Intent detection neural net | APP fraud, duress, bot, takeover | Per-user + global baseline | Multi-class probability |
| 10 | Device Intelligence | Fingerprint + geo analysis | RAT, emulator, geo-velocity | Device history database | Trust score [0,1] |
| 11 | Composite Signal Engine | Multi-modal fusion | Lie detection, multi-user patterns | Cross-session analysis | Anomaly probability |
| 12 | GAN Adversarial | CTGAN-style discriminator | Synthetic behavior replay detection | Generative-adversarial training | Discriminator confidence |
| 13 | Transaction Baseline | Statistical profiling | Amount, beneficiary, timing anomalies | Per-user transaction history | Deviation score |

## Fusion Strategies

### A. Legacy Weighted Average (`score_with_ensemble`)
Simple weighted average across engine scores. Retained for backward compatibility.

### B. Bayesian Belief-Update Fusion (`score_with_bayesian_fusion`) ★ Recommended
State-of-the-art fusion using log-odds belief updates:
- **Uncertainty-aware**: Each engine reports score + confidence
- **Self-calibrating**: Engine reliability priors adapt over time
- **Fully explainable**: Audit trail shows how each engine shifted belief (SHAP-like)
- **Robust to failure**: Gracefully degrades on low-confidence signals

## Feature Pipeline

```
Browser JS Collector (200+ raw features)
    ↓
/api/v1/behavioral/data (POST, JWT-authenticated)
    ↓
BehavioralFeatureExtractor (app/feature_extractor.py)
    ↓ 200+ raw features → top-20 per-user (BioCatch-style selector)
    ↓
MLEnsemble.score_with_bayesian_fusion(user_id, features)
    ↓ Bayesian belief-update across 13 engines
    ↓
Risk Level: low (<0.35) | medium (0.35–0.65) | high (>0.65)
```

## Drift Detection

- **Algorithm:** ADWIN (Adaptive Windowing) via `app/models/adwin_drift.py`
- **Trigger:** When the distribution of a user's feature vector changes beyond α=0.05
- **Response:** Flags `drift_detected=True` in `model_metadata`, triggers model retrain

## Per-User Feature Selection

Inspired by BioCatch's approach:
1. Extract all 200+ behavioral features
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
2. **No GPU required:** All models are CPU-efficient by design for real-time (<50ms) inference
3. **PostgreSQL recommended:** Model metadata stored in DB; PostgreSQL for multi-instance deployments

## Metrics & Thresholds

| Metric | Default Threshold | Config Key |
|--------|------------------|------------|
| Anomaly score | 0.80 | `ANOMALY_SCORE_THRESHOLD` |
| Confidence score | 0.70 | `CONFIDENCE_THRESHOLD` |
| High risk | >0.65 | `RISK_HIGH_THRESHOLD` |
| Medium risk | 0.35–0.65 | `RISK_MEDIUM_THRESHOLD` |
| Step-up trigger | >0.60 | `STEP_UP_RISK_SCORE_THRESHOLD` |
| Consecutive anomalies | 3 | `CONSECUTIVE_ANOMALIES_LIMIT` |
