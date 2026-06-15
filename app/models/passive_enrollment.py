"""
Passive Enrollment Manager — BioCatch-Style Silent Profile Building.

Replaces explicit calibration with passive enrollment that builds
behavioral profiles from normal user sessions. Users never see a
calibration page — the system silently collects data during login
and regular usage until enough data exists to authenticate.

BioCatch approach:
  - First 2–6 sessions: silent enrollment (no alerts triggered)
  - Session 7+: live comparison against profile
  - Zero user friction, zero awareness

Our implementation:
  - Sessions 1–N (configurable, default 5): passive enrollment
  - Session N+1: live behavioral authentication begins
  - Profile built from login keystroke dynamics + in-session behavior
  - Exponential moving average for profile updates
"""

from __future__ import annotations

import logging
import math
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Features used for passive enrollment profile building
ENROLLMENT_FEATURES = [
    # Keystroke (most distinctive during login)
    "hold_time_mean",
    "hold_time_std",
    "hold_time_median",
    "flight_time_mean",
    "flight_time_std",
    "flight_time_median",
    "typing_speed_wpm",
    "typing_speed_cpm",
    "rhythm_consistency",
    "burst_ratio",
    "pause_ratio",
    "digraph_consistency",
    "hold_time_cv",
    "flight_time_cv",
    # Mouse (collected during session)
    "velocity_mean",
    "velocity_std",
    "velocity_median",
    "acceleration_mean",
    "curvature_mean",
    "click_duration_mean",
    "avg_direction_change",
    "movement_efficiency",
    "dwell_time_mean",
    "velocity_smoothness",
    # Extended (from behavioral_feature_engine)
    "key_hold_mean",
    "key_hold_std",
    "flight_time_mean",
    "typing_speed_wpm",
    "rhythm_consistency",
    "mouse_vel_mean",
    "mouse_vel_std",
    "trajectory_curvature",
    "micro_jitter_amp",
    "dir_change_freq",
    "click_dur_mean",
    "modifier_overlap_mean",
    "modifier_overlap_std",
    "modifier_overlap_count",
]


