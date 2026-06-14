"""
Silent Duress and Coercion Detection Engine.

First-of-its-kind in Indian banking behavioral biometrics.

Detects when users are physically coerced into initiating fraudulent
transfers by analyzing 40+ behavioral stress markers. When duress is
detected, the system alerts bank security SILENTLY — no visible change
to the session that could endanger the user.

Compliance: RBI Master Direction 2021 — continuous risk monitoring.

Stress Features Analyzed:
- Keystroke jitter (hold time variance vs baseline σ)
- Mouse tremor (high-frequency jerk oscillations)
- Typing speed deviation (>3σ from baseline)
- Error rate spike (backspace frequency >4× baseline)
- Hesitation patterns (unusual pauses before high-value confirmations)
- Cognitive load indicators (decision time on routine fields)
"""

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from typing import Dict, List, Tuple, Optional
import joblib
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Feature definitions for duress detection ────────────────────────────

DURESS_FEATURES = [
    # Keystroke stress markers (20 features)
    "hold_time_jitter",  # Variance in hold times vs baseline σ
    "hold_time_mean_deviation",  # Mean hold time deviation from baseline
    "flight_time_jitter",  # Variance in flight times vs baseline
    "flight_time_mean_deviation",  # Mean flight time deviation from baseline
    "typing_speed_z_score",  # Speed deviation in σ from baseline
    "typing_speed_acceleration",  # Rate of speed change during session
    "backspace_frequency",  # Error correction rate (backspace/total keys)
    "backspace_burst_count",  # Number of rapid backspace sequences
    "error_rate_vs_baseline",  # Current error rate / baseline error rate
    "pause_frequency",  # Number of pauses >2 seconds
    "pause_duration_mean",  # Average pause duration
    "pause_before_confirm",  # Pause duration before confirmation actions
    "inter_key_interval_cv",  # Coefficient of variation in IKI
    "key_pressure_variance",  # Pressure inconsistency
    "rhythm_breakdown_score",  # How much rhythm deviates from baseline
    "digraph_timing_deviation",  # Specific key-pair timing deviation
    "deletion_retype_ratio",  # Ratio of delete-then-retype sequences
    "capitalization_errors",  # Case errors (stress indicator)
    "typing_burst_irregularity",  # Irregularity in burst typing patterns
    "key_sequence_entropy",  # Entropy of key sequence (randomness)
    # Mouse stress markers (15 features)
    "mouse_tremor_score",  # High-frequency cursor oscillations
    "mouse_jerk_mean",  # Mean jerk (derivative of acceleration)
    "mouse_jerk_std",  # Jerk variability
    "cursor_overshoot_rate",  # Rate of overshooting click targets
    "click_hesitation_mean",  # Delay between reaching target and clicking
    "double_click_rate",  # Unintentional double-click frequency
    "scroll_jitter",  # Scroll behavior irregularity
    "movement_reversal_rate",  # How often cursor reverses direction
    "path_efficiency_drop",  # Drop in movement efficiency vs baseline
    "velocity_spike_count",  # Number of sudden velocity changes
    "acceleration_irregularity",  # Acceleration pattern irregularity
    "idle_periods_in_motion",  # Stop-start patterns during movement
    "click_pressure_variance",  # Click force inconsistency
    "drag_tremor_score",  # Tremor during drag operations
    "hover_instability",  # Cursor instability during hover
    # Cognitive load & session indicators (8 features)
    "decision_time_increase",  # Time on decisions vs baseline
    "field_navigation_errors",  # Wrong-field entries
    "form_completion_time_ratio",  # Session form time vs baseline
    "transaction_amount_hesitation",  # Pause before entering amount
    "beneficiary_entry_pattern",  # Copy-paste vs typed (APP fraud signal)
    "session_duration_anomaly",  # Session length vs baseline
    "time_of_day_risk",  # Unusual access hours
    "concurrent_session_flag",  # Multiple sessions detected
    # Advanced stress markers (5 new features)
    "modifier_overlap_instability",  # Erratic shift-key timing
    "digraph_rhythm_deviation",  # Per-pair timing breakdown
    "flight_cv_spike",  # Sudden flight time variability
    "correction_burst_density",  # Backspace clusters per minute
    "inter_field_hesitation_ratio",  # Hesitation between form fields
]

