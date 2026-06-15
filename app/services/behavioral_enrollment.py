import statistics
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class BehavioralEnrollmentService:
    @staticmethod
    def extract_features_from_raw(
        keystroke_events: List[Dict[str, Any]],
        mouse_events: List[Dict[str, Any]],
        window_start: int,
        window_end: int,
    ) -> Dict[str, float]:
        """Extract timing and velocity features from raw behavioral events."""
        features = {}
        
        # Keystroke features
        if keystroke_events and len(keystroke_events) >= 5:
            hold_times = [e.get("hold_time", 0) for e in keystroke_events if e.get("hold_time")]
            flight_times = [e.get("flight_time", 0) for e in keystroke_events if e.get("flight_time")]
            
            if hold_times:
                features["hold_time_mean"] = statistics.mean(hold_times)
                features["hold_time_std"] = statistics.stdev(hold_times) if len(hold_times) > 1 else 0.0
                features["hold_time_median"] = statistics.median(hold_times)
                features["hold_time_cv"] = features["hold_time_std"] / max(features["hold_time_mean"], 1e-6)
                
            if flight_times:
                features["flight_time_mean"] = statistics.mean(flight_times)
                features["flight_time_std"] = statistics.stdev(flight_times) if len(flight_times) > 1 else 0.0
                features["flight_time_median"] = statistics.median(flight_times)
                features["flight_time_cv"] = features["flight_time_std"] / max(features["flight_time_mean"], 1e-6)
                
            elapsed_ms = max(1, window_end - window_start)
            typing_speed_wpm = (len(keystroke_events) / 5.0) / max(elapsed_ms / 60000.0, 0.01)
            features["typing_speed_wpm"] = min(typing_speed_wpm, 200)
            
            backspaces = [e for e in keystroke_events if e.get("is_backspace")]
            correction_rate = len(backspaces) / max(len(keystroke_events), 1)
            features["burst_ratio"] = 1.0 - correction_rate
            
            if hold_times and len(hold_times) > 2:
                h_mean = statistics.mean(hold_times)
                h_std = statistics.stdev(hold_times)
                features["rhythm_consistency"] = max(0, 1.0 - (h_std / max(h_mean, 1e-6)))
                
            digraph_times = []
            for i in range(len(keystroke_events) - 1):
                ft = keystroke_events[i + 1].get("flight_time", 0)
                if ft and 0 < ft < 2000:
                    digraph_times.append(ft)
            if digraph_times and len(digraph_times) > 2:
                d_mean = statistics.mean(digraph_times)
                d_std = statistics.stdev(digraph_times)
                features["digraph_consistency"] = max(0, 1.0 - (d_std / max(d_mean, 1e-6)))

        # Mouse features
        if mouse_events:
            velocities = [e.get("velocity", 0) for e in mouse_events if e.get("velocity")]
            if velocities:
                features["velocity_mean"] = statistics.mean(velocities)
                features["velocity_std"] = statistics.stdev(velocities) if len(velocities) > 1 else 0.0
                features["velocity_median"] = statistics.median(velocities)
            
            accelerations = [e.get("acceleration", 0) for e in mouse_events if e.get("acceleration")]
            if accelerations:
                features["acceleration_mean"] = statistics.mean(accelerations)
                
            curvatures = [e.get("curvature", 0) for e in mouse_events if e.get("curvature")]
            if curvatures:
                features["curvature_mean"] = statistics.mean(curvatures)

        return features

    @staticmethod
    def process_session_zero(
        user_id: int, 
        enrollment_seed: Dict[str, Any], 
        behavioral_data: Dict[str, Any],
        source: str = "registration"
    ) -> Dict[str, Any]:
        """Extract features from initial session data and ingest into passive enrollment.
        
        This handles two parallel profile systems:
        1. Aggregate features → PassiveEnrollmentManager (existing EMA system)
        2. Per-key/digraph profiles → Bayesian conjugate update system (new)
        """
        keystroke_events = enrollment_seed.get("keystroke_events") or behavioral_data.get("keystroke_events") or []
        mouse_events = enrollment_seed.get("mouse_events") or behavioral_data.get("mouse_events") or []
        
        window_end = enrollment_seed.get("window_end", 0) or behavioral_data.get("window_end", 0)
        window_start = enrollment_seed.get("window_start", 0) or behavioral_data.get("window_start", 0)
        
        result = {"action": "no_data"}
        
        # ── 1. Aggregate feature extraction (existing system) ─────────────
        features = BehavioralEnrollmentService.extract_features_from_raw(
            keystroke_events, mouse_events, window_start, window_end
        )
        
        if features:
            try:
                from app.models.passive_enrollment import get_enrollment_manager
                enrollment_mgr = get_enrollment_manager()
                result = enrollment_mgr.ingest_session_data(
                    user_id=user_id,
                    keystroke_features=features,
                    source=source,
                )
            except Exception as exc:
                logger.error("Failed to ingest Session 0 aggregate data: %s", exc)
                result = {"error": str(exc)}
        
        # ── 2. Per-key/digraph profile extraction (new Bayesian system) ───
        if keystroke_events and len(keystroke_events) >= 5:
            try:
                from app.models.digraph_profile import get_digraph_extractor
                from app.models.passive_enrollment import get_enrollment_manager
                
                extractor = get_digraph_extractor()
                digraph_profile = extractor.extract_profile(
                    keystroke_events, source="signup"
                )
                
                if digraph_profile.get("meta", {}).get("unique_keys", 0) >= 3:
                    enrollment_mgr = get_enrollment_manager()
                    digraph_result = enrollment_mgr.ingest_digraph_profile(
                        user_id=user_id,
                        digraph_profile=digraph_profile,
                        source="signup",
                    )
                    
                    # Merge digraph result into the main result
                    result["digraph_action"] = digraph_result.get("action")
                    result["digraph_keys"] = digraph_result.get("per_key_count", 0)
                    result["digraph_pairs"] = digraph_result.get("per_digraph_count", 0)
                    result["digraph_confidence"] = digraph_result.get("confidence", 0.0)
                    
                    logger.info(
                        "Session 0 digraph profile for user %d: %d keys, %d digraphs",
                        user_id,
                        digraph_result.get("per_key_count", 0),
                        digraph_result.get("per_digraph_count", 0),
                    )
            except Exception as exc:
                logger.error("Failed to extract Session 0 digraph profile: %s", exc)
        
        return result

behavioral_enrollment_service = BehavioralEnrollmentService()