class PassiveEnrollmentManager:
    """Manages passive behavioral enrollment without explicit calibration.

    Usage flow:
        1. User registers normally (no calibration step)
        2. Each login captures keystroke dynamics from username/password fields
        3. Each session captures mouse/navigation behavior
        4. After ``min_sessions`` sessions, user is marked as enrolled
        5. From that point, behavioral authentication is active

    The manager maintains:
        - Per-user session count
        - Per-user feature profiles (mean + std per feature)
        - Enrollment status
        - Profile confidence score (0.0–1.0)
    """

    DEFAULT_MIN_SESSIONS = 5
    DEFAULT_MIN_SAMPLES_PER_SESSION = 10
    PROFILE_UPDATE_ALPHA = 0.2  # EMA learning rate

    def __init__(
        self,
        min_sessions: int = DEFAULT_MIN_SESSIONS,
        min_samples_per_session: int = DEFAULT_MIN_SAMPLES_PER_SESSION,
    ):
        self.min_sessions = min_sessions
        self.min_samples = min_samples_per_session
        self._profiles_mem: Dict[int, Dict[str, Any]] = {}
        self._session_counts_mem: Dict[int, int] = {}
        self._enrollment_status_mem: Dict[int, bool] = {}

    def _get_redis(self):
        try:
            from flask import has_app_context
            if not has_app_context():
                return None
            from app.extensions import get_redis
            return get_redis()
        except Exception:
            return None

    def _load_state(self, user_id: int):
        rc = self._get_redis()
        if rc:
            import json
            try:
                state_str = rc.get(f"passive_enrollment:{user_id}")
                if state_str:
                    state = json.loads(state_str)
                    self._profiles_mem[user_id] = state.get("profile", {})
                    self._session_counts_mem[user_id] = state.get("sessions", 0)
                    self._enrollment_status_mem[user_id] = state.get("enrolled", False)
            except Exception as e:
                logger.error("Failed to load passive enrollment state: %s", e)

    def _save_state(self, user_id: int):
        rc = self._get_redis()
        if rc:
            import json
            try:
                state = {
                    "profile": self._profiles_mem.get(user_id, {}),
                    "sessions": self._session_counts_mem.get(user_id, 0),
                    "enrolled": self._enrollment_status_mem.get(user_id, False)
                }
                rc.set(f"passive_enrollment:{user_id}", json.dumps(state))
            except Exception as e:
                logger.error("Failed to save passive enrollment state: %s", e)

    def get_enrollment_status(self, user_id: int) -> Dict[str, Any]:
        """Check enrollment status for a user."""
        self._load_state(user_id)
        sessions = self._session_counts_mem.get(user_id, 0)
        enrolled = self._enrollment_status_mem.get(user_id, False)
        profile = self._profiles_mem.get(user_id, {})
        confidence = profile.get("confidence", 0.0)

        if enrolled:
            phase = "active"
        elif sessions >= self.min_sessions:
            phase = "ready"
        else:
            phase = "collecting"

        return {
            "enrolled": enrolled,
            "sessions_completed": sessions,
            "sessions_required": self.min_sessions,
            "profile_confidence": round(confidence, 4),
            "enrollment_phase": phase,
        }

    def ingest_session_data(
        self,
        user_id: int,
        keystroke_features: Optional[Dict[str, float]] = None,
        mouse_features: Optional[Dict[str, float]] = None,
        extended_features: Optional[Dict[str, float]] = None,
        session_context: Optional[Dict[str, Any]] = None,
        source: str = "session",
    ) -> Dict[str, Any]:
        """Ingest behavioral data from a session for enrollment or profile update.

        Called at the end of each session (or periodically during a session).
        During enrollment phase: accumulates data to build profile.
        After enrollment: updates profile via EMA and returns match score.

        Args:
            user_id: The user whose profile to update.
            keystroke_features: Keystroke timing features from this session.
            mouse_features: Mouse dynamics features from this session.
            extended_features: Extended 200+ features from behavioral engine.
            source: "login" for login-time data, "session" for in-session data.

        Returns:
            {
                "action": str,  # "collecting"|"enrolled"|"matched"|"anomaly"
                "match_score": float,  # 0.0–1.0 (only after enrollment)
                "profile_confidence": float,
                "sessions_completed": int,
                "message": str,
            }
        """
        # Merge all feature sources into a unified feature dict
        features = {}
        if keystroke_features:
            features.update(keystroke_features)
        if mouse_features:
            features.update(mouse_features)
        if extended_features:
            features.update(extended_features)

        if not features:
            return {
                "action": "no_data",
                "match_score": 0.0,
                "profile_confidence": 0.0,
                "sessions_completed": self._session_counts_mem.get(user_id, 0),
                "message": "No behavioral features provided",
            }

        # Filter to only known enrollment features
        filtered = {
            k: float(v)
            for k, v in features.items()
            if k in ENROLLMENT_FEATURES
            and isinstance(v, (int, float))
            and not (math.isnan(v) or math.isinf(v))
            and v != 0.0  # Skip zero-value features (no data)
        }

        if len(filtered) < 3:
            return {
                "action": "insufficient_data",
                "match_score": 0.0,
                "profile_confidence": 0.0,
                "sessions_completed": self._session_counts_mem.get(user_id, 0),
                "message": f"Only {len(filtered)} valid features (need ≥3)",
            }

        self._load_state(user_id)
        enrolled = self._enrollment_status_mem.get(user_id, False)

        if not enrolled:
            # ── Enrollment phase: accumulate data ──
            result = self._process_enrollment(user_id, filtered, source)
        else:
            # ── Post-enrollment: compare + update ──
            result = self._process_authenticated(user_id, filtered, source, session_context)
            
        self._save_state(user_id)
        return result

    def _process_enrollment(
        self, user_id: int, features: Dict[str, float], source: str
    ) -> Dict[str, Any]:
        """Process data during the enrollment phase."""
        if user_id not in self._profiles_mem:
            self._profiles_mem[user_id] = {
                "samples": [],
                "feature_stats": {},
                "confidence": 0.0,
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
            }

        profile = self._profiles_mem[user_id]
        profile["samples"].append(features)

        # Keep last 50 samples max
        if len(profile["samples"]) > 50:
            profile["samples"] = profile["samples"][-50:]

        # Increment session count (only for session-end submissions)
        if source in ("login", "session", "registration"):
            self._session_counts_mem[user_id] = self._session_counts_mem.get(user_id, 0) + 1

        sessions = self._session_counts_mem.get(user_id, 0)

        # Check if we have enough data to enroll
        if (
            sessions >= self.min_sessions
            and len(profile["samples"]) >= self.min_sessions
        ):
            self._build_profile(user_id)
            self._enrollment_status_mem[user_id] = True
            confidence = profile.get("confidence", 0.0)

            logger.info(
                "User %d passively enrolled after %d sessions "
                "(confidence: %.2f, features: %d)",
                user_id,
                sessions,
                confidence,
                len(profile["feature_stats"]),
            )

            return {
                "action": "enrolled",
                "match_score": 1.0,
                "profile_confidence": confidence,
                "sessions_completed": sessions,
                "message": (
                    f"Passive enrollment complete after {sessions} sessions. "
                    f"Behavioral authentication is now active."
                ),
            }

        # Still collecting
        confidence = min(1.0, sessions / self.min_sessions)
        profile["confidence"] = confidence

        return {
            "action": "collecting",
            "match_score": 0.0,
            "profile_confidence": confidence,
            "sessions_completed": sessions,
            "message": (
                f"Session {sessions}/{self.min_sessions} recorded. "
                f"{self.min_sessions - sessions} more sessions needed for enrollment."
            ),
        }

    def _process_authenticated(
        self, user_id: int, features: Dict[str, float], source: str, session_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Process data after enrollment — compare against profile."""
        profile = self._profiles_mem.get(user_id, {})
        stats = profile.get("feature_stats", {})

        if not stats:
            return {
                "action": "no_profile",
                "match_score": 0.5,
                "profile_confidence": 0.0,
                "sessions_completed": self._session_counts_mem.get(user_id, 0),
                "message": "Profile exists but has no statistics",
            }

        # Context-aware adjustments
        context_penalty = 0.0
        if session_context:
            if session_context.get("is_new_device"):
                context_penalty += 0.2
            if session_context.get("is_new_ip"):
                context_penalty += 0.1

        # Compute match score via Mahalanobis-style distance
        match_score = self._compute_match_score(features, stats)
        match_score = max(0.0, match_score - context_penalty)

        # Update profile with new data (EMA)
        self._update_profile_ema(user_id, features, context_penalty)

        # Determine action
        if match_score >= 0.7:
            action = "matched"
            message = f"Behavioral match: {match_score:.2f}"
        elif match_score >= 0.4:
            action = "weak_match"
            message = f"Weak behavioral match: {match_score:.2f} — monitoring"
        else:
            action = "anomaly"
            message = f"Behavioral anomaly detected: {match_score:.2f}"

        return {
            "action": action,
            "match_score": round(match_score, 4),
            "profile_confidence": profile.get("confidence", 0.0),
            "sessions_completed": self._session_counts_mem.get(user_id, 0),
            "message": message,
        }

    def _build_profile(self, user_id: int):
        """Build statistical profile from accumulated samples."""
        profile = self._profiles_mem.get(user_id, {})
        samples = profile.get("samples", [])

        if len(samples) < 2:
            return

        # Collect all feature keys seen across samples
        all_keys = set()
        for sample in samples:
            all_keys.update(sample.keys())

        stats: Dict[str, Dict[str, float]] = {}
        feature_count = 0

        for key in all_keys:
            values = [
                s[key]
                for s in samples
                if key in s
                and isinstance(s[key], (int, float))
                and not math.isnan(s[key])
                and not math.isinf(s[key])
            ]

            if len(values) >= 2:
                arr = np.array(values, dtype=np.float64)
                # Remove outliers (beyond 2.5 sigma)
                mean = np.mean(arr)
                std = np.std(arr)
                if std > 0:
                    mask = np.abs(arr - mean) <= 2.5 * std
                    arr = arr[mask]
                    if len(arr) < 2:
                        arr = np.array(values, dtype=np.float64)

                stats[key] = {
                    "mean": float(np.mean(arr)),
                    "std": max(float(np.std(arr)), 1e-6),  # Avoid division by zero
                    "median": float(np.median(arr)),
                    "min": float(np.min(arr)),
                    "max": float(np.max(arr)),
                    "count": len(arr),
                }
                feature_count += 1

        profile["feature_stats"] = stats
        profile["confidence"] = min(
            1.0, feature_count / 15
        )  # ~15 features = full confidence
        profile["last_updated"] = datetime.now().isoformat()

        logger.info(
            "Built passive enrollment profile for user %d: %d features, confidence %.2f",
            user_id,
            feature_count,
            profile["confidence"],
        )

    def _compute_match_score(
        self, features: Dict[str, float], stats: Dict[str, Dict[str, float]]
    ) -> float:
        """Compute how well current features match the stored profile.

        Uses normalized z-score distance: lower distance = better match.
        """
        z_scores = []

        for key, value in features.items():
            if key in stats:
                s = stats[key]
                mean = s["mean"]
                std = s["std"]
                if std > 0:
                    z = abs(value - mean) / std
                    z_scores.append(z)

        if not z_scores:
            return 0.5  # No overlap — uncertain

        # Mean z-score → match probability
        mean_z = np.mean(z_scores)

        # Convert z-score to 0–1 match (z=0 → 1.0, z=3 → ~0.0)
        # Using sigmoid-like mapping
        match = 1.0 / (1.0 + (mean_z / 2.0) ** 2)

        return float(match)

    def _update_profile_ema(self, user_id: int, features: Dict[str, float], context_penalty: float = 0.0):
        """Update profile statistics using exponential moving average."""
        profile = self._profiles_mem.get(user_id, {})
        stats = profile.get("feature_stats", {})
        sessions = self._session_counts_mem.get(user_id, 0)
        
        # Dynamic alpha: higher for early sessions, lower as profile matures.
        # Reduce alpha if device context is new (context_penalty > 0)
        base_alpha = max(0.1, 0.5 - (sessions * 0.05))
        alpha = max(0.01, base_alpha - (context_penalty * 0.5))

        for key, value in features.items():
            if key in stats:
                s = stats[key]
                old_mean = s["mean"]
                old_std = s["std"]

                # EMA update for mean
                new_mean = old_mean * (1 - alpha) + value * alpha

                # EMA update for std (approximate)
                deviation = abs(value - new_mean)
                new_std = old_std * (1 - alpha) + deviation * alpha
                new_std = max(new_std, 1e-6)

                s["mean"] = new_mean
                s["std"] = new_std
                s["count"] = s.get("count", 1) + 1
            else:
                # New feature — add it
                stats[key] = {
                    "mean": value,
                    "std": abs(value * 0.1) + 1e-6,
                    "median": value,
                    "min": value,
                    "max": value,
                    "count": 1,
                }

        profile["last_updated"] = datetime.now().isoformat()

    def reset_enrollment(self, user_id: int):
        """Reset enrollment for a user (e.g., after account recovery)."""
        self._profiles_mem.pop(user_id, None)
        self._session_counts_mem.pop(user_id, None)
        self._enrollment_status_mem.pop(user_id, None)
        self._save_state(user_id)
        logger.info("Enrollment reset for user %d", user_id)

    def get_profile_summary(self, user_id: int) -> Dict[str, Any]:
        """Get a summary of the user's behavioral profile."""
        self._load_state(user_id)
        profile = self._profiles_mem.get(user_id, {})
        stats = profile.get("feature_stats", {})
        status = self.get_enrollment_status(user_id)

        top_features = sorted(
            stats.items(),
            key=lambda x: x[1].get("count", 0),
            reverse=True,
        )[:10]

        return {
            **status,
            "feature_count": len(stats),
            "total_samples": len(profile.get("samples", [])),
            "created_at": profile.get("created_at", ""),
            "last_updated": profile.get("last_updated", ""),
            "top_features": [
                {
                    "name": name,
                    "mean": round(s["mean"], 4),
                    "std": round(s["std"], 4),
                    "samples": s.get("count", 0),
                }
                for name, s in top_features
            ],
        }

    # ── Bayesian Per-Key/Digraph Profile System ───────────────────────────────

    def _load_digraph_state(self, user_id: int) -> Dict[str, Any]:
        """Load the per-key/digraph Bayesian profile from Redis or memory."""
        if not hasattr(self, "_digraph_profiles_mem"):
            self._digraph_profiles_mem: Dict[int, Dict[str, Any]] = {}

        rc = self._get_redis()
        if rc:
            import json
            try:
                state_str = rc.get(f"digraph_profile:{user_id}")
                if state_str:
                    self._digraph_profiles_mem[user_id] = json.loads(state_str)
            except Exception as e:
                logger.error("Failed to load digraph profile: %s", e)

        return self._digraph_profiles_mem.get(user_id, {})

    def _save_digraph_state(self, user_id: int, profile: Dict[str, Any]):
        """Persist the per-key/digraph Bayesian profile."""
        if not hasattr(self, "_digraph_profiles_mem"):
            self._digraph_profiles_mem = {}

        self._digraph_profiles_mem[user_id] = profile

        rc = self._get_redis()
        if rc:
            import json
            try:
                rc.set(f"digraph_profile:{user_id}", json.dumps(profile))
            except Exception as e:
                logger.error("Failed to save digraph profile: %s", e)

    @staticmethod
    def _bayesian_update(
        prior_mean: float,
        prior_std: float,
        observed_value: float,
        observation_noise: float,
    ) -> tuple:
        """Normal-Normal conjugate Bayesian update.

        Given a prior N(prior_mean, prior_std²) and an observation from
        N(observed_value, observation_noise²), compute the posterior.

        The posterior precision is the sum of prior and likelihood precisions:
            τ_post = τ_prior + τ_obs
            μ_post = (μ_prior · τ_prior + x · τ_obs) / τ_post
            σ_post = 1 / √τ_post

        This naturally handles:
          - Wide priors (signup): fast learning, σ shrinks quickly
          - Narrow posteriors (many logins): stable, resistant to noise
          - Single outlier sessions don't corrupt the profile
        """
        prior_var = max(prior_std ** 2, 1e-6)
        obs_var = max(observation_noise ** 2, 1e-6)

        prior_precision = 1.0 / prior_var
        obs_precision = 1.0 / obs_var

        post_precision = prior_precision + obs_precision
        post_mean = (prior_mean * prior_precision + observed_value * obs_precision) / post_precision
        post_std = math.sqrt(1.0 / post_precision)

        # Floor the std to prevent collapse to zero
        post_std = max(post_std, 1.0)

        return round(post_mean, 3), round(post_std, 3)

    def ingest_digraph_profile(
        self,
        user_id: int,
        digraph_profile: Dict[str, Any],
        source: str = "login",
    ) -> Dict[str, Any]:
        """Ingest a per-key/digraph profile and update via Bayesian posterior.

        During enrollment (first login): initializes the prior from the data.
        After enrollment: performs conjugate Normal-Normal updates.

        Args:
            user_id: The user to update.
            digraph_profile: Output of DigraphProfileExtractor.extract_profile().
            source: "signup" for Session 0, "login" for subsequent logins.

        Returns:
            {
                "action": "initialized"|"updated"|"matched"|"anomaly",
                "match_score": float (0-1),
                "per_key_count": int,
                "per_digraph_count": int,
                "confidence": float (0-1),
                "updates_count": int,
            }
        """
        stored = self._load_digraph_state(user_id)
        incoming_keys = digraph_profile.get("per_key_hold", {})
        incoming_digraphs = digraph_profile.get("per_digraph_flight", {})
        incoming_aggregate = digraph_profile.get("aggregate", {})

        if not incoming_keys and not incoming_digraphs:
            return {
                "action": "no_data",
                "match_score": 0.0,
                "per_key_count": 0,
                "per_digraph_count": 0,
                "confidence": 0.0,
                "updates_count": stored.get("updates_count", 0),
            }

        if not stored or not stored.get("per_key_hold"):
            # ── First time: initialize prior ──────────────────────────────
            # Use wide priors (std = 50% of mean) to express high uncertainty
            initialized = {
                "per_key_hold": {},
                "per_digraph_flight": {},
                "aggregate": {},
                "updates_count": 1,
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
            }

            for key, stats in incoming_keys.items():
                mean = stats["mean"]
                # Wide prior: std is 50% of mean (high uncertainty)
                std = max(stats.get("std", mean * 0.5), mean * 0.3)
                initialized["per_key_hold"][key] = {
                    "mean": round(mean, 3),
                    "std": round(max(std, 5.0), 3),  # Floor at 5ms
                    "count": stats.get("count", 1),
                }

            for key, stats in incoming_digraphs.items():
                mean = stats["mean"]
                std = max(stats.get("std", mean * 0.5), mean * 0.3)
                initialized["per_digraph_flight"][key] = {
                    "mean": round(mean, 3),
                    "std": round(max(std, 5.0), 3),
                    "count": stats.get("count", 1),
                }

            # Store aggregate features
            initialized["aggregate"] = incoming_aggregate

            self._save_digraph_state(user_id, initialized)

            logger.info(
                "Digraph profile initialized for user %d: %d keys, %d digraphs (source=%s)",
                user_id,
                len(initialized["per_key_hold"]),
                len(initialized["per_digraph_flight"]),
                source,
            )

            return {
                "action": "initialized",
                "match_score": 1.0,
                "per_key_count": len(initialized["per_key_hold"]),
                "per_digraph_count": len(initialized["per_digraph_flight"]),
                "confidence": 0.2,  # Low confidence — only one session
                "updates_count": 1,
            }

        # ── Subsequent sessions: Bayesian update + match scoring ──────────
        match_score = self._compute_digraph_match_score(stored, digraph_profile)

        # Observation noise: use the incoming session's std, floored
        # If the user is typing consistently this session, noise is low
        # If they're typing erratically, noise is high (less weight)
        updates_count = stored.get("updates_count", 1) + 1

        # Update per-key hold times
        for key, stats in incoming_keys.items():
            obs_mean = stats["mean"]
            obs_noise = max(stats.get("std", 20.0), 5.0)

            if key in stored["per_key_hold"]:
                prior = stored["per_key_hold"][key]
                new_mean, new_std = self._bayesian_update(
                    prior["mean"], prior["std"], obs_mean, obs_noise
                )
                stored["per_key_hold"][key] = {
                    "mean": new_mean,
                    "std": new_std,
                    "count": prior.get("count", 1) + stats.get("count", 1),
                }
            else:
                # New key not seen before — add with wide prior
                stored["per_key_hold"][key] = {
                    "mean": round(obs_mean, 3),
                    "std": round(max(obs_noise, obs_mean * 0.3, 5.0), 3),
                    "count": stats.get("count", 1),
                }

        # Update per-digraph flight times
        for key, stats in incoming_digraphs.items():
            obs_mean = stats["mean"]
            obs_noise = max(stats.get("std", 30.0), 5.0)

            if key in stored["per_digraph_flight"]:
                prior = stored["per_digraph_flight"][key]
                new_mean, new_std = self._bayesian_update(
                    prior["mean"], prior["std"], obs_mean, obs_noise
                )
                stored["per_digraph_flight"][key] = {
                    "mean": new_mean,
                    "std": new_std,
                    "count": prior.get("count", 1) + stats.get("count", 1),
                }
            else:
                stored["per_digraph_flight"][key] = {
                    "mean": round(obs_mean, 3),
                    "std": round(max(obs_noise, obs_mean * 0.3, 5.0), 3),
                    "count": stats.get("count", 1),
                }

        # Update aggregate features via EMA
        if incoming_aggregate:
            old_agg = stored.get("aggregate", {})
            alpha = max(0.1, 0.5 / math.sqrt(updates_count))
            for key, value in incoming_aggregate.items():
                if isinstance(value, (int, float)) and not math.isnan(value):
                    old_val = old_agg.get(key, value)
                    old_agg[key] = round(old_val * (1 - alpha) + value * alpha, 4)
            stored["aggregate"] = old_agg

        stored["updates_count"] = updates_count
        stored["last_updated"] = datetime.now().isoformat()
        self._save_digraph_state(user_id, stored)

        # Confidence grows with more updates and more keys
        n_keys = len(stored["per_key_hold"])
        n_digraphs = len(stored["per_digraph_flight"])
        confidence = min(1.0, (updates_count / 5.0) * 0.5 + (n_keys / 20.0) * 0.3 + (n_digraphs / 30.0) * 0.2)

        # Determine action based on match score
        if match_score >= 0.7:
            action = "matched"
        elif match_score >= 0.4:
            action = "weak_match"
        else:
            action = "anomaly"

        logger.info(
            "Digraph profile updated for user %d: score=%.3f, keys=%d, "
            "digraphs=%d, updates=%d, confidence=%.3f (source=%s)",
            user_id, match_score, n_keys, n_digraphs, updates_count, confidence, source,
        )

        return {
            "action": action,
            "match_score": round(match_score, 4),
            "per_key_count": n_keys,
            "per_digraph_count": n_digraphs,
            "confidence": round(confidence, 4),
            "updates_count": updates_count,
        }

    def _compute_digraph_match_score(
        self,
        stored: Dict[str, Any],
        incoming: Dict[str, Any],
    ) -> float:
        """Compute match score between stored profile and incoming keystrokes.

        Uses z-score distance: how many standard deviations is the incoming
        value from the stored mean? Lower z = better match.

        Weights per-key hold (40%) and per-digraph flight (60%) since
        digraph transitions are more discriminative (Killourhy & Maxion, 2009).
        """
        key_z_scores: List[float] = []
        digraph_z_scores: List[float] = []

        # Per-key hold time comparison
        for key, stats in incoming.get("per_key_hold", {}).items():
            if key in stored.get("per_key_hold", {}):
                prior = stored["per_key_hold"][key]
                z = abs(stats["mean"] - prior["mean"]) / max(prior["std"], 1.0)
                key_z_scores.append(z)

        # Per-digraph flight time comparison
        for key, stats in incoming.get("per_digraph_flight", {}).items():
            if key in stored.get("per_digraph_flight", {}):
                prior = stored["per_digraph_flight"][key]
                z = abs(stats["mean"] - prior["mean"]) / max(prior["std"], 1.0)
                digraph_z_scores.append(z)

        if not key_z_scores and not digraph_z_scores:
            return 0.5  # No overlap — can't determine match

        # Weighted combination (digraphs are more discriminative)
        key_score = 0.5
        if key_z_scores:
            mean_z_key = np.mean(key_z_scores)
            key_score = float(1.0 / (1.0 + (mean_z_key / 2.0) ** 2))

        digraph_score = 0.5
        if digraph_z_scores:
            mean_z_digraph = np.mean(digraph_z_scores)
            digraph_score = float(1.0 / (1.0 + (mean_z_digraph / 2.0) ** 2))

        # Weighted average: 40% key hold, 60% digraph flight
        if key_z_scores and digraph_z_scores:
            score = 0.4 * key_score + 0.6 * digraph_score
        elif digraph_z_scores:
            score = digraph_score
        else:
            score = key_score

        return float(score)


# ── Singleton ──────────────────────────────────────────────────────────────────
_enrollment_manager: PassiveEnrollmentManager | None = None


def get_enrollment_manager() -> PassiveEnrollmentManager:
    global _enrollment_manager
    if _enrollment_manager is None:
        _enrollment_manager = PassiveEnrollmentManager()
    return _enrollment_manager

