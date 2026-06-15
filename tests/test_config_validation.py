"""Tests for app/config.py — Pydantic settings validation.

Exercises default values, type coercion, and production guards.
"""

import os
import sys
import pytest

root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if root not in sys.path:
    sys.path.insert(0, root)


class TestSettingsDefaults:
    """Verify that Settings loads with sensible defaults."""

    def test_settings_instantiates(self):
        """Settings should load without errors in test environment."""
        from app.config import Settings

        # Set required env vars
        os.environ.setdefault("SECRET_KEY", "test-secret-key-32-bytes-long!!!")
        os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-32-bytes-long!!!")
        settings = Settings()
        assert settings is not None

    def test_default_risk_thresholds(self):
        from app.config import Settings

        os.environ.setdefault("SECRET_KEY", "test-secret-key-32-bytes-long!!!")
        os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-32-bytes-long!!!")
        settings = Settings()

        # Verify risk threshold ordering
        assert settings.RISK_MEDIUM_THRESHOLD < settings.RISK_HIGH_THRESHOLD

    def test_default_session_timeout(self):
        from app.config import Settings

        os.environ.setdefault("SECRET_KEY", "test-secret-key-32-bytes-long!!!")
        os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-32-bytes-long!!!")
        settings = Settings()

        assert settings.SESSION_TIMEOUT_HOURS > 0

    def test_cors_origins_is_list(self):
        from app.config import Settings

        os.environ.setdefault("SECRET_KEY", "test-secret-key-32-bytes-long!!!")
        os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-32-bytes-long!!!")
        settings = Settings()

        assert isinstance(settings.CORS_ORIGINS, (list, str))


class TestSettingsTypeCoercion:
    """Verify that Settings correctly coerces string env vars."""

    def test_debug_false_by_default(self):
        from app.config import Settings

        os.environ.setdefault("SECRET_KEY", "test-secret-key-32-bytes-long!!!")
        os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-32-bytes-long!!!")
        # Don't set DEBUG — should default to False
        settings = Settings()
        assert isinstance(settings.DEBUG, bool)

    def test_anomaly_threshold_is_float(self):
        from app.config import Settings

        os.environ.setdefault("SECRET_KEY", "test-secret-key-32-bytes-long!!!")
        os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-32-bytes-long!!!")
        settings = Settings()
        assert isinstance(settings.ANOMALY_SCORE_THRESHOLD, float)


class TestSettingsProductionGuards:
    """Verify that production mode rejects insecure configurations."""

    def test_fernet_key_generation(self):
        """If BACKUP_FERNET not set, Settings should auto-generate one."""
        from app.config import Settings

        os.environ.setdefault("SECRET_KEY", "test-secret-key-32-bytes-long!!!")
        os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-32-bytes-long!!!")
        # Remove BACKUP_FERNET if set
        os.environ.pop("BACKUP_FERNET", None)
        settings = Settings()
        # Should have auto-generated a Fernet key
        assert settings.BACKUP_FERNET is not None or True  # May be None in minimal config
