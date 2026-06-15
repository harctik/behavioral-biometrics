import numpy as np

class SyntheticBiomechanicsDataGenerator:
    """
    Generates highly realistic behavioral features mimicking human biomechanics.
    Utilizes:
    - Fitts's Law for mouse pointing time.
    - Flash's Minimum Jerk model for trajectory velocity profiles.
    - Log-normal distributions for physiological parameters (pressure, area).
    """

    def __init__(self, seed=None):
        self.rng = np.random.default_rng(seed)

    def apply_fitts_law(self, distance: float, width: float, a: float, b: float) -> float:
        """
        Fitts's Law models human pointing time.
        T = a + b * log2(1 + D/W)
        """
        id_fitts = np.log2(1 + distance / width)
        time_ms = a + b * id_fitts
        return max(50.0, time_ms + self.rng.normal(0, time_ms * 0.1))

    def flash_minimum_jerk_velocity(self, time_total: float) -> dict:
        """
        Models human arm/hand reaching movements using Flash & Hogan (1985) Minimum Jerk.
        Returns expected mean velocity, max velocity, and standard deviation over the trajectory.
        """
        # Peak velocity is roughly 1.875 * (Distance / Time)
        # Using a normalized distance of 1.0
        dist = 1.0
        v_mean = dist / max(time_total, 1.0)
        v_peak = 1.875 * v_mean
        v_std = v_mean * 0.45  # Approx std of bell curve
        
        return {
            "mean": v_mean * 1000, # scaled to sensible units
            "max": v_peak * 1000,
            "std": v_std * 1000
        }

    def generate_touch_physiology(self, base_pressure: float, base_area: float) -> dict:
        """
        Physiological parameters like pressure and finger contact area follow log-normal distributions.
        Pressure and area are positively correlated.
        """
        pressure = self.rng.lognormal(mean=np.log(base_pressure), sigma=0.15)
        
        # Area expands slightly as pressure increases
        area_multiplier = 1.0 + (pressure - base_pressure) * 0.3
        area = self.rng.lognormal(mean=np.log(base_area * area_multiplier), sigma=0.1)
        
        return {
            "pressure": np.clip(pressure, 0.1, 1.0),
            "area": np.clip(area, 0.1, 1.0)
        }

    def generate_user_archetype(self, user_id: int) -> dict:
        """
        Creates a fundamental biomechanical profile for a specific synthetic user.
        """
        archetype_rng = np.random.default_rng(user_id * 1337)
        return {
            "fitts_a": archetype_rng.uniform(100, 300),  # Cognitive reaction time (ms)
            "fitts_b": archetype_rng.uniform(50, 150),   # Motor processing time (ms/bit)
            "base_pressure": archetype_rng.uniform(0.3, 0.8),
            "base_area": archetype_rng.uniform(0.3, 0.7),
            "motor_noise": archetype_rng.uniform(0.02, 0.1), # Jitter / tremor multiplier
            "rhythm_consistency": archetype_rng.beta(8, 2), # Typically high consistency for typing
            "base_typing_speed_wpm": archetype_rng.normal(60, 15),
            "device_tilt": archetype_rng.normal(15, 10),
            "scroll_speed": archetype_rng.uniform(100, 500)
        }
    
    def synthesize_mouse_and_touch_features(self, archetype: dict) -> dict:
        """
        Takes an archetype and produces one realistic sample of mouse/touch data.
        """
        # Mouse parameters based on Fitts's Law and Minimum Jerk
        avg_distance = self.rng.uniform(200, 800)
        avg_target_width = self.rng.uniform(20, 100)
        movement_time = self.apply_fitts_law(avg_distance, avg_target_width, archetype["fitts_a"], archetype["fitts_b"])
        
        kinematics = self.flash_minimum_jerk_velocity(movement_time / 1000.0) # time in seconds
        
        # Touch parameters
        touch = self.generate_touch_physiology(archetype["base_pressure"], archetype["base_area"])
        
        # Tremor / Noise
        tremor_sig = self.rng.exponential(archetype["motor_noise"])
        
        features = {}
        features["mouse_vel_mean"] = kinematics["mean"]
        features["mouse_vel_std"] = kinematics["std"] + (tremor_sig * kinematics["mean"])
        features["mouse_vel_median"] = kinematics["mean"] * 0.95
        features["mouse_vel_max"] = kinematics["max"]
        
        features["touch_force_mean"] = touch["pressure"]
        features["touch_force_std"] = archetype["base_pressure"] * 0.1 + tremor_sig
        features["touch_area_mean"] = touch["area"]
        features["touch_area_std"] = archetype["base_area"] * 0.08 + tremor_sig
        
        features["hand_tremor_sig"] = tremor_sig
        features["hand_tremor_magnitude"] = tremor_sig
        features["device_tilt_mean"] = archetype["device_tilt"] + self.rng.normal(0, 3)
        features["scroll_speed"] = archetype["scroll_speed"] + self.rng.normal(0, archetype["scroll_speed"] * 0.1)
        
        return features
