"""
Tests for Phase 4 production-readiness features:
- Audit hash-chain verification
- ConsentManager with DB persistence
- CBS CircuitBreaker
"""

import pytest
import time

from app.database import DatabaseManager
from app.compliance import ConsentManager
from app.banking.cbs_adapters import (
    CircuitBreaker,
    CircuitState,
    ExternalCallError,
    FinacleAdapter,
)


# ═══════════════════════════════════════════════════════════════════════════
#  Audit Chain Verification
# ═══════════════════════════════════════════════════════════════════════════


class TestAuditChainVerification:
    """Verify the tamper-evident SHA-256 hash chain."""

    @pytest.fixture(autouse=True)
    def db(self):
        self.db = DatabaseManager(":memory:")
        yield self.db

    def test_empty_chain_is_valid(self):
        result = self.db.verify_audit_chain()
        assert result["is_valid"] is True
        assert result["total_records"] == 0

    def test_single_entry_verifies(self):
        self.db.log_audit_evidence(action="login", status="ok", user_id=1)
        result = self.db.verify_audit_chain()
        assert result["is_valid"] is True
        assert result["verified_count"] == 1

    def test_multiple_entries_verify(self):
        for i in range(10):
            self.db.log_audit_evidence(
                action=f"action_{i}",
                status="ok",
                user_id=1,
                metadata={"step": i},
            )
        result = self.db.verify_audit_chain()
        assert result["is_valid"] is True
        assert result["verified_count"] == 10

    def test_tampered_entry_detected(self):
        for i in range(5):
            self.db.log_audit_evidence(action=f"action_{i}", status="ok", user_id=1)

        # Tamper with the middle record
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE audit_evidence SET action = 'TAMPERED' WHERE evidence_id = 3"
            )
            conn.commit()

        result = self.db.verify_audit_chain()
        assert result["is_valid"] is False
        assert result["first_broken_id"] == 3
        assert "tampered" in result["error"].lower()

    def test_deleted_entry_detected(self):
        for i in range(5):
            self.db.log_audit_evidence(action=f"action_{i}", status="ok", user_id=1)

        # Delete a record, breaking the chain linkage
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM audit_evidence WHERE evidence_id = 2")
            conn.commit()

        result = self.db.verify_audit_chain()
        assert result["is_valid"] is False
        assert "prev_hash mismatch" in result["error"]


# ═══════════════════════════════════════════════════════════════════════════
#  ConsentManager Persistence
# ═══════════════════════════════════════════════════════════════════════════


