"""
Coverage Boost Tests — targets the 6 critical/medium coverage gaps.

Files covered:
  1. behavioral_feature_engine.py (was 0%)
  2. per_user_feature_selector.py (was 0%)
  3. passive_enrollment.py (was 23%)
  4. transaction_baseline.py (was 32%)
  5. invisible_challenge_engine.py (was 45%)
  6. extended_risk_scorer.py (was 49%)
  7. device_intelligence.py (was 57%)
  8. ml_ensemble.py (was 68%)
"""

import math
import pytest
import numpy as np


# ═══════════════════════════════════════════════════════════════════════════════
# 1. BehavioralFeatureEngine (was 0% → target 95%+)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBehavioralFeatureEngine:
    """Covers extract(), get_feature_vector(), get_category_scores(), helpers."""

    @pytest.fixture
    def engine(self):
        from app.behavioral_feature_engine import BehavioralFeatureEngine

        return BehavioralFeatureEngine()

    @pytest.fixture
    def sample_payload(self):
        return {
            "categories": {
                "mouse_pointer": {
                    "mouse_vel_mean": 350,
                    "click_dur_mean": 180,
                    "mouse_event_count": 50,
                },
                "keystroke": {
                    "key_hold_mean": 110,
                    "flight_time_mean": 85,
                    "typing_speed_wpm": 55,
                    "keystroke_event_count": 30,
                },
                "cognitive": {
                    "hesitation_count": 2,
                    "session_duration": 300,
                    "cognitive_event_count": 10,
                },
                "invisible_challenges": {
                    "challenge_count": 5,
                    "response_count": 4,
                    "bot_challenge_score": 0.1,
                },
                "physiological": {
                    "touch_force_mean": 0.6,
                    "hand_tremor_magnitude": 0.1,
                    "motion_acc_std": 5,
                },
                "composite": {"fraud_pattern_score": 0.05, "bot_vs_human_score": 0.9},
            },
            "extended_features": {"mouse_mouse_vel_std": 120, "ks_key_hold_std": 20},
            "device_context": {
                "screen_width": 1920,
                "screen_height": 1080,
                "login_hour": 14,
                "login_day": 2,
            },
        }

    def test_init(self, engine):
        assert engine.FEATURE_COUNT > 100

    def test_extract_empty_payload(self, engine):
        result = engine.extract({})
        assert isinstance(result, dict)
        assert len(result) == engine.FEATURE_COUNT
        assert all(v == 0.0 for v in result.values())

    def test_extract_with_data(self, engine, sample_payload):
        result = engine.extract(sample_payload)
        assert result["mouse_vel_mean"] == 350.0
        assert result["key_hold_mean"] == 110.0
        assert result["screen_width"] == 1920.0
        assert result["fraud_pattern_score"] == 0.05

    def test_get_feature_vector(self, engine, sample_payload):
        features = engine.extract(sample_payload)
        vec = engine.get_feature_vector(features)
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (engine.FEATURE_COUNT,)
        assert vec.dtype == np.float32

    def test_get_category_scores(self, engine, sample_payload):
        features = engine.extract(sample_payload)
        scores = engine.get_category_scores(features)
        assert "mouse_anomaly" in scores
        assert "keystroke_anomaly" in scores
        assert "cognitive_risk" in scores
        assert "duress_risk" in scores
        assert "challenge_bot_risk" in scores
        assert "physiological_anomaly" in scores
        assert "device_risk" in scores
        assert "composite_fraud" in scores
        assert all(0.0 <= v <= 1.0 for v in scores.values())

    def test_score_category_empty(self, engine):
        assert engine._score_category({}, []) == 0.0

    def test_score_physio_high_force(self, engine):
        assert engine._score_physio({"touch_force_mean": 0.99}) >= 0.3

    def test_score_physio_low_force(self, engine):
        assert engine._score_physio({"touch_force_mean": 0.01}) >= 0.3

    def test_score_physio_high_tremor(self, engine):
        assert engine._score_physio({"hand_tremor_magnitude": 0.8}) >= 0.2

    def test_score_physio_high_motion(self, engine):
        assert engine._score_physio({"motion_acc_std": 20}) >= 0.3

    def test_score_physio_all_normal(self, engine):
        assert (
            engine._score_physio(
                {
                    "touch_force_mean": 0.5,
                    "hand_tremor_magnitude": 0.1,
                    "motion_acc_std": 5,
                }
            )
            == 0.0
        )

    def test_safe_float_none(self, engine):
        assert engine._safe_float(None) == 0.0

    def test_safe_float_nan(self, engine):
        assert engine._safe_float(float("nan")) == 0.0

    def test_safe_float_inf(self, engine):
        assert engine._safe_float(float("inf")) == 0.0

    def test_safe_float_string(self, engine):
        assert engine._safe_float("42.5") == 42.5

    def test_safe_float_bad_string(self, engine):
        assert engine._safe_float("not_a_number") == 0.0

    def test_safe_float_list(self, engine):
        assert engine._safe_float([1, 2]) == 0.0

    def test_get_info(self, engine):
        info = engine.get_info()
        assert info["total_features"] == engine.FEATURE_COUNT
        assert "categories" in info
        assert len(info["categories"]) == 8
        assert info["all_feature_names"] == engine.ALL_FEATURES

    def test_singleton(self):
        from app.behavioral_feature_engine import get_behavioral_engine

        e1 = get_behavioral_engine()
        e2 = get_behavioral_engine()
        assert e1 is e2


