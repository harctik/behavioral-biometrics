import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import logging
logger = logging.getLogger(__name__)

import os
import hashlib
import joblib
from collections import deque
from logging.handlers import RotatingFileHandler
from datetime import datetime
class BehavioralAnalytics:
    """Advanced behavioral analytics for user comparison and insights"""

    def __init__(self):
        self.population_stats = {}
        self.user_baseline = {}

    def compute_population_stats(self, all_users_data: List[Dict]):
        """Compute population-level statistics for comparison"""
        if not all_users_data:
            return

        all_features = []
        for user_data in all_users_data:
            all_features.extend(user_data.get("features", []))

        if not all_features:
            return

        feature_names = set()
        for f in all_features:
            feature_names.update(f.keys())

        for feature in feature_names:
            values = [f.get(feature, 0) for f in all_features if f.get(feature, 0) > 0]
            if values:
                self.population_stats[feature] = {
                    "mean": np.mean(values),
                    "std": np.std(values),
                    "median": np.median(values),
                    "q25": np.percentile(values, 25),
                    "q75": np.percentile(values, 75),
                }

    def compare_to_population(self, user_features: List[Dict]) -> Dict:
        """Compare user behavior to population norms"""
        if not self.population_stats:
            return {"similarity": 0.5, "deviations": []}

        deviations = []
        for feature, stats in self.population_stats.items():
            user_values = [
                f.get(feature, 0) for f in user_features if f.get(feature, 0) > 0
            ]
            if user_values:
                user_mean = np.mean(user_values)
                z_score = (
                    (user_mean - stats["mean"]) / stats["std"]
                    if stats["std"] > 0
                    else 0
                )
                if abs(z_score) > 2:
                    deviations.append(
                        {
                            "feature": feature,
                            "z_score": float(z_score),
                            "direction": "above" if z_score > 0 else "below",
                        }
                    )

        similarity = max(0, 1 - len(deviations) * 0.1)

        return {
            "similarity": float(similarity),
            "deviations": deviations[:5],
            "unique_patterns": len(deviations),
        }

    def detect_stress_indicators(self, features: Dict) -> Dict:
        """Detect potential stress from behavioral changes"""
        indicators = []
        confidence = 0.0

        # Speed variance increase
        if features.get("speed_variance", 0) > 8:
            indicators.append("high_speed_variance")
            confidence += 0.2

        # Rhythm consistency decrease
        if features.get("rhythm_consistency", 1) < 0.5:
            indicators.append("low_rhythm_consistency")
            confidence += 0.25

        # Increased pause ratio
        if features.get("pause_ratio", 0) > 0.4:
            indicators.append("increased_pauses")
            confidence += 0.2

        # Flight time variability
        if features.get("flight_time_cv", 0) > 0.5:
            indicators.append("high_flight_variability")
            confidence += 0.2

        # Mouse movement irregularity
        if features.get("movement_efficiency", 1) < 0.6:
            indicators.append("irregular_mouse_movement")
            confidence += 0.15

        return {
            "stress_detected": confidence > 0.4,
            "confidence": min(confidence, 1.0),
            "indicators": indicators,
            "recommendation": "Consider additional verification"
            if confidence > 0.5
            else "Monitor closely",
        }

    def detect_fatigue_indicators(self, features: Dict) -> Dict:
        """Detect potential fatigue from behavioral patterns"""
        indicators = []
        confidence = 0.0

        # Reduced typing speed
        if features.get("typing_speed_wpm", 60) < 25:
            indicators.append("slow_typing_speed")
            confidence += 0.25

        # Increased hold time
        if features.get("hold_time_mean", 100) > 150:
            indicators.append("long_key_hold_time")
            confidence += 0.2

        # Reduced mouse velocity
        if features.get("velocity_mean", 3) < 1:
            indicators.append("slow_mouse_movement")
            confidence += 0.2

        # Increased click duration
        if features.get("click_duration_mean", 100) > 180:
            indicators.append("long_click_duration")
            confidence += 0.2

        # Reduced movement efficiency
        if features.get("movement_efficiency", 0.8) < 0.5:
            indicators.append("inefficient_movement")
            confidence += 0.15

        return {
            "fatigue_detected": confidence > 0.4,
            "confidence": min(confidence, 1.0),
            "indicators": indicators,
            "recommendation": "Suggest break"
            if confidence > 0.6
            else "Continue monitoring",
        }