DURESS_FEATURE_COUNT = len(DURESS_FEATURES)  # Should be 48


class DuressDetector:
    """Gradient Boosting-based duress and coercion detector.

    Analyzes 43 behavioral stress features and produces a composite
    duress score. Designed for Indian banking sector deployment.

    Silent Alert Protocol:
    - Score > 0.75: Silent SOC alert + encrypted fraud team notification
    - Score 0.5-0.75: Elevated monitoring, prepare for silent challenge
    - Score < 0.5: Normal monitoring

    The transaction ALWAYS continues normally — no visible change to
    protect the user from the coercer.
    """

    def __init__(self):
        self.model = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            min_samples_split=10,
            subsample=0.8,
            random_state=42,
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.baseline_profiles: Dict[int, Dict] = {}
        self.alert_threshold = 0.75
        self.monitor_threshold = 0.50

    def set_user_baseline(self, user_id: int, baseline_features: List[Dict]):
        """Establish behavioral baseline for a user from normal sessions.

        Called during enrollment phase. The baseline represents the user's
        normal behavioral patterns against which deviations are measured.
        """
        if not baseline_features:
            return

        # Compute statistical baseline for each feature
        baseline = {}
        all_keys = set()
        for f in baseline_features:
            all_keys.update(f.keys())

        for key in all_keys:
            values = [
                f.get(key, 0.0)
                for f in baseline_features
                if isinstance(f.get(key), (int, float))
            ]
            if values:
                baseline[key] = {
                    "mean": float(np.mean(values)),
                    "std": float(np.std(values)) if len(values) > 1 else 1.0,
                    "median": float(np.median(values)),
                    "q25": float(np.percentile(values, 25)),
                    "q75": float(np.percentile(values, 75)),
                }

        self.baseline_profiles[user_id] = baseline
        logger.info(
            f"Duress baseline set for user {user_id} with {len(baseline)} features"
        )

    def extract_duress_features(
        self,
        user_id: int,
        keystroke_features: Dict,
        mouse_features: Dict,
        session_context: Optional[Dict] = None,
    ) -> Dict[str, float]:
        """Extract 43 duress-specific features from current behavioral data.

        Compares current behavior against the user's established baseline
        to detect stress markers.
        """
        baseline = self.baseline_profiles.get(user_id, {})
        ctx = session_context or {}
        duress = {}

        # ── Keystroke stress markers ────────────────────────────────

        # Hold time jitter (variance deviation from baseline)
        ht_std = keystroke_features.get("hold_time_std", 0.0)
        ht_baseline_std = baseline.get("hold_time_std", {}).get("mean", ht_std)
        duress["hold_time_jitter"] = abs(ht_std - ht_baseline_std) / (
            ht_baseline_std + 1e-6
        )

        # Hold time mean deviation
        ht_mean = keystroke_features.get("hold_time_mean", 0.0)
        ht_baseline_mean = baseline.get("hold_time_mean", {}).get("mean", ht_mean)
        ht_baseline_std_val = baseline.get("hold_time_mean", {}).get("std", 1.0)
        duress["hold_time_mean_deviation"] = abs(ht_mean - ht_baseline_mean) / (
            ht_baseline_std_val + 1e-6
        )

        # Flight time stress markers
        ft_std = keystroke_features.get("flight_time_std", 0.0)
        ft_baseline_std = baseline.get("flight_time_std", {}).get("mean", ft_std)
        duress["flight_time_jitter"] = abs(ft_std - ft_baseline_std) / (
            ft_baseline_std + 1e-6
        )

        ft_mean = keystroke_features.get("flight_time_mean", 0.0)
        ft_baseline_mean = baseline.get("flight_time_mean", {}).get("mean", ft_mean)
        ft_baseline_std_val = baseline.get("flight_time_mean", {}).get("std", 1.0)
        duress["flight_time_mean_deviation"] = abs(ft_mean - ft_baseline_mean) / (
            ft_baseline_std_val + 1e-6
        )

        # Typing speed z-score
        wpm = keystroke_features.get("typing_speed_wpm", 0.0)
        wpm_baseline = baseline.get("typing_speed_wpm", {}).get("mean", wpm)
        wpm_std = baseline.get("typing_speed_wpm", {}).get("std", 1.0)
        duress["typing_speed_z_score"] = abs(wpm - wpm_baseline) / (wpm_std + 1e-6)

        # Typing speed acceleration (rate of speed change)
        duress["typing_speed_acceleration"] = ctx.get("speed_acceleration", 0.0)

        # Error metrics (backspace frequency, bursts, rate vs baseline)
        duress["backspace_frequency"] = ctx.get("backspace_frequency", 0.0)
        duress["backspace_burst_count"] = ctx.get("backspace_burst_count", 0.0)
        baseline_error_rate = baseline.get("backspace_frequency", {}).get("mean", 0.05)
        duress["error_rate_vs_baseline"] = ctx.get("backspace_frequency", 0.0) / (
            baseline_error_rate + 1e-6
        )

        # Pause analysis
        duress["pause_frequency"] = ctx.get("pause_frequency", 0.0)
        duress["pause_duration_mean"] = ctx.get("pause_duration_mean", 0.0)
        duress["pause_before_confirm"] = ctx.get("pause_before_confirm", 0.0)

        # Rhythm and consistency
        rhythm = keystroke_features.get("rhythm_consistency", 0.0)
        rhythm_baseline = baseline.get("rhythm_consistency", {}).get("mean", rhythm)
        duress["inter_key_interval_cv"] = keystroke_features.get("flight_time_cv", 0.0)
        duress["key_pressure_variance"] = 1.0 - keystroke_features.get(
            "pressure_consistency", 0.8
        )
        duress["rhythm_breakdown_score"] = abs(rhythm - rhythm_baseline) / (
            rhythm_baseline + 1e-6
        )
        duress["digraph_timing_deviation"] = 1.0 - keystroke_features.get(
            "digraph_consistency", 0.5
        )

        # Error/correction patterns
        duress["deletion_retype_ratio"] = ctx.get("deletion_retype_ratio", 0.0)
        duress["capitalization_errors"] = ctx.get("capitalization_errors", 0.0)
        duress["typing_burst_irregularity"] = keystroke_features.get(
            "speed_variance", 0.0
        )
        duress["key_sequence_entropy"] = ctx.get("key_sequence_entropy", 3.0)

        # ── Mouse stress markers ────────────────────────────────────

        duress["mouse_tremor_score"] = ctx.get("mouse_tremor_score", 0.0)
        duress["mouse_jerk_mean"] = ctx.get("mouse_jerk_mean", 0.0)
        duress["mouse_jerk_std"] = ctx.get("mouse_jerk_std", 0.0)
        duress["cursor_overshoot_rate"] = ctx.get("cursor_overshoot_rate", 0.0)
        duress["click_hesitation_mean"] = ctx.get("click_hesitation_mean", 0.0)
        duress["double_click_rate"] = ctx.get("double_click_rate", 0.0)
        duress["scroll_jitter"] = ctx.get("scroll_jitter", 0.0)
        duress["movement_reversal_rate"] = ctx.get("movement_reversal_rate", 0.0)

        # Path efficiency drop
        eff = mouse_features.get("movement_efficiency", 0.8)
        eff_baseline = baseline.get("movement_efficiency", {}).get("mean", eff)
        duress["path_efficiency_drop"] = max(0, eff_baseline - eff)

        duress["velocity_spike_count"] = ctx.get("velocity_spike_count", 0.0)
        duress["acceleration_irregularity"] = mouse_features.get(
            "acceleration_std", 0.0
        )
        duress["idle_periods_in_motion"] = ctx.get("idle_periods_in_motion", 0.0)
        duress["click_pressure_variance"] = mouse_features.get(
            "click_duration_std", 0.0
        )
        duress["drag_tremor_score"] = ctx.get("drag_tremor_score", 0.0)
        duress["hover_instability"] = ctx.get("hover_instability", 0.0)

        # ── Cognitive load & session indicators ─────────────────────

        duress["decision_time_increase"] = ctx.get("decision_time_increase", 0.0)
        duress["field_navigation_errors"] = ctx.get("field_navigation_errors", 0.0)
        duress["form_completion_time_ratio"] = ctx.get(
            "form_completion_time_ratio", 1.0
        )
        duress["transaction_amount_hesitation"] = ctx.get(
            "transaction_amount_hesitation", 0.0
        )
        duress["beneficiary_entry_pattern"] = ctx.get("beneficiary_entry_pattern", 0.0)
        duress["session_duration_anomaly"] = ctx.get("session_duration_anomaly", 0.0)
        duress["time_of_day_risk"] = self._compute_time_risk()
        duress["concurrent_session_flag"] = float(ctx.get("concurrent_sessions", 0) > 1)

        # ── Advanced stress markers ─────────────────────────────────

        # Modifier overlap instability (erratic shift usage under stress)
        mod_std = keystroke_features.get("modifier_overlap_std", 0.0)
        mod_mean = keystroke_features.get("modifier_overlap_mean", 0.0)
        baseline_mod_std = baseline.get("modifier_overlap_std", {}).get("mean", mod_std)
        duress["modifier_overlap_instability"] = (
            abs(mod_std - baseline_mod_std) / (baseline_mod_std + 1e-6)
        )

        # Digraph rhythm deviation (specific key-pair timing breaks down under stress)
        digraph_devs = []
        for key, val in keystroke_features.items():
            if key.startswith("digraph_") and key.endswith("_mean"):
                bval = baseline.get(key, {}).get("mean", val)
                if bval > 0:
                    digraph_devs.append(abs(val - bval) / (bval + 1e-6))
        duress["digraph_rhythm_deviation"] = (
            float(np.mean(digraph_devs)) if digraph_devs else 0.0
        )

        # Flight time CV spike (sudden timing variability increase)
        flight_cv = keystroke_features.get("flight_time_cv", 0.0)
        baseline_cv = baseline.get("flight_time_cv", {}).get("mean", flight_cv)
        duress["flight_cv_spike"] = max(0, flight_cv - baseline_cv) / (
            baseline_cv + 1e-6
        )

        # Correction burst density (backspace clusters per minute)
        duress["correction_burst_density"] = ctx.get("correction_burst_density", 0.0)

        # Inter-field hesitation ratio
        duress["inter_field_hesitation_ratio"] = ctx.get(
            "inter_field_hesitation_ratio", 0.0
        )

        return duress

    def compute_duress_score(
        self,
        user_id: int,
        keystroke_features: Dict,
        mouse_features: Dict,
        session_context: Optional[Dict] = None,
    ) -> Dict:
        """Compute composite duress score for a session.

        Returns:
            Dict with duress_score, alert_level, top contributing features,
            and recommended actions.
        """
        features = self.extract_duress_features(
            user_id, keystroke_features, mouse_features, session_context
        )

        if self.is_trained:
            # Use trained Gradient Boosting model
            feature_vector = np.array(
                [features.get(f, 0.0) for f in DURESS_FEATURES]
            ).reshape(1, -1)
            feature_vector = self.scaler.transform(feature_vector)
            duress_probability = float(self.model.predict_proba(feature_vector)[0][1])
        else:
            # Heuristic scoring when model isn't trained yet
            duress_probability = self._heuristic_duress_score(features)

        # Determine alert level
        if duress_probability >= self.alert_threshold:
            alert_level = "critical"
            action = "silent_soc_alert"
        elif duress_probability >= self.monitor_threshold:
            alert_level = "elevated"
            action = "enhanced_monitoring"
        else:
            alert_level = "normal"
            action = "standard_monitoring"

        # Get top contributing stress features
        top_features = sorted(features.items(), key=lambda x: abs(x[1]), reverse=True)[
            :5
        ]

        return {
            "duress_score": round(duress_probability, 4),
            "alert_level": alert_level,
            "action": action,
            "top_stress_features": [
                {"feature": name, "value": round(float(val), 4)}
                for name, val in top_features
            ],
            "feature_count": len(features),
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
        }

    def train(self, normal_features: List[Dict], duress_features: List[Dict]):
        """Train the Gradient Boosting duress detector.

        Args:
            normal_features: List of duress feature dicts from normal sessions
            duress_features: List of duress feature dicts from simulated duress
        """
        if len(normal_features) < 5 or len(duress_features) < 5:
            logger.warning("Insufficient training data for duress detector")
            return {"error": "Insufficient training data"}

        # Convert to feature matrices
        X_normal = np.array(
            [[f.get(feat, 0.0) for feat in DURESS_FEATURES] for f in normal_features]
        )
        X_duress = np.array(
            [[f.get(feat, 0.0) for feat in DURESS_FEATURES] for f in duress_features]
        )

        X = np.vstack([X_normal, X_duress])
        y = np.concatenate([np.zeros(len(X_normal)), np.ones(len(X_duress))])

        # Scale features
        X = self.scaler.fit_transform(X)

        # Train
        self.model.fit(X, y)
        self.is_trained = True

        # Compute training metrics
        predictions = self.model.predict(X)
        accuracy = float(np.mean(predictions == y))

        # Feature importance
        importance = dict(zip(DURESS_FEATURES, self.model.feature_importances_))
        top_important = sorted(importance.items(), key=lambda x: x[1], reverse=True)[
            :10
        ]

        logger.info(f"Duress detector trained. Accuracy: {accuracy:.3f}")
        return {
            "accuracy": accuracy,
            "training_samples": len(X),
            "top_features": [
                {"feature": name, "importance": round(float(imp), 4)}
                for name, imp in top_important
            ],
        }

    def _heuristic_duress_score(self, features: Dict) -> float:
        """Rule-based duress scoring when ML model isn't trained yet."""
        score = 0.0
        indicators = 0

        # Typing speed deviation > 3σ
        if features.get("typing_speed_z_score", 0) > 3.0:
            score += 0.20
            indicators += 1

        # High hold time jitter
        if features.get("hold_time_jitter", 0) > 2.0:
            score += 0.15
            indicators += 1

        # Rhythm breakdown
        if features.get("rhythm_breakdown_score", 0) > 0.5:
            score += 0.15
            indicators += 1

        # Error rate spike (>4× baseline)
        if features.get("error_rate_vs_baseline", 0) > 4.0:
            score += 0.15
            indicators += 1

        # Mouse tremor
        if features.get("mouse_tremor_score", 0) > 0.5:
            score += 0.10
            indicators += 1

        # Pause before confirmation
        if features.get("pause_before_confirm", 0) > 5000:  # >5 seconds
            score += 0.10
            indicators += 1

        # Decision time increase
        if features.get("decision_time_increase", 0) > 2.0:
            score += 0.08
            indicators += 1

        # Path efficiency drop
        if features.get("path_efficiency_drop", 0) > 0.3:
            score += 0.07
            indicators += 1

        # Modifier overlap instability (unique duress signal)
        if features.get("modifier_overlap_instability", 0) > 2.0:
            score += 0.12
            indicators += 1

        # Digraph rhythm breakdown under stress
        if features.get("digraph_rhythm_deviation", 0) > 1.5:
            score += 0.10
            indicators += 1

        # Flight time CV spike (sudden variability)
        if features.get("flight_cv_spike", 0) > 2.0:
            score += 0.08
            indicators += 1

        # Correction burst density (frantic backspacing)
        if features.get("correction_burst_density", 0) > 5.0:
            score += 0.08
            indicators += 1

        # Multi-indicator amplification: 5+ indicators = duress likely
        if indicators >= 5:
            score *= 1.25

        return min(score, 1.0)

    def _compute_time_risk(self) -> float:
        """Compute risk based on time of day. Unusual hours = higher risk."""
        hour = datetime.now().hour
        if 0 <= hour < 6:  # Midnight to 6 AM
            return 0.8
        elif 6 <= hour < 9:  # Early morning
            return 0.3
        elif 9 <= hour < 18:  # Business hours
            return 0.1
        elif 18 <= hour < 22:  # Evening
            return 0.2
        else:  # Late night
            return 0.6

    def save(self, filepath: str):
        """Save duress detector state."""
        joblib.dump(
            {
                "model": self.model,
                "scaler": self.scaler,
                "is_trained": self.is_trained,
                "baseline_profiles": self.baseline_profiles,
                "alert_threshold": self.alert_threshold,
                "monitor_threshold": self.monitor_threshold,
            },
            f"{filepath}_duress.pkl",
        )

    def load(self, filepath: str) -> bool:
        """Load duress detector state."""
        try:
            data = joblib.load(f"{filepath}_duress.pkl")
            self.model = data["model"]
            self.scaler = data["scaler"]
            self.is_trained = data["is_trained"]
            self.baseline_profiles = data.get("baseline_profiles", {})
            self.alert_threshold = data.get("alert_threshold", 0.75)
            self.monitor_threshold = data.get("monitor_threshold", 0.50)
            return True
        except Exception:
            logger.exception("Failed to load duress detector from %s", filepath)
            return False