# ═══════════════════════════════════════════════════════════════════════════════
# 2. PerUserFeatureSelector (was 0% → target 95%+)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPerUserFeatureSelector:
    @pytest.fixture
    def selector(self):
        from app.models.per_user_feature_selector import PerUserFeatureSelector

        return PerUserFeatureSelector(top_n=5)

    def _make_profile(self, n_features=10, base_mean=100):
        return {
            f"feature_{i}": {"mean": base_mean + i * 10, "std": 5.0 + i, "count": 20}
            for i in range(n_features)
        }

    def test_select_features_empty(self, selector):
        result = selector.select_features(1, {})
        assert result["selected_features"] == []
        assert result["selection_quality"] == 0.0

    def test_select_features_with_data(self, selector):
        profile = self._make_profile()
        result = selector.select_features(user_id=1, user_profile=profile)
        assert len(result["selected_features"]) == 5
        assert len(result["feature_weights"]) == 5
        assert abs(sum(result["feature_weights"].values()) - 1.0) < 0.01

    def test_select_features_filters_low_count(self, selector):
        profile = {"f1": {"mean": 50, "std": 5, "count": 1}}  # count < 2
        result = selector.select_features(2, profile)
        assert result["selected_features"] == []

    def test_select_features_filters_zero_mean(self, selector):
        profile = {"f1": {"mean": 0, "std": 5, "count": 5}}
        result = selector.select_features(3, profile)
        assert result["selected_features"] == []

    def test_update_population_stats(self, selector):
        selector.update_population_stats(1, {"f1": 10.0, "f2": 20.0})
        selector.update_population_stats(2, {"f1": 12.0, "f2": 18.0})
        assert selector._population_stats["f1"]["count"] == 2
        assert selector._population_sample_count == 2

    def test_update_population_skips_nan(self, selector):
        selector.update_population_stats(1, {"f1": float("nan"), "f2": 5.0})
        assert "f1" not in selector._population_stats
        assert "f2" in selector._population_stats

    def test_distinctiveness_with_population(self, selector):
        for i in range(5):
            selector.update_population_stats(i, {"f1": 10 + i, "f2": 50 + i * 10})
        profile = {
            "f1": {"mean": 100, "std": 5, "count": 10},
            "f2": {"mean": 55, "std": 5, "count": 10},
        }
        result = selector.select_features(99, profile)
        assert len(result["selected_features"]) > 0

    def test_get_weighted_score_no_selection(self, selector):
        result = selector.get_weighted_score(
            1, {"f1": 10}, {"f1": {"mean": 10, "std": 1, "count": 5}}
        )
        assert "weighted_match_score" in result

    def test_get_weighted_score_good_match(self, selector):
        profile = self._make_profile(n_features=6, base_mean=100)
        selector.select_features(1, profile)
        current = {f"feature_{i}": 100 + i * 10 for i in range(6)}
        result = selector.get_weighted_score(1, current, profile)
        assert result["weighted_match_score"] > 0.5
        assert len(result["anomalous_features"]) == 0

    def test_get_weighted_score_anomaly(self, selector):
        profile = self._make_profile(n_features=6)
        selector.select_features(1, profile)
        current = {f"feature_{i}": 999999 for i in range(6)}
        result = selector.get_weighted_score(1, current, profile)
        assert result["weighted_match_score"] < 0.5
        assert len(result["anomalous_features"]) > 0

    def test_get_weighted_score_empty_profile(self, selector):
        result = selector.get_weighted_score(1, {}, {})
        assert result["weighted_match_score"] == 0.5

    def test_get_weighted_score_nan_values(self, selector):
        profile = self._make_profile(n_features=6)
        selector.select_features(1, profile)
        current = {f"feature_{i}": float("nan") for i in range(6)}
        result = selector.get_weighted_score(1, current, profile)
        assert "weighted_match_score" in result

    def test_invalidate_selection(self, selector):
        profile = self._make_profile()
        selector.select_features(1, profile)
        assert selector.get_user_selection(1) is not None
        selector.invalidate_selection(1)
        assert selector.get_user_selection(1) is None

    def test_singleton(self):
        from app.models.per_user_feature_selector import get_feature_selector

        s1 = get_feature_selector()
        s2 = get_feature_selector()
        assert s1 is s2


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PassiveEnrollmentManager (was 23% → target 95%+)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPassiveEnrollment:
    @pytest.fixture
    def mgr(self):
        from app.models.passive_enrollment import PassiveEnrollmentManager

        return PassiveEnrollmentManager(min_sessions=3, min_samples_per_session=3)

    def _features(self, offset=0):
        return {
            "hold_time_mean": 110 + offset,
            "hold_time_std": 20 + offset,
            "flight_time_mean": 85 + offset,
            "typing_speed_wpm": 55 + offset,
            "velocity_mean": 350 + offset,
            "key_hold_mean": 110 + offset,
        }

    def test_initial_status(self, mgr):
        status = mgr.get_enrollment_status(1)
        assert status["enrolled"] is False
        assert status["enrollment_phase"] == "collecting"
        assert status["sessions_completed"] == 0

    def test_enrollment_flow(self, mgr):
        for i in range(3):
            result = mgr.ingest_session_data(1, keystroke_features=self._features(i))
            if i < 2:
                assert result["action"] == "collecting"
        assert result["action"] == "enrolled"
        assert mgr.get_enrollment_status(1)["enrolled"] is True
        assert mgr.get_enrollment_status(1)["enrollment_phase"] == "active"

    def test_post_enrollment_match(self, mgr):
        for i in range(3):
            mgr.ingest_session_data(1, keystroke_features=self._features(i))
        result = mgr.ingest_session_data(1, keystroke_features=self._features(0))
        assert result["action"] in ("matched", "weak_match", "anomaly")
        assert 0 <= result["match_score"] <= 1

    def test_post_enrollment_anomaly(self, mgr):
        for i in range(3):
            mgr.ingest_session_data(1, keystroke_features=self._features(0))
        anomalous = {k: v * 100 for k, v in self._features(0).items()}
        result = mgr.ingest_session_data(1, keystroke_features=anomalous)
        assert result["action"] in ("anomaly", "weak_match")

    def test_no_data(self, mgr):
        result = mgr.ingest_session_data(1)
        assert result["action"] == "no_data"

    def test_insufficient_data(self, mgr):
        result = mgr.ingest_session_data(1, keystroke_features={"hold_time_mean": 110})
        assert result["action"] == "insufficient_data"

    def test_reset_enrollment(self, mgr):
        for i in range(3):
            mgr.ingest_session_data(1, keystroke_features=self._features(i))
        assert mgr.get_enrollment_status(1)["enrolled"] is True
        mgr.reset_enrollment(1)
        assert mgr.get_enrollment_status(1)["enrolled"] is False

    def test_profile_summary(self, mgr):
        for i in range(3):
            mgr.ingest_session_data(1, keystroke_features=self._features(i))
        summary = mgr.get_profile_summary(1)
        assert summary["enrolled"] is True
        assert summary["feature_count"] > 0
        assert len(summary["top_features"]) > 0

    def test_ready_phase(self, mgr):
        for i in range(3):
            mgr.ingest_session_data(1, keystroke_features=self._features(i))
        mgr._enrollment_status[1] = False
        status = mgr.get_enrollment_status(1)
        assert status["enrollment_phase"] == "ready"

    def test_singleton(self):
        from app.models.passive_enrollment import get_enrollment_manager

        m1 = get_enrollment_manager()
        m2 = get_enrollment_manager()
        assert m1 is m2