class DeviceFingerprint:
    """Device fingerprinting for enhanced security"""

    def __init__(self):
        self.fingerprints = {}

    def generate_fingerprint(self, request_headers: Dict, ip_address: str) -> str:
        """Generate device fingerprint from request"""
        components = [
            ip_address,
            request_headers.get("User-Agent", ""),
            request_headers.get("Accept-Language", ""),
            request_headers.get("Accept-Encoding", ""),
        ]

        fingerprint = hashlib.sha256("|".join(components).encode()).hexdigest()
        return fingerprint

    def store_fingerprint(self, user_id: int, fingerprint: str):
        """Store device fingerprint for user"""
        if user_id not in self.fingerprints:
            self.fingerprints[user_id] = []

        if fingerprint not in self.fingerprints[user_id]:
            self.fingerprints[user_id].append(fingerprint)

    def is_known_device(self, user_id: int, fingerprint: str) -> bool:
        """Check if device fingerprint is known"""
        return fingerprint in self.fingerprints.get(user_id, [])

    def get_device_count(self, user_id: int) -> int:
        """Get number of known devices for user"""
        return len(self.fingerprints.get(user_id, []))



class SessionSecurityMonitor:
    """Monitor session for hijacking attempts"""

    def __init__(self):
        self.session_profiles = {}

    def create_session_profile(
        self, session_id: str, ip_address: str, user_agent: str, initial_behavior: Dict
    ):
        """Create behavioral profile for session"""
        self.session_profiles[session_id] = {
            "ip_address": ip_address,
            "user_agent": user_agent,
            "initial_behavior": initial_behavior,
            "ip_changes": 0,
            "behavioral_anomalies": 0,
            "created_at": datetime.now(),
        }

    def detect_ip_change(self, session_id: str, new_ip: str) -> bool:
        """Detect IP address change in session"""
        if session_id not in self.session_profiles:
            return False

        profile = self.session_profiles[session_id]
        if profile["ip_address"] != new_ip:
            profile["ip_changes"] += 1
            return True
        return False

    def detect_behavioral_deviation(
        self, session_id: str, current_behavior: Dict
    ) -> float:
        """Detect deviation from initial behavioral profile"""
        if session_id not in self.session_profiles:
            return 0.0

        profile = self.session_profiles[session_id]
        initial = profile["initial_behavior"]

        deviations = []
        for key in initial:
            if key in current_behavior:
                diff = abs(current_behavior[key] - initial[key])
                max_val = max(abs(current_behavior[key]), abs(initial[key]), 1)
                deviations.append(diff / max_val)

        if deviations:
            avg_deviation = np.mean(deviations)
            if avg_deviation > 0.3:
                profile["behavioral_anomalies"] += 1
            return avg_deviation
        return 0.0

    def get_session_risk_score(self, session_id: str) -> Dict:
        """Calculate session risk score"""
        if session_id not in self.session_profiles:
            return {"risk_level": "unknown", "score": 0.0}

        profile = self.session_profiles[session_id]

        ip_risk = min(profile["ip_changes"] * 0.3, 1.0)
        behavior_risk = min(profile["behavioral_anomalies"] * 0.2, 1.0)

        total_risk = (ip_risk + behavior_risk) / 2

        risk_level = "low"
        if total_risk > 0.6:
            risk_level = "high"
        elif total_risk > 0.3:
            risk_level = "medium"

        return {
            "risk_level": risk_level,
            "score": float(total_risk),
            "ip_changes": profile["ip_changes"],
            "behavioral_anomalies": profile["behavioral_anomalies"],
        }



