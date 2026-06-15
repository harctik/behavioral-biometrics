"""
Synthetic Behavioral Biometrics Data Generator — Research-grade simulation.

Generates realistic behavioral feature vectors that mimic real user typing,
mouse movement, and cognitive patterns. Each simulated user has a unique
"behavioral fingerprint" sampled from plausible physiological distributions.

This is standard practice in behavioral biometrics research (BioCatch, TypingDNA,
BehavioSec all use synthetic bootstrapping before real enrollment data arrives).

Usage:
    from app.synthetic_data_generator import SyntheticDataGenerator
    gen = SyntheticDataGenerator(seed=42)
    users = gen.generate_dataset(n_users=10, samples_per_user=200)
    # users[0]["genuine"] → 200 feature dicts (the user's normal behavior)
    # users[0]["impostor"] → 200 feature dicts (other users trying to mimic)
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class UserProfile:
    """A simulated user's unique behavioral fingerprint.

    Each user has characteristic ranges for timing, pressure, mouse dynamics,
    etc., sampled from real-world distributions observed in keystroke dynamics
    research (Killourhy & Maxion, CMU 2009; Antal & Nemes, 2016).
    """

    def __init__(self, user_id: int, rng: np.random.Generator):
        self.user_id = user_id

        # ── Keystroke Dynamics (timing in milliseconds) ───────────────────
        # Key hold time: most people 80-150ms, some outliers 50-250ms
        self.key_hold_mean = rng.normal(115, 25)
        self.key_hold_std = rng.uniform(15, 40)

        # Flight time (inter-key interval): 80-250ms typical
        self.flight_time_mean = rng.normal(150, 40)
        self.flight_time_std = rng.uniform(20, 60)

        # Typing speed: 30-90 WPM for most users
        self.typing_speed_wpm = rng.normal(55, 15)

        # Rhythm consistency: how stable is timing across sessions (0-1)
        self.rhythm_consistency = rng.beta(5, 2)  # Skewed toward consistent

        # Error rate: 0.01 - 0.15
        self.error_rate = rng.beta(2, 15)

        # ── Mouse Dynamics ────────────────────────────────────────────────
        # Mouse velocity: pixels/ms
        self.mouse_vel_mean = rng.normal(0.8, 0.3)
        self.mouse_vel_std = rng.uniform(0.1, 0.5)

        # Click duration: 80-200ms
        self.click_dur_mean = rng.normal(130, 30)
        self.click_dur_std = rng.uniform(15, 40)

        # Cursor curvature: 0 = straight, 1 = very curved
        self.trajectory_curvature = rng.beta(3, 8)

        # Jitter (hand tremor): mostly small, some larger
        self.micro_jitter = rng.exponential(0.02)

        # ── Cognitive/Behavioral ──────────────────────────────────────────
        # Form fill speed: fields per second
        self.form_fill_speed = rng.normal(0.3, 0.1)

        # Hesitation frequency: pauses per minute
        self.hesitation_freq = rng.poisson(3)

        # Session duration preference: seconds
        self.session_duration_mean = rng.normal(120, 40)

        # ── Physiological ─────────────────────────────────────────────────
        # Hand dominance: -1 = left, 0 = ambidextrous, 1 = right
        self.hand_dominance = rng.choice([-0.8, 0.0, 0.8], p=[0.1, 0.05, 0.85])

        # Touch pressure (mobile): 0-1 normalized
        self.touch_force_mean = rng.beta(4, 4)
        self.touch_force_std = rng.uniform(0.05, 0.2)

        # ── Device context ────────────────────────────────────────────────
        self.screen_width = rng.choice([1366, 1440, 1536, 1920, 2560])
        self.screen_height = rng.choice([768, 900, 864, 1080, 1440])
        self.hardware_concurrency = rng.choice([4, 8, 12, 16])
        self.device_memory = rng.choice([4, 8, 16, 32])

        # Login time preferences
        self.preferred_hour = int(rng.normal(14, 4)) % 24
        self.preferred_day = int(rng.integers(0, 7))


class SyntheticDataGenerator:
    """Generates synthetic behavioral biometric datasets.

    Creates realistic feature vectors for multiple simulated users,
    each with unique behavioral fingerprints and natural session-to-session
    variation.
    """

    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)
        self.random = random.Random(seed)

    def generate_dataset(
        self,
        n_users: int = 10,
        samples_per_user: int = 200,
        impostor_samples: int = 100,
    ) -> List[Dict[str, Any]]:
        """Generate a full dataset with genuine + impostor samples per user.

        Args:
            n_users: Number of simulated users to create.
            samples_per_user: Genuine samples per user.
            impostor_samples: Impostor samples per user (from other users' profiles).

        Returns:
            List of dicts, each with:
                user_id: int
                profile: UserProfile metadata
                genuine: List[Dict] — feature vectors for this user
                impostor: List[Dict] — feature vectors from other users
        """
        logger.info(
            "Generating synthetic dataset: %d users × %d samples",
            n_users, samples_per_user,
        )

        # Create user profiles
        profiles = [
            UserProfile(user_id=i + 1, rng=self.rng)
            for i in range(n_users)
        ]

        dataset = []
        for i, profile in enumerate(profiles):
            # Generate genuine samples with natural variation
            genuine = [
                self._generate_sample(profile, session_idx=j)
                for j in range(samples_per_user)
            ]

            # Generate impostor samples from OTHER users' profiles
            impostor = []
            other_profiles = [p for p in profiles if p.user_id != profile.user_id]
            for j in range(impostor_samples):
                other = self.random.choice(other_profiles)
                impostor.append(self._generate_sample(other, session_idx=j))

            dataset.append({
                "user_id": profile.user_id,
                "profile": self._profile_metadata(profile),
                "genuine": genuine,
                "impostor": impostor,
            })

        logger.info(
            "Dataset generated: %d users, %d total genuine, %d total impostor",
            n_users,
            n_users * samples_per_user,
            n_users * impostor_samples,
        )
        return dataset

    def _generate_sample(self, profile: UserProfile, session_idx: int = 0) -> Dict[str, float]:
        """Generate a single behavioral feature vector from a user profile.

        Adds realistic session-to-session variation (circadian rhythms,
        fatigue, learning effects).
        """
        rng = self.rng

        # Session-level variation factors
        fatigue = 1.0 + 0.1 * math.sin(session_idx * 0.1)  # Gradual fatigue
        time_of_day = (profile.preferred_hour + rng.normal(0, 2)) % 24
        circadian = 1.0 + 0.05 * math.cos(2 * math.pi * time_of_day / 24)

        # Noise scale: how much variation from the profile mean
        ns = lambda std: rng.normal(0, std * fatigue * circadian)

        features: Dict[str, float] = {}

        # ── Category 1: Mouse & Pointer (44 features) ────────────────────
        features["mouse_vel_instant"] = max(0, profile.mouse_vel_mean + ns(0.3))
        features["mouse_vel_mean"] = max(0, profile.mouse_vel_mean + ns(0.1))
        features["mouse_vel_std"] = max(0, profile.mouse_vel_std + ns(0.05))
        features["mouse_vel_median"] = max(0, profile.mouse_vel_mean + ns(0.1))
        features["mouse_acc_mean"] = max(0, rng.normal(0.5, 0.2))
        features["mouse_decel_rate"] = max(0, rng.normal(0.3, 0.1))
        features["mouse_jerk_mean"] = max(0, rng.normal(0.2, 0.1))
        features["mouse_jerk_std"] = max(0, rng.uniform(0.05, 0.3))
        features["trajectory_curvature"] = np.clip(profile.trajectory_curvature + ns(0.05), 0, 1)
        features["angular_deviation"] = max(0, rng.normal(15, 5))
        features["overshoot_distance"] = max(0, rng.normal(5, 3))
        features["click_precision"] = np.clip(rng.normal(0.85, 0.1), 0, 1)
        features["click_dur_mean"] = max(0, profile.click_dur_mean + ns(15))
        features["click_dur_std"] = max(0, profile.click_dur_std + ns(5))
        features["dbl_click_interval"] = max(0, rng.normal(250, 50))
        features["mouse_idle_time"] = max(0, rng.exponential(2000))
        features["aimless_movement_dist"] = max(0, rng.exponential(30))
        features["dir_change_freq"] = max(0, rng.normal(0.3, 0.1))
        features["dir_change_angle_mean"] = max(0, rng.normal(45, 15))
        features["dir_change_angle_std"] = max(0, rng.uniform(10, 30))
        features["micro_jitter_amp"] = max(0, profile.micro_jitter + ns(0.005))
        features["micro_jitter_freq"] = max(0, rng.normal(5, 2))
        features["hand_tremor_sig"] = max(0, rng.exponential(0.1))
        features["scroll_speed"] = max(0, rng.normal(300, 100))
        features["scroll_acc"] = max(0, rng.normal(50, 20))
        features["scroll_reversal_freq"] = max(0, rng.poisson(2))
        features["hover_dwell_mean"] = max(0, rng.normal(500, 200))
        features["mouse_event_count"] = max(1, int(rng.normal(150, 50)))
        features["click_count"] = max(1, int(rng.normal(20, 8)))
        features["scroll_event_count"] = max(0, int(rng.normal(15, 8)))
        features["mouse_click_interval_mean"] = max(0, rng.normal(3000, 1000))
        features["mouse_click_interval_std"] = max(0, rng.normal(1500, 500))
        features["mouse_dblclick_count"] = max(0, int(rng.poisson(1)))
        features["hover_dwell_max"] = max(0, rng.normal(2000, 800))
        features["hover_count"] = max(0, int(rng.normal(10, 5)))
        features["mouse_path_straightness"] = np.clip(rng.normal(0.7, 0.15), 0, 1)
        features["mouse_path_segment_count"] = max(1, int(rng.normal(30, 10)))
        for d in range(8):
            features[f"mouse_dir_histogram_{d}"] = max(0, rng.uniform(0.05, 0.25))
        features["mouse_dir_entropy"] = max(0, rng.normal(2.5, 0.5))
        features["mouse_acceleration_mean"] = max(0, rng.normal(0.5, 0.2))

        # ── Category 2: Keystroke (38 features) ──────────────────────────
        features["key_hold_mean"] = max(10, profile.key_hold_mean + ns(10))
        features["key_hold_std"] = max(1, profile.key_hold_std + ns(5))
        features["key_hold_median"] = max(10, profile.key_hold_mean + ns(8))
        features["key_hold_cv"] = np.clip(features["key_hold_std"] / max(features["key_hold_mean"], 1), 0, 2)
        features["flight_time_mean"] = max(10, profile.flight_time_mean + ns(20))
        features["flight_time_std"] = max(1, profile.flight_time_std + ns(10))
        features["flight_time_median"] = max(10, profile.flight_time_mean + ns(15))
        features["inter_key_gap_cv"] = np.clip(rng.normal(0.4, 0.15), 0, 2)
        features["typing_speed_wpm"] = max(5, profile.typing_speed_wpm + ns(5))
        features["typing_speed_variance"] = max(0, rng.normal(3, 1.5))
        features["digraph_timing_consistency"] = np.clip(profile.rhythm_consistency + ns(0.1), 0, 1)
        features["trigraph_timing_consistency"] = np.clip(profile.rhythm_consistency - 0.1 + ns(0.1), 0, 1)
        features["ngram_pattern_entropy"] = max(0, rng.normal(3.0, 0.8))
        features["rhythm_consistency"] = np.clip(profile.rhythm_consistency + ns(0.05), 0, 1)
        features["burst_count"] = max(0, int(rng.normal(5, 2)))
        features["burst_mean_length"] = max(1, rng.normal(4, 1.5))
        features["burst_to_pause_ratio"] = np.clip(rng.normal(0.6, 0.2), 0, 1)
        features["segmented_typing_score"] = np.clip(rng.normal(0.7, 0.15), 0, 1)
        features["backspace_freq"] = max(0, profile.error_rate + ns(0.02))
        features["backspace_timing"] = max(0, rng.normal(200, 80))
        features["delete_vs_backspace"] = np.clip(rng.beta(2, 8), 0, 1)
        features["error_correction_speed"] = max(0, rng.normal(300, 100))
        features["copy_paste_count"] = max(0, int(rng.poisson(0.5)))
        features["shortcut_proficiency"] = np.clip(rng.beta(3, 4), 0, 1)
        features["ctrl_usage_count"] = max(0, int(rng.poisson(3)))
        features["caps_lock_used"] = float(rng.random() < 0.1)
        features["shift_hold_mean"] = max(0, rng.normal(150, 50))
        features["uppercase_method"] = float(rng.random() < 0.7)  # 1=shift, 0=caps
        features["tab_nav_count"] = max(0, int(rng.poisson(2)))
        features["enter_submit_count"] = max(0, int(rng.poisson(1)))
        features["numpad_preference"] = float(rng.random() < 0.3)
        features["password_rhythm"] = np.clip(rng.normal(0.8, 0.15), 0, 1)
        features["data_familiarity_signal"] = np.clip(rng.normal(0.7, 0.2), 0, 1)
        features["time_to_first_key"] = max(0, rng.normal(1500, 500))
        features["time_last_key_to_submit"] = max(0, rng.normal(800, 300))
        features["keystroke_event_count"] = max(5, int(rng.normal(80, 30)))
        features["total_keys_pressed"] = max(5, int(rng.normal(75, 25)))
        features["keystroke_pressure_variance"] = max(0, rng.normal(0.05, 0.02))
        features["keystroke_rhythm_consistency"] = np.clip(profile.rhythm_consistency + ns(0.08), 0, 1)
        features["typing_hold_variance"] = max(0, rng.normal(20, 10))

        # ── Category 3: Cognitive (27 features) ──────────────────────────
        features["nav_path_length"] = max(1, int(rng.normal(8, 3)))
        features["nav_path_entropy"] = max(0, rng.normal(2.0, 0.6))
        features["nav_deviation_score"] = np.clip(rng.normal(0.2, 0.1), 0, 1)
        features["field_visit_count"] = max(1, int(rng.normal(6, 2)))
        features["field_revisit_count"] = max(0, int(rng.poisson(1)))
        features["field_skip_count"] = max(0, int(rng.poisson(0.5)))
        features["field_order_consistency"] = np.clip(rng.normal(0.85, 0.1), 0, 1)
        features["form_fill_speed"] = max(0.01, profile.form_fill_speed + ns(0.05))
        features["pre_field_hesitation_mean"] = max(0, rng.normal(400, 150))
        features["pre_field_hesitation_max"] = max(0, rng.normal(1200, 400))
        features["hesitation_count"] = max(0, int(profile.hesitation_freq + ns(1)))
        features["hesitation_duration_mean"] = max(0, rng.normal(800, 300))
        features["pre_submit_pause"] = max(0, rng.normal(1000, 400))
        features["back_button_count"] = max(0, int(rng.poisson(0.3)))
        features["scroll_read_speed"] = max(0, rng.normal(200, 80))
        features["scroll_depth_reached"] = np.clip(rng.beta(5, 2), 0, 1)
        features["session_duration"] = max(10, profile.session_duration_mean + ns(30))
        features["session_flow_efficiency"] = np.clip(rng.normal(0.75, 0.12), 0, 1)
        features["tab_switch_count"] = max(0, int(rng.poisson(1)))
        features["session_dead_time"] = max(0, rng.exponential(5))
        features["idle_gap_count"] = max(0, int(rng.poisson(2)))
        features["idle_gap_mean"] = max(0, rng.normal(3000, 1000))
        features["error_rate_spike"] = max(0, rng.exponential(0.05))
        features["slow_correction_count"] = max(0, int(rng.poisson(1)))
        features["correction_rate"] = max(0, profile.error_rate + ns(0.01))
        features["rapid_submit_detected"] = float(rng.random() < 0.05)
        features["reread_count"] = max(0, int(rng.poisson(0.5)))
        features["cognitive_event_count"] = max(1, int(rng.normal(20, 8)))

        # ── Category 4: Duress ────────────────────────────────────────────
        features["duress_probability"] = max(0, rng.exponential(0.02))  # Usually near 0

        # ── Category 5: Invisible Challenges (17 features) ───────────────
        features["challenge_count"] = max(0, int(rng.poisson(3)))
        features["response_count"] = features["challenge_count"]
        features["correction_time_mean"] = max(0, rng.normal(200, 80))
        features["correction_time_std"] = max(0, rng.normal(50, 20))
        features["correction_time_median"] = max(0, rng.normal(180, 70))
        features["correction_accuracy_mean"] = np.clip(rng.normal(0.9, 0.08), 0, 1)
        features["correction_accuracy_std"] = max(0, rng.uniform(0.02, 0.1))
        features["subconscious_ratio"] = np.clip(rng.beta(6, 3), 0, 1)
        features["mouse_deviation_count"] = max(0, int(rng.poisson(2)))
        features["mouse_deviation_correction_time"] = max(0, rng.normal(300, 100))
        features["button_micro_shift_count"] = max(0, int(rng.poisson(1)))
        features["button_micro_shift_correction_time"] = max(0, rng.normal(250, 100))
        features["scroll_speed_inject_count"] = max(0, int(rng.poisson(1)))
        features["scroll_speed_inject_correction_time"] = max(0, rng.normal(400, 150))
        features["cursor_speed_change_count"] = max(0, int(rng.poisson(1)))
        features["cursor_speed_change_correction_time"] = max(0, rng.normal(350, 120))
        features["bot_challenge_score"] = max(0, rng.exponential(0.03))

        # ── Category 6: Physiological (15 features) ──────────────────────
        features["hand_dominance_score"] = profile.hand_dominance
        features["touch_force_mean"] = np.clip(profile.touch_force_mean + ns(0.05), 0, 1)
        features["touch_force_std"] = max(0, profile.touch_force_std + ns(0.02))
        features["touch_area_mean"] = np.clip(rng.normal(0.4, 0.1), 0, 1)
        features["touch_area_std"] = max(0, rng.uniform(0.02, 0.1))
        features["grip_posture_score"] = np.clip(rng.normal(0.6, 0.15), 0, 1)
        features["motion_acc_mean"] = max(0, rng.normal(2.0, 0.8))
        features["motion_acc_std"] = max(0, rng.normal(1.0, 0.4))
        features["hand_tremor_magnitude"] = max(0, rng.exponential(0.1))
        features["hand_tremor_frequency"] = max(0, rng.normal(8, 3))
        features["device_tilt_mean"] = rng.normal(15, 8)
        features["device_tilt_std"] = max(0, rng.uniform(2, 10))
        features["touch_event_count"] = max(0, int(rng.normal(30, 15)))
        features["motion_event_count"] = max(0, int(rng.normal(50, 20)))
        features["orientation_change_count"] = max(0, int(rng.poisson(1)))

        # ── Category 7: Device (9 features) ──────────────────────────────
        features["screen_width"] = float(profile.screen_width)
        features["screen_height"] = float(profile.screen_height)
        features["device_memory"] = float(profile.device_memory)
        features["hardware_concurrency"] = float(profile.hardware_concurrency)
        features["max_touch_points"] = float(rng.choice([0, 5, 10]))
        features["login_hour"] = float(int(time_of_day))
        features["login_day"] = float(profile.preferred_day)
        features["rat_latency_score"] = max(0, rng.exponential(0.01))
        features["emulator_score"] = max(0, rng.exponential(0.01))

        # ── Category 8: Composite (10 features) ──────────────────────────
        features["sensorimotor_loop_time"] = max(0, rng.normal(250, 80))
        features["cognitive_signature_entropy"] = max(0, rng.normal(3.5, 0.8))
        features["bot_vs_human_score"] = max(0, rng.exponential(0.02))
        features["rat_vs_human_score"] = max(0, rng.exponential(0.02))
        features["social_eng_probability"] = max(0, rng.exponential(0.02))
        features["session_risk_trajectory"] = np.clip(rng.normal(0.2, 0.1), 0, 1)
        features["lie_detection_signal"] = max(0, rng.exponential(0.03))
        features["multi_user_score"] = max(0, rng.exponential(0.02))
        features["fraud_pattern_score"] = max(0, rng.exponential(0.02))
        features["genuine_user_score"] = np.clip(rng.normal(0.85, 0.1), 0, 1)

        # ── Category 9: Temporal Rhythm (25 features) ─────────────────────
        features["typing_rhythm_entropy"] = max(0, rng.normal(2.5, 0.6))
        features["typing_burst_count"] = max(0, int(rng.normal(5, 2)))
        features["typing_burst_mean_length"] = max(1, rng.normal(4, 1.5))
        features["typing_burst_ratio"] = np.clip(rng.normal(0.5, 0.15), 0, 1)
        features["scroll_reading_wpm"] = max(0, rng.normal(200, 60))
        features["scroll_depth_pct"] = np.clip(rng.beta(4, 2), 0, 1)
        features["pre_submit_pause_mean"] = max(0, rng.normal(1000, 400))
        features["inter_session_speed_delta"] = rng.normal(0, 5)
        features["flight_time_cv"] = np.clip(rng.normal(0.35, 0.12), 0, 2)
        features["bigram_speed_mean"] = max(0, rng.normal(150, 40))
        features["total_active_ms"] = max(100, rng.normal(60000, 20000))
        features["idle_ratio"] = np.clip(rng.beta(3, 7), 0, 1)
        features["micro_vibration_mean"] = max(0, rng.exponential(0.05))
        features["modifier_overlap_mean"] = max(0, rng.normal(50, 20))
        features["modifier_overlap_std"] = max(0, rng.normal(20, 10))
        features["modifier_overlap_count"] = max(0, int(rng.poisson(3)))
        features["touch_velocity_mean"] = max(0, rng.normal(200, 80))
        features["scroll_velocity_mean"] = max(0, rng.normal(300, 100))
        features["scroll_velocity_std"] = max(0, rng.normal(100, 40))
        features["scroll_reversal_rate"] = np.clip(rng.exponential(0.1), 0, 1)
        features["scroll_session_depth"] = np.clip(rng.beta(4, 2), 0, 1)
        features["nav_dwell_mean"] = max(0, rng.normal(2000, 800))
        features["nav_dwell_std"] = max(0, rng.normal(800, 300))
        features["nav_field_revisit_count"] = max(0, int(rng.poisson(1)))
        features["nav_focus_sequence_entropy"] = max(0, rng.normal(2.0, 0.6))
        features["motion_rotation_mean"] = rng.normal(0, 5)

        # Ensure all values are float
        return {k: float(v) for k, v in features.items()}

    def _profile_metadata(self, profile: UserProfile) -> Dict[str, Any]:
        """Extract human-readable metadata from a profile."""
        return {
            "user_id": profile.user_id,
            "typing_speed_wpm": round(profile.typing_speed_wpm, 1),
            "key_hold_mean_ms": round(profile.key_hold_mean, 1),
            "flight_time_mean_ms": round(profile.flight_time_mean, 1),
            "rhythm_consistency": round(profile.rhythm_consistency, 3),
            "error_rate": round(profile.error_rate, 4),
            "hand_dominance": "right" if profile.hand_dominance > 0 else "left" if profile.hand_dominance < 0 else "ambidextrous",
            "screen_resolution": f"{profile.screen_width}x{profile.screen_height}",
        }


def generate_and_save(
    output_dir: str = "training_data",
    n_users: int = 10,
    samples_per_user: int = 200,
    seed: int = 42,
) -> str:
    """Generate synthetic data and save to disk as JSON.

    Returns the path to the generated dataset file.
    """
    import json
    import os

    os.makedirs(output_dir, exist_ok=True)
    gen = SyntheticDataGenerator(seed=seed)
    dataset = gen.generate_dataset(
        n_users=n_users,
        samples_per_user=samples_per_user,
    )

    filepath = os.path.join(output_dir, f"synthetic_{n_users}users_{samples_per_user}samples.json")
    with open(filepath, "w") as f:
        json.dump(dataset, f, indent=2)

    logger.info("Synthetic dataset saved to %s", filepath)
    return filepath
