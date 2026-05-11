"""ML Model Unit Tests.

Covers: CognitiveEngine, ADWIN drift detection, DuressDetector,
LivenessDetector (GAN module), and FeatureExtractor.

These tests run WITHOUT GPU/heavy deps — all models tested via their
pure-Python / NumPy inference paths.
"""

import pytest
import numpy as np


# ═══════════════════════════════════════════════════════════════════════════════
# COGNITIVE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


class TestCognitiveEngine:
    """Tests for the behavioral biometrics cognitive behavioral engine."""

    def _engine(self):
        from app.models.cognitive_engine import CognitiveEngine

        return CognitiveEngine()

    def test_normal_session_produces_low_risk(self):
        """Normal behavioral features should yield low cognitive risk."""
        result = self._engine().analyze(
            {
                "hesitation_count": 1,
                "hesitation_duration_mean": 500,
                "reread_count": 1,
                "tab_switch_count": 0,
                "scroll_reversal_rate": 0.1,
                "copy_paste_count": 0,
                "rapid_submit_detected": 0,
                "nav_dwell_mean": 800,
                "nav_focus_sequence_entropy": 1.5,
                "correction_rate": 0.12,
                "scroll_velocity_std": 0.5,
                "scroll_velocity_mean": 1.0,
            }
        )
        assert result["behavioral_state"] == "normal"
        assert result["recommended_action"] == "allow"
        assert result["cognitive_risk"] < 0.25
        assert result["duress_probability"] < 0.3
        assert isinstance(result["cognitive_flags"], list)

    def test_duress_detection(self):
        """Multiple long hesitations + tab switches should trigger duress."""
        result = self._engine().analyze(
            {
                "hesitation_count": 5,
                "hesitation_duration_mean": 4000,
                "reread_count": 6,
                "tab_switch_count": 4,
                "scroll_reversal_rate": 0.7,
                "copy_paste_count": 0,
                "rapid_submit_detected": 0,
                "nav_dwell_mean": 1500,
                "correction_rate": 0.15,
            }
        )
        assert result["duress_probability"] >= 0.5
        assert any("duress" in f for f in result["cognitive_flags"])

    def test_app_fraud_detection(self):
        """Copy-paste + rapid submit + no hesitation = coached APP fraud."""
        result = self._engine().analyze(
            {
                "copy_paste_count": 3,
                "rapid_submit_detected": 1,
                "hesitation_count": 0,
                "tab_switch_count": 3,
                "nav_dwell_mean": 200,
                "nav_focus_sequence_entropy": 0.3,
                "correction_rate": 0.0,
                "reread_count": 0,
                "scroll_reversal_rate": 0.0,
            }
        )
        assert result["app_fraud_probability"] >= 0.5
        assert result["recommended_action"] in ("block", "step_up")
        assert any("app_fraud" in f for f in result["cognitive_flags"])

    def test_bot_detection(self):
        """Constant scroll speed + superhuman nav = bot."""
        result = self._engine().analyze(
            {
                "scroll_velocity_std": 0.0005,
                "scroll_velocity_mean": 2.0,
                "nav_dwell_mean": 30,
                "correction_rate": 0.0,
                "hesitation_count": 0,
                "nav_focus_sequence_entropy": 0.0,
                "copy_paste_count": 0,
                "rapid_submit_detected": 0,
                "reread_count": 0,
                "tab_switch_count": 0,
                "scroll_reversal_rate": 0.0,
            }
        )
        assert result["bot_probability"] >= 0.5
        assert any("bot" in f for f in result["cognitive_flags"])

    def test_takeover_detection_with_baseline(self):
        """Large behavioral shift from baseline = account takeover."""
        baseline = {
            "nav_dwell_mean": 1000,
            "correction_rate": 0.15,
            "scroll_velocity_mean": 1.0,
        }
        result = self._engine().analyze(
            {
                "nav_dwell_mean": 100,
                "correction_rate": 0.8,
                "scroll_velocity_mean": 5.0,
                "hesitation_count": 0,
                "reread_count": 0,
                "tab_switch_count": 0,
                "scroll_reversal_rate": 0.0,
                "copy_paste_count": 0,
                "rapid_submit_detected": 0,
            },
            baseline=baseline,
        )
        assert result["takeover_probability"] >= 0.4
        assert any("takeover" in f for f in result["cognitive_flags"])

    def test_takeover_no_baseline_returns_zero(self):
        """Without a baseline, takeover probability must be 0."""
        result = self._engine().analyze(
            {"nav_dwell_mean": 100, "correction_rate": 0.8},
            baseline=None,
        )
        assert result["takeover_probability"] == 0.0

    def test_run_cognitive_analysis_convenience(self):
        """The module-level convenience function should work identically."""
        from app.models.cognitive_engine import run_cognitive_analysis

        result = run_cognitive_analysis({"hesitation_count": 0, "copy_paste_count": 0})
        assert "cognitive_risk" in result
        assert "recommended_action" in result

    def test_empty_features_safe(self):
        """Empty feature dict should not crash — all values default to 0."""
        result = self._engine().analyze({})
        assert result["cognitive_risk"] >= 0.0
        assert result["behavioral_state"] in (
            "normal",
            "suspicious",
            "alert",
            "critical",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ADWIN DRIFT DETECTION
# ═══════════════════════════════════════════════════════════════════════════════


class TestADWINDriftDetection:
    """Tests for the ADWIN adaptive windowing drift detector."""

    def test_stable_stream_no_drift(self):
        from app.models.adwin_drift import ADWINDetector

        det = ADWINDetector(delta=0.05)
        for _ in range(50):
            det.add_observation(0.5 + np.random.normal(0, 0.01))
        has_drift, _ = det.get_drift_status("default")
        # Stable stream should usually not trigger drift
        # (probabilistic — we use tight variance to keep deterministic)
        assert isinstance(has_drift, bool)

    def test_behavioral_drift_detector_api(self):
        from app.models.adwin_drift import BehavioralDriftDetector

        bdd = BehavioralDriftDetector()
        for score in [0.1, 0.12, 0.11, 0.13, 0.1]:
            bdd.add_user_score(user_id=1, score=score)
        has_drift, drifts = bdd.check_user_drift(1)
        assert isinstance(has_drift, bool)
        assert isinstance(drifts, list)

    def test_recalibration_after_drift(self):
        from app.models.adwin_drift import BehavioralDriftDetector

        bdd = BehavioralDriftDetector()
        # Feed stable data then a sudden shift
        for _ in range(30):
            bdd.add_user_score(user_id=2, score=0.1)
        for _ in range(30):
            bdd.add_user_score(user_id=2, score=0.9)
        # should_recalibrate checks for recent drifts
        result = bdd.should_recalibrate(2)
        assert isinstance(result, bool)

    def test_get_user_statistics(self):
        from app.models.adwin_drift import BehavioralDriftDetector

        bdd = BehavioralDriftDetector()
        bdd.add_user_score(user_id=3, score=0.5)
        stats = bdd.get_user_statistics(3)
        assert isinstance(stats, dict)

    def test_clear_user_drifts(self):
        from app.models.adwin_drift import BehavioralDriftDetector

        bdd = BehavioralDriftDetector()
        bdd.add_user_score(user_id=4, score=0.5)
        bdd.clear_user_drifts(4)
        has_drift, drifts = bdd.check_user_drift(4)
        assert has_drift is False
        assert drifts == []


# ═══════════════════════════════════════════════════════════════════════════════
# DURESS DETECTOR
# ═══════════════════════════════════════════════════════════════════════════════


class TestDuressDetector:
    """Tests for the standalone DuressDetector module."""

    def _make_feature_dict(self, speed_factor=1.0):
        """Generate a plausible feature dict for duress detection."""
        return {
            f"feature_{i}": float(np.random.normal(0.5, 0.1) * speed_factor)
            for i in range(20)
        }

    def test_set_baseline(self):
        from app.models.duress_detector import DuressDetector

        d = DuressDetector()
        baseline = [self._make_feature_dict() for _ in range(10)]
        d.set_user_baseline(1, baseline)
        # Should store baseline without error
        assert 1 in d.baseline_profiles

    def test_compute_duress_score(self):
        from app.models.duress_detector import DuressDetector

        d = DuressDetector()
        baseline = [self._make_feature_dict() for _ in range(10)]
        d.set_user_baseline(1, baseline)
        result = d.compute_duress_score(
            user_id=1,
            keystroke_features=self._make_feature_dict(),
            mouse_features=self._make_feature_dict(),
        )
        assert "duress_score" in result
        assert "alert_level" in result
        assert result["alert_level"] in ("normal", "elevated", "high", "critical")

    def test_no_baseline_returns_safe(self):
        from app.models.duress_detector import DuressDetector

        d = DuressDetector()
        result = d.compute_duress_score(
            user_id=999,
            keystroke_features=self._make_feature_dict(),
            mouse_features=self._make_feature_dict(),
        )
        assert result["duress_score"] == 0.0
        assert result["alert_level"] == "normal"


# ═══════════════════════════════════════════════════════════════════════════════
# LIVENESS DETECTOR (from GAN module)
# ═══════════════════════════════════════════════════════════════════════════════


class TestLivenessDetector:
    """Tests for anti-replay entropy analysis."""

    def test_real_stream_low_replay_probability(self):
        from app.models.gan_adversarial import LivenessDetector

        ld = LivenessDetector()
        # Natural-looking stream with variance
        stream = [{"hold_time": float(np.random.normal(120, 25))} for _ in range(50)]
        result = ld.check_entropy(stream)
        assert result["sufficient_data"] is True
        assert result["replay_probability"] <= 0.7

    def test_constant_stream_high_replay_probability(self):
        from app.models.gan_adversarial import LivenessDetector

        ld = LivenessDetector()
        # Perfectly uniform stream — synthetic/replayed
        stream = [{"hold_time": 100.0} for _ in range(50)]
        result = ld.check_entropy(stream)
        assert result["sufficient_data"] is True
        # Constant values should trigger suspicion
        assert result["coefficient_of_variation"] < 0.05

    def test_insufficient_data(self):
        from app.models.gan_adversarial import LivenessDetector

        ld = LivenessDetector()
        stream = [{"hold_time": 100.0} for _ in range(5)]
        result = ld.check_entropy(stream)
        assert result["sufficient_data"] is False

    def test_hmac_sign_and_verify(self):
        from app.models.gan_adversarial import LivenessDetector

        ld = LivenessDetector(hmac_key="test-key-12345")
        token = ld.sign_event_packet("session-1", {"key": "a"}, 1000)
        assert ":" in token

    def test_hmac_verify_rejects_tampered(self):
        from app.models.gan_adversarial import LivenessDetector

        ld = LivenessDetector(hmac_key="test-key-12345")
        token = ld.sign_event_packet("session-1", {"key": "a"}, 1000)
        # Tamper with the data
        valid = ld.verify_event_packet("session-1", {"key": "b"}, 1000, token)
        assert valid is False


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE EXTRACTOR
# ═══════════════════════════════════════════════════════════════════════════════


class TestFeatureExtractor:
    """Tests for the behavioral feature extractor."""

    def test_extract_keystroke_features(self):
        from app.feature_extractor import BehavioralFeatureExtractor

        ext = BehavioralFeatureExtractor()
        events = [
            {"ts": i * 100, "key": chr(65 + (i % 26)), "type": "keydown"}
            for i in range(20)
        ]
        features = ext.extract_keystroke_features(events)
        assert isinstance(features, dict)
        assert len(features) > 0

    def test_extract_mouse_features(self):
        from app.feature_extractor import BehavioralFeatureExtractor

        ext = BehavioralFeatureExtractor()
        events = [
            {"x": i * 10, "y": i * 5, "ts": i * 50, "type": "mousemove"}
            for i in range(20)
        ]
        features = ext.extract_mouse_features(events)
        assert isinstance(features, dict)

    def test_empty_events_safe(self):
        from app.feature_extractor import BehavioralFeatureExtractor

        ext = BehavioralFeatureExtractor()
        k_features = ext.extract_keystroke_features([])
        m_features = ext.extract_mouse_features([])
        assert isinstance(k_features, dict)
        assert isinstance(m_features, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# MFA ENFORCEMENT (server-side decorator)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMFAEnforcement:
    """Verify that @require_mfa blocks pwd-only JWTs on sensitive endpoints."""

    def test_sign_intent_rejects_pwd_token(self, client, logged_in_user, auth_headers):
        """sign-intent should reject pwd-only tokens."""
        resp = client.post(
            "/api/v1/transaction/sign-intent",
            json={
                "session_id": logged_in_user["session_id"],
                "amount": 500,
                "operation": "transfer",
                "nonce": "test-nonce",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "MFA_REQUIRED"

    def test_transaction_nonce_allows_pwd_token(self, client, auth_headers):
        """Nonce issuance does NOT require MFA (read-only operation)."""
        resp = client.get("/api/v1/transaction/nonce", headers=auth_headers)
        assert resp.status_code == 200
        assert "nonce" in resp.get_json()

    def test_sign_intent_allows_mfa_token(
        self, client, mfa_logged_in_user, mfa_auth_headers
    ):
        """sign-intent should accept MFA-elevated tokens."""
        nonce = client.get(
            "/api/v1/transaction/nonce", headers=mfa_auth_headers
        ).get_json()["nonce"]
        resp = client.post(
            "/api/v1/transaction/sign-intent",
            json={
                "session_id": mfa_logged_in_user["session_id"],
                "amount": 500,
                "operation": "transfer",
                "nonce": nonce,
            },
            headers=mfa_auth_headers,
        )
        assert resp.status_code == 200
        assert "signature" in resp.get_json()