class RiskBasedAuthenticator:
    """Risk-based authentication with adaptive scoring"""

    def __init__(self):
        self.risk_weights = {
            "device_known": 0.15,
            "time_pattern": 0.10,
            "location": 0.15,
            "behavioral_match": 0.40,
            "session_age": 0.10,
            "anomaly_score": 0.10,
        }

    def calculate_risk_score(self, context: Dict) -> Dict:
        """Calculate overall risk score"""
        risk_factors = []

        # Device factor
        if context.get("device_known", False):
            risk_factors.append(0.0)
        else:
            risk_factors.append(0.8)

        # Time pattern factor (unusual hours)
        current_hour = datetime.now().hour
        if 9 <= current_hour <= 18:
            time_risk = 0.2
        else:
            time_risk = 0.6
        risk_factors.append(time_risk)

        # Location factor
        location_risk = context.get("location_risk", 0.5)
        risk_factors.append(location_risk)

        # Behavioral match
        behavior_score = context.get("behavioral_score", 0.5)
        behavior_risk = 1 - behavior_score
        risk_factors.append(behavior_risk)

        # Session age (newer = higher risk)
        session_age = context.get("session_age_minutes", 0)
        if session_age < 5:
            age_risk = 0.7
        elif session_age < 30:
            age_risk = 0.4
        else:
            age_risk = 0.2
        risk_factors.append(age_risk)

        # Anomaly score
        anomaly_risk = context.get("anomaly_score", 0.5)
        risk_factors.append(anomaly_risk)

        # Weighted average
        total_risk = sum(
            rf * rw for rf, rw in zip(risk_factors, self.risk_weights.values())
        )

        # Determine action
        if total_risk > 0.7:
            action = "block"
        elif total_risk > 0.5:
            action = "challenge"
        elif total_risk > 0.3:
            action = "monitor"
        else:
            action = "allow"

        return {
            "risk_score": float(total_risk),
            "risk_level": "high"
            if total_risk > 0.6
            else "medium"
            if total_risk > 0.3
            else "low",
            "action": action,
            "factors": {
                "device": risk_factors[0],
                "time": risk_factors[1],
                "location": risk_factors[2],
                "behavior": risk_factors[3],
                "session_age": risk_factors[4],
                "anomaly": risk_factors[5],
            },
        }



class AuditLogger:
    """Comprehensive audit logging for security compliance"""

    def __init__(self, log_file: str = "audit.log"):
        self.log_file = log_file
        self.setup_logger()

    def setup_logger(self):
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)

        handler = RotatingFileHandler(
            self.log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )
        self.logger.addHandler(handler)

    def log_authentication(
        self, event_type: str, user_id: int, session_id: str, details: Dict
    ):
        """Log authentication event"""
        self.logger.info(
            f"AUTH | {event_type} | User:{user_id} | Session:{session_id} | "
            f"IP:{details.get('ip_address', 'N/A')} | "
            f"Success:{details.get('success', 'N/A')}"
        )

    def log_behavioral_analysis(
        self, user_id: int, session_id: str, auth_score: float, anomaly_detected: bool
    ):
        """Log behavioral analysis result"""
        self.logger.info(
            f"BEHAVIOR | User:{user_id} | Session:{session_id} | "
            f"Score:{auth_score:.3f} | Anomaly:{anomaly_detected}"
        )

    def log_risk_event(
        self, user_id: int, session_id: str, risk_score: float, action: str
    ):
        """Log risk event"""
        self.logger.warning(
            f"RISK | User:{user_id} | Session:{session_id} | "
            f"Score:{risk_score:.3f} | Action:{action}"
        )

    def log_session_event(
        self, event_type: str, user_id: int, session_id: str, details: Dict
    ):
        """Log session event"""
        self.logger.info(
            f"SESSION | {event_type} | User:{user_id} | Session:{session_id} | "
            f"{details}"
        )