# ═══════════════════════════════════════════════════════════════════════════════
# 4. TransactionHistoryBaseline (was 32% → target 95%+)
# ═══════════════════════════════════════════════════════════════════════════════


class TestTransactionBaseline:
    @pytest.fixture
    def baseline(self):
        from app.models.transaction_baseline import TransactionHistoryBaseline

        return TransactionHistoryBaseline()

    def _seed_history(self, baseline, user_id=1, n=10):
        for i in range(n):
            baseline.record_transaction(
                user_id, amount=1000 + i * 100, beneficiary_id=f"bene_{i % 3}"
            )

    def test_record_transaction(self, baseline):
        baseline.record_transaction(1, 5000, "bene_1")
        assert len(baseline._user_history[1]) == 1
        assert "bene_1" in baseline._user_beneficiaries[1]

    def test_record_caps_at_200(self, baseline):
        for i in range(250):
            baseline.record_transaction(1, 100 + i, "bene")
        assert len(baseline._user_history[1]) == 200

    def test_score_no_history(self, baseline):
        result = baseline.score_transaction(1, 5000, "bene_new")
        assert result["transaction_risk"] >= 0
        assert "insufficient_history" in str(result.get("flags", []))

    def test_score_normal_transaction(self, baseline):
        self._seed_history(baseline)
        result = baseline.score_transaction(1, 1200, "bene_0", behavioral_risk=0.1)
        assert result["transaction_risk"] < 0.5
        assert result["amount_risk"] < 0.5

    def test_score_unusual_amount(self, baseline):
        self._seed_history(baseline)
        result = baseline.score_transaction(1, 999999, "bene_0", behavioral_risk=0.1)
        assert result["amount_risk"] > 0.3

    def test_score_new_beneficiary(self, baseline):
        self._seed_history(baseline)
        result = baseline.score_transaction(
            1, 1200, "unknown_bene", behavioral_risk=0.1
        )
        assert result["beneficiary_risk"] > 0

    def test_get_user_profile(self, baseline):
        self._seed_history(baseline)
        profile = baseline.get_user_profile(1)
        assert profile is not None
        assert isinstance(profile, dict)

    def test_get_user_profile_no_history(self, baseline):
        profile = baseline.get_user_profile(99)
        assert profile is not None

    def test_singleton(self):
        from app.models.transaction_baseline import get_txn_baseline

        t1 = get_txn_baseline()
        t2 = get_txn_baseline()
        assert t1 is t2


