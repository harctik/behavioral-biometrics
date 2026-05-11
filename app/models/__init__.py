"""ML models package for behavioral biometrics authentication.

Core Models:
- BehavioralTransformerEncoder: 4-head self-attention (PRIMARY sequence model)
- AutoencoderAnomalyDetector: Reconstruction-error anomaly detection
- OneClassSVMDetector: Boundary-based novelty detection
- IncrementalKNNClassifier: Online k-NN for incremental learning
- IsolationForestDetector: Ensemble anomaly detection
- GRUSequenceModel: Legacy recurrent model (lower weight in ensemble)
- PassiveAggressiveDetector: Streaming classifier

Banking Extensions:
- DuressDetector: 43-feature stress/coercion detection
- SiameseNetwork: Maker-Checker behavioral verification
- SimCLRModel: Contrastive learning for fast enrollment
  (uses BehavioralTransformerEncoder as shared backbone)

BioCatch-Aligned Engines:
- PassiveEnrollmentManager: Silent profile building (replaces calibration)
- PerUserFeatureSelector: Top-20 unique features per user (BioCatch patent)
- TransactionHistoryBaseline: Amount/beneficiary/timing anomaly scoring

Ensemble:
- EnsembleBehavioralClassifier: Orchestrates all models with progressive enrollment
  Transformer (0.25) > Autoencoder (0.20) > SVM (0.15) > k-NN (0.15)
  > Isolation Forest (0.10) > GRU (0.10) > PA (0.05)
"""