class TestConsentManagerPersistence:
    """Test ConsentManager with database-backed persistence."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.db = DatabaseManager(":memory:")
        self.cm = ConsentManager(db=self.db)

    def test_record_consent_persists(self):
        record = self.cm.record_consent(
            user_id=1,
            purposes=["keystroke_dynamics_analysis", "fraud_detection"],
        )
        assert record["status"] == "active"
        assert len(record["purposes"]) == 2

        # Verify persisted in DB
        db_record = self.db.get_consent(1)
        assert db_record is not None
        assert db_record["status"] == "active"
        assert "keystroke_dynamics_analysis" in db_record["purposes"]

    def test_check_consent_reads_from_db(self):
        self.cm.record_consent(user_id=1, purposes=["fraud_detection"])
        assert self.cm.check_consent(1, "fraud_detection") is True
        assert self.cm.check_consent(1, "risk_scoring") is False

    def test_withdraw_consent_full(self):
        self.cm.record_consent(user_id=1, purposes=["fraud_detection", "risk_scoring"])
        result = self.cm.withdraw_consent(user_id=1)
        assert result["status"] == "withdrawn"
        assert self.cm.check_consent(1, "fraud_detection") is False

    def test_withdraw_consent_partial(self):
        self.cm.record_consent(user_id=1, purposes=["fraud_detection", "risk_scoring"])
        result = self.cm.withdraw_consent(user_id=1, purposes=["fraud_detection"])
        assert result["status"] == "partial"
        assert self.cm.check_consent(1, "risk_scoring") is True
        assert self.cm.check_consent(1, "fraud_detection") is False

    def test_consent_status_reflects_db(self):
        self.cm.record_consent(user_id=1, purposes=["fraud_detection"])
        status = self.cm.get_consent_status(1)
        assert status["has_consent"] is True
        assert status["status"] == "active"
        assert "fraud_detection" in status["purposes"]

    def test_withdraw_nonexistent_user(self):
        result = self.cm.withdraw_consent(user_id=999)
        assert "error" in result

    def test_invalid_purposes_filtered(self):
        record = self.cm.record_consent(
            user_id=1,
            purposes=["fraud_detection", "invalid_purpose"],
        )
        assert "invalid_purpose" not in record["purposes"]
        assert "fraud_detection" in record["purposes"]

    def test_consent_without_db_uses_memory(self):
        cm = ConsentManager(db=None)
        cm.record_consent(user_id=1, purposes=["fraud_detection"])
        assert cm.check_consent(1, "fraud_detection") is True


# ═══════════════════════════════════════════════════════════════════════════
#  Circuit Breaker
# ═══════════════════════════════════════════════════════════════════════════


class TestCircuitBreaker:
    """Test the CBS circuit breaker state machine."""

    def test_starts_closed(self):
        cb = CircuitBreaker(failure_threshold=3, cooldown_s=1.0)
        assert cb.state == CircuitState.CLOSED

    def test_success_keeps_closed(self):
        cb = CircuitBreaker(failure_threshold=3)
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(failure_threshold=3, cooldown_s=60.0)

        def failing():
            raise ConnectionError("down")

        for _ in range(3):
            with pytest.raises(ConnectionError):
                cb.call(failing)

        assert cb.state == CircuitState.OPEN

    def test_open_rejects_calls(self):
        cb = CircuitBreaker(failure_threshold=1, cooldown_s=60.0)

        with pytest.raises(ConnectionError):
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("down")))

        assert cb.state == CircuitState.OPEN

        with pytest.raises(ExternalCallError, match="Circuit breaker OPEN"):
            cb.call(lambda: "should not run")

    def test_half_open_after_cooldown(self):
        cb = CircuitBreaker(failure_threshold=1, cooldown_s=0.1)

        with pytest.raises(ConnectionError):
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("down")))

        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)

        # After cooldown, next call transitions to HALF_OPEN then succeeds
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(failure_threshold=1, cooldown_s=0.1)

        with pytest.raises(ConnectionError):
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("down")))

        time.sleep(0.15)

        with pytest.raises(ConnectionError):
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("still down")))

        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3, cooldown_s=60.0)

        # 2 failures, then a success
        for _ in range(2):
            with pytest.raises(ConnectionError):
                cb.call(lambda: (_ for _ in ()).throw(ConnectionError("flaky")))

        cb.call(lambda: "ok")
        assert cb._failure_count == 0
        assert cb.state == CircuitState.CLOSED

    def test_adapter_has_breaker(self):
        adapter = FinacleAdapter()
        assert hasattr(adapter, "breaker")
        assert adapter.breaker.state == CircuitState.CLOSED

    def test_health_check_includes_breaker_state(self):
        adapter = FinacleAdapter()
        health = adapter.health_check()
        assert "circuit_breaker" in health
        assert health["circuit_breaker"] == "closed"


# ═══════════════════════════════════════════════════════════════════════════
#  ML Ensemble Integration
# ═══════════════════════════════════════════════════════════════════════════


class TestMLEnsemble:
    """Test the unified ML ensemble scoring layer."""

    def test_ensemble_returns_complete_structure(self):
        from app.ml_ensemble import score_with_ensemble

        result = score_with_ensemble(extended_features={})
        assert "ensemble_risk" in result
        assert "cognitive_analysis" in result
        assert "duress_score" in result
        assert "liveness_score" in result
        assert "ensemble_action" in result
        assert "ensemble_flags" in result
        assert isinstance(result["ensemble_flags"], list)

    def test_ensemble_with_empty_features(self):
        from app.ml_ensemble import score_with_ensemble

        result = score_with_ensemble(extended_features={})
        assert 0.0 <= result["ensemble_risk"] <= 1.0
        assert result["ensemble_action"] in {
            "allow",
            "step_up",
            "block",
            "silent_challenge",
        }

    def test_ensemble_with_high_risk_features(self):
        from app.ml_ensemble import score_with_ensemble

        # Features that should trigger high cognitive risk
        result = score_with_ensemble(
            extended_features={
                "copy_paste_count": 5,
                "tab_switch_count": 8,
                "hesitation_count": 10,
                "hesitation_duration_mean": 5000,
                "rapid_submit_detected": 1,
                "correction_rate": 0.6,
            },
        )
        assert result["ensemble_risk"] > 0.0
        assert result["cognitive_analysis"] is not None

    def test_ensemble_cognitive_analysis_populated(self):
        from app.ml_ensemble import score_with_ensemble

        result = score_with_ensemble(
            extended_features={"copy_paste_count": 1},
        )
        cog = result["cognitive_analysis"]
        assert cog is not None
        assert "duress_probability" in cog
        assert "app_fraud_probability" in cog
        assert "cognitive_risk" in cog
        assert "behavioral_state" in cog

    def test_ensemble_liveness_score_range(self):
        from app.ml_ensemble import score_with_ensemble

        result = score_with_ensemble(extended_features={"motion_event_count": 20})
        assert 0.0 <= result["liveness_score"] <= 1.0

    def test_ensemble_handles_none_features(self):
        from app.ml_ensemble import score_with_ensemble

        result = score_with_ensemble(extended_features=None)
        # With no input features, ensemble returns a small baseline risk
        # from default weights; the key thing is it doesn't crash
        # and action remains "allow" (risk < 0.3).
        assert 0.0 <= result["ensemble_risk"] < 0.3
        assert result["ensemble_action"] == "allow"


# ═══════════════════════════════════════════════════════════════════════════
#  Concurrency / Stress Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestConcurrency:
    """Basic concurrency tests for database thread-safety.

    Uses file-based SQLite (not :memory:) because the production code creates
    per-thread connections for file DBs, while :memory: reuses a single
    connection that is not thread-safe.
    """

    def test_concurrent_audit_writes(self, tmp_path):
        """Multiple threads writing audit evidence should not corrupt data."""
        import threading

        db = DatabaseManager(str(tmp_path / "test_concurrent.db"))
        errors = []

        def write_entries(thread_id):
            try:
                for i in range(10):
                    db.log_audit_evidence(
                        action=f"thread_{thread_id}_action_{i}",
                        status="ok",
                        user_id=thread_id,
                        metadata={"thread": thread_id, "seq": i},
                    )
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=write_entries, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Thread errors: {errors}"

        # All entries should exist
        with db.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) as c FROM audit_evidence").fetchone()[
                "c"
            ]
        assert count == 50

    def test_concurrent_consent_writes(self, tmp_path):
        """Multiple users recording consent concurrently."""
        import threading

        db = DatabaseManager(str(tmp_path / "test_consent.db"))
        errors = []

        def record_consent(user_id):
            try:
                cm = ConsentManager(db=db)
                cm.record_consent(user_id=user_id, purposes=["fraud_detection"])
            except Exception as exc:
                errors.append(str(exc))

        threads = [
            threading.Thread(target=record_consent, args=(u,)) for u in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Thread errors: {errors}"

    def test_concurrent_reads_during_writes(self, tmp_path):
        """Reading behavioral data while writing concurrently."""
        import threading

        db = DatabaseManager(str(tmp_path / "test_rw.db"))
        db.create_user("concurrency_user", "test@test.com", "TestPass123!")
        errors = []

        def write_behavioral(user_id):
            try:
                for _ in range(10):
                    db.store_behavioral_data(
                        user_id=user_id,
                        session_id="sess-1",
                        data_type="keystroke",
                        features={"test": True},
                        raw_data={},
                        confidence_score=1.0,
                    )
            except Exception as exc:
                errors.append(f"write: {exc}")

        def read_behavioral(user_id):
            try:
                for _ in range(10):
                    db.get_user_behavioral_data(user_id=user_id, limit=10)
            except Exception as exc:
                errors.append(f"read: {exc}")

        threads = [
            threading.Thread(target=write_behavioral, args=(1,)),
            threading.Thread(target=write_behavioral, args=(1,)),
            threading.Thread(target=read_behavioral, args=(1,)),
            threading.Thread(target=read_behavioral, args=(1,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Thread errors: {errors}"