# ═══════════════════════════════════════════════════════════════════════════════
# 5. InvisibleChallengeEngine (was 45% → target 90%+)
# ═══════════════════════════════════════════════════════════════════════════════


class TestInvisibleChallengeEngine:
    @pytest.fixture
    def engine(self):
        from app.models.invisible_challenge_engine import InvisibleChallengeEngine

        return InvisibleChallengeEngine()

    def test_score_responses_empty(self, engine):
        result = engine.score_responses({})
        assert "challenge_risk" in result
        assert result["challenge_risk"] >= 0

    def test_score_responses_normal(self, engine):
        features = {
            "challenge_count": 5,
            "response_count": 5,
            "correction_time_mean": 200,
            "correction_accuracy_mean": 0.95,
            "subconscious_ratio": 0.9,
            "bot_challenge_score": 0.05,
        }
        result = engine.score_responses(features)
        assert result["challenge_risk"] < 0.5

    def test_score_responses_bot_like(self, engine):
        features = {
            "challenge_count": 5,
            "response_count": 0,
            "correction_time_mean": 10,
            "correction_accuracy_mean": 1.0,
            "subconscious_ratio": 0.0,
            "bot_challenge_score": 0.95,
        }
        result = engine.score_responses(features)
        assert result["challenge_risk"] > 0.3

    def test_score_with_user_id(self, engine):
        features = {
            "challenge_count": 3,
            "response_count": 3,
            "bot_challenge_score": 0.1,
        }
        result = engine.score_responses(features, user_id=42)
        assert isinstance(result, dict)

    def test_singleton(self):
        from app.models.invisible_challenge_engine import get_challenge_engine

        e1 = get_challenge_engine()
        e2 = get_challenge_engine()
        assert e1 is e2


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ExtendedRiskScorer (was 49% → target 90%+)
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtendedRiskScorer:
    @pytest.fixture
    def scorer(self):
        from app.extended_risk_scorer import ExtendedRiskScorer

        return ExtendedRiskScorer()

    def test_score_empty(self, scorer):
        result = scorer.score({})
        assert isinstance(result, dict)

    def test_score_normal_features(self, scorer):
        features = {
            "anomaly_score": 0.1,
            "confidence_score": 0.9,
            "ip_risk": 0.0,
            "device_risk": 0.0,
            "behavioral_distance": 0.1,
        }
        result = scorer.score(features)
        assert isinstance(result, dict)

    def test_score_high_risk(self, scorer):
        features = {
            "anomaly_score": 0.95,
            "confidence_score": 0.1,
            "ip_risk": 0.9,
            "device_risk": 0.8,
            "behavioral_distance": 0.9,
        }
        result = scorer.score(features)
        assert isinstance(result, dict)

    def test_score_with_all_signals(self, scorer):
        features = {
            "anomaly_score": 0.5,
            "confidence_score": 0.5,
            "ip_risk": 0.5,
            "device_risk": 0.5,
            "behavioral_distance": 0.5,
            "geo_velocity_risk": 0.3,
            "session_anomaly": 0.2,
        }
        result = scorer.score(features)
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. DeviceIntelligence (was 57% → target 85%+)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeviceIntelligence:
    @pytest.fixture
    def engine(self):
        from app.models.device_intelligence import DeviceIntelligenceEngine

        return DeviceIntelligenceEngine()

    def test_analyze_empty(self, engine):
        result = engine.analyze({})
        assert "device_risk" in result
        assert 0 <= result["device_risk"] <= 1

    def test_analyze_normal_device(self, engine):
        features = {
            "screen_width": 1920,
            "screen_height": 1080,
            "hardware_concurrency": 8,
            "device_memory": 16,
            "max_touch_points": 0,
            "rat_latency_score": 0.0,
            "emulator_score": 0.0,
        }
        result = engine.analyze(features)
        assert result["device_risk"] < 0.5

    def test_analyze_emulator(self, engine):
        features = {"emulator_score": 0.9, "rat_latency_score": 0.0}
        result = engine.analyze(features)
        assert result["device_risk"] > 0.2

    def test_analyze_rat(self, engine):
        features = {"rat_latency_score": 0.9, "emulator_score": 0.0}
        result = engine.analyze(features)
        assert result["device_risk"] > 0.2

    def test_singleton(self):
        from app.models.device_intelligence import get_device_engine

        d1 = get_device_engine()
        d2 = get_device_engine()
        assert d1 is d2


# ═══════════════════════════════════════════════════════════════════════════════
# 8. ML Ensemble (was 68% → target 90%+)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMLEnsemble:
    def test_score_empty(self):
        from app.ml_ensemble import score_with_ensemble

        result = score_with_ensemble({})
        assert result["ensemble_risk"] >= 0
        assert result["ensemble_action"] in (
            "allow",
            "silent_challenge",
            "step_up",
            "block",
        )

    def test_score_normal_features(self):
        from app.ml_ensemble import score_with_ensemble

        features = {
            "mouse_vel_mean": 350,
            "key_hold_mean": 110,
            "typing_speed_wpm": 55,
            "bot_challenge_score": 0.05,
            "session_duration": 300,
            "hesitation_count": 2,
        }
        result = score_with_ensemble(features, user_id=1)
        assert result["ensemble_risk"] < 1.0
        assert result["cognitive_analysis"] is not None

    def test_score_with_transaction(self):
        from app.ml_ensemble import score_with_ensemble

        result = score_with_ensemble(
            {"mouse_vel_mean": 350},
            user_id=1,
            transaction_amount=5000,
            beneficiary_id="bene_1",
        )
        assert "transaction_risk" in result

    def test_score_with_keystroke_features(self):
        from app.ml_ensemble import score_with_ensemble

        result = score_with_ensemble(
            {"mouse_vel_mean": 350},
            user_id=1,
            keystroke_features={"hold_time_mean": 110, "flight_time_mean": 85},
            mouse_features={"velocity_mean": 350},
        )
        assert "duress_score" in result

    def test_score_with_baseline(self):
        from app.ml_ensemble import score_with_ensemble

        baseline = {
            f"feature_{i}": {"mean": 100 + i, "std": 10, "count": 20} for i in range(10)
        }
        features = {f"feature_{i}": 100 + i for i in range(10)}
        features["mouse_vel_mean"] = 350
        result = score_with_ensemble(features, user_id=1, user_baseline=baseline)
        assert "weighted_match_score" in result

    def test_ensemble_action_levels(self):
        from app.ml_ensemble import score_with_ensemble

        result = score_with_ensemble({})
        assert result["ensemble_action"] in (
            "allow",
            "silent_challenge",
            "step_up",
            "block",
        )
