from cryptography.fernet import Fernet
from datetime import timedelta

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_prefix="",
        extra="ignore",
    )

    # API key (used in .env, must be declared)
    api_key: str = Field(default="")

    # Security headers and policies
    CSP_POLICY: str = "default-src 'self'"
    HSTS_MAX_AGE: int = 31536000
    REFERRER_POLICY: str = "no-referrer"
    # JWT settings
    JWT_SECRET_KEY: str = Field(default="dev-jwt-secret-change-in-production")
    JWT_PREVIOUS_SECRET_KEY: str | None = Field(default=None)
    # IP allow/deny lists
    IP_ALLOWLIST: str = ""
    IP_DENYLIST: str = ""
    # Credential‑stuffing thresholds
    CREDENTIAL_STUFFING_MAX_ATTEMPTS_PER_IP: int = 10
    CREDENTIAL_STUFFING_WINDOW_SECONDS: int = 300
    # Rate limit storage backend (explicit to avoid implicit in-memory warning)
    RATELIMIT_STORAGE_URI: str = "memory://"
    # Backup-code encryption key. MUST be a persistent env var in production —
    # if this changes between restarts, previously encrypted backup codes become
    # unreadable. Generate once with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    BACKUP_FERNET: str = Field(default="")
    # Flask configuration
    SECRET_KEY: str = Field(default="dev-secret-key-change-in-production")
    DEBUG: bool = Field(default=False)
    FLASK_ENV: str = Field(default="development")
    # JWT configuration — 15 minute tokens; continuous auth systems need short-lived access
    JWT_ACCESS_TOKEN_EXPIRES_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRES_DAYS: int = 30
    # Database configuration
    DATABASE_PATH: str = "database/auth_system.db"
    SQLALCHEMY_DATABASE_URI: str | None = None
    # Model configuration
    MODELS_BASE_PATH: str = "models/saved"
    MODEL_RETRAIN_THRESHOLD: float = 0.3
    # Behavioral analysis configuration
    CALIBRATION_MIN_SAMPLES: int = 30
    CALIBRATION_MAX_WAIT_SEC: int = 5
    WINDOW_SIZE: int = 30
    MIN_CALIBRATION_TIME: int = 300
    KEYSTROKE_FEATURES: list[str] = [
        "key_hold_time",
        "flight_time",
        "typing_speed",
        "typing_speed_variance",
        "pause_variance",
        "digraph_timing",
        "trigraph_timing",
        "key_pressure_mean",
        "key_pressure_std",
        "key_impact_velocity",
        "key_release_sharpness",
        "force_consistency",
        "rhythm_consistency",
        "error_correction_speed",
        "segmented_typing_score",
        "data_familiarity_signal",
    ]
    MOUSE_FEATURES: list[str] = [
        "velocity",
        "acceleration",
        "deceleration_rate",
        "jerk",
        "curvature",
        "click_duration",
        "dwell_time",
        "direction_changes",
        "micro_jitter_amp",
        "micro_jitter_freq",
        "target_acquisition_efficiency",
        "visual_motor_coupling",
        "eye_hand_reaction_time",
        "fitts_law_adherence",
    ]
    # ML Model configuration
    GRU_SEQUENCE_LENGTH: int = 50
    GRU_HIDDEN_UNITS: int = 64
    AUTOENCODER_ENCODING_DIM: int = 32
    ANOMALY_THRESHOLD: float = 0.15
    DRIFT_DETECTION_WINDOW: int = 100
    # Authentication thresholds
    CONFIDENCE_THRESHOLD: float = 0.7
    ANOMALY_SCORE_THRESHOLD: float = 0.8
    CONSECUTIVE_ANOMALIES_LIMIT: int = 3
    # WebSocket configuration
    SOCKETIO_CORS_ALLOWED_ORIGINS: str = ""
    SOCKETIO_LOGGER: bool = False
    SOCKETIO_ENGINEIO_LOGGER: bool = False
    # Security configuration
    BCRYPT_LOG_ROUNDS: int = 12
    SESSION_TIMEOUT_HOURS: int = 8
    SESSION_INACTIVITY_TIMEOUT_MINUTES: int = 15  # RBI mandate for netbanking
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15
    CSRF_ENABLED: bool = True
    CSRF_HEADER_NAME: str = "X-CSRF-Token"
    # Feature extraction configuration
    KEYSTROKE_BUFFER_SIZE: int = 1000
    MOUSE_BUFFER_SIZE: int = 2000
    FEATURE_UPDATE_INTERVAL: int = 5
    # Drift detection configuration
    DRIFT_ALPHA: float = 0.05
    DRIFT_MIN_SAMPLES: int = 30
    BEHAVIORAL_CHANGE_THRESHOLD: float = 0.25
    # Risk scoring thresholds
    RISK_HIGH_THRESHOLD: float = 0.65
    RISK_MEDIUM_THRESHOLD: float = 0.35
    # Timeline defaults
    TRUST_TIMELINE_DEFAULT_WINDOW_MINUTES: int = 30
    TRUST_TIMELINE_MAX_WINDOW_MINUTES: int = 180
    SESSION_CONTEXT_STRICT: bool = True
    STEP_UP_RISK_SCORE_THRESHOLD: float = 0.6
    TRANSACTION_SIGNING_REQUIRED: bool = True
    TXN_SIGNING_KEY: str = Field(default="dev-txn-signing-key-change-in-production")
    TXN_SIGNING_PREVIOUS_KEY: str | None = Field(default=None)
    ADMIN_USERNAMES: str = ""
    ANALYST_USERNAMES: str = ""
    REDIS_URL: str = ""
    SESSION_CACHE_TTL_SECONDS: int = 8 * 3600
    CORS_ORIGINS: str = ""

    # ── Email / Transactional Mail ──────────────────────────────────────────
    MAIL_SERVER: str = "localhost"
    MAIL_PORT: int = 587
    MAIL_USE_TLS: bool = True
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_DEFAULT_SENDER: str = "noreply@behaviorauth.local"
    MAIL_BACKEND: str = ""  # 'smtp' | 'ses' | 'console' | 'resend' (auto-detected if blank)
    AWS_REGION: str = "us-east-1"
    RESEND_API_KEY: str = ""
    RESET_URL_BASE: str = "http://localhost:3000/reset-password"

    @field_validator("JWT_SECRET_KEY", mode="before")
    @classmethod
    def ensure_jwt_secret(cls, v, info):
        if not v:
            raise ValueError("JWT_SECRET_KEY must be set in environment")
        if info.data.get("FLASK_ENV") == "production" and v.startswith("dev-"):
            raise ValueError(
                "JWT_SECRET_KEY cannot use a dev default in production. "
                'Generate a secure key: python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        return v

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def ensure_secret(cls, v, info):
        if not v:
            raise ValueError("SECRET_KEY must be set in environment")
        if info.data.get("FLASK_ENV") == "production" and v.startswith("dev-"):
            raise ValueError(
                "SECRET_KEY cannot use a dev default in production. "
                'Generate a secure key: python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def validate_cors_origins(cls, v):
        import warnings

        if v == "*":
            warnings.warn(
                "CORS_ORIGINS=* allows all origins. This is insecure for "
                "production. Set explicit frontend origin(s) instead.",
                stacklevel=2,
            )
        return v

    @field_validator("BACKUP_FERNET", mode="before")
    @classmethod
    def ensure_backup_fernet(cls, v):
        import warnings

        if not v:
            # Auto-generate for dev/test — but warn loudly
            warnings.warn(
                "BACKUP_FERNET is not set. Generating an ephemeral key. "
                "Backup codes encrypted in this session will be UNREADABLE "
                "after a restart. Set BACKUP_FERNET in .env for production.",
                stacklevel=2,
            )
            return Fernet.generate_key().decode()
        return v

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v):
        if isinstance(v, str):
            v_lower = v.lower()
            if v_lower in ("true", "1", "yes", "on"):
                return True
            if v_lower in ("false", "0", "no", "off", "release"):
                return False
        return v

    @field_validator("TXN_SIGNING_KEY", mode="before")
    @classmethod
    def ensure_txn_key(cls, v, info):
        if info.data.get("FLASK_ENV") == "production" and v.startswith("dev-"):
            raise ValueError(
                "TXN_SIGNING_KEY cannot use a dev default in production. "
                'Generate a secure key: python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        return v

    @field_validator("RATELIMIT_STORAGE_URI", mode="before")
    @classmethod
    def enforce_redis(cls, v, info):
        if info.data.get("FLASK_ENV") == "production" and (not v or "memory" in v):
            raise ValueError("RATELIMIT_STORAGE_URI must be set to Redis in production")
        return v

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    @classmethod
    def enforce_postgres(cls, v, info):
        if info.data.get("FLASK_ENV") == "production":
            if not v or "sqlite" in v:
                raise ValueError(
                    "SQLite is not suitable for production multi-instance deployments. "
                    "Set SQLALCHEMY_DATABASE_URI to a PostgreSQL cluster."
                )
        return v

    def init_app(self, app):
        """Initialize Flask app with settings"""
        app.config.update(
            {
                "SECRET_KEY": self.SECRET_KEY,
                "DEBUG": self.DEBUG,
                "CSP_POLICY": self.CSP_POLICY,
                "HSTS_MAX_AGE": self.HSTS_MAX_AGE,
                "REFERRER_POLICY": self.REFERRER_POLICY,
                "JWT_SECRET_KEY": self.JWT_SECRET_KEY,
                "JWT_ACCESS_TOKEN_EXPIRES": timedelta(
                    minutes=self.JWT_ACCESS_TOKEN_EXPIRES_MINUTES
                ),
                "JWT_REFRESH_TOKEN_EXPIRES": timedelta(
                    days=self.JWT_REFRESH_TOKEN_EXPIRES_DAYS
                ),
                "SQLALCHEMY_DATABASE_URI": self.SQLALCHEMY_DATABASE_URI
                or f"sqlite:///{self.DATABASE_PATH}",
                "MAIL_SERVER": self.MAIL_SERVER,
                "MAIL_PORT": self.MAIL_PORT,
                "MAIL_USE_TLS": self.MAIL_USE_TLS,
                "MAIL_USERNAME": self.MAIL_USERNAME,
                "MAIL_PASSWORD": self.MAIL_PASSWORD,
                "MAIL_DEFAULT_SENDER": self.MAIL_DEFAULT_SENDER,
                "MAIL_BACKEND": self.MAIL_BACKEND,
                "AWS_REGION": self.AWS_REGION,
                "RESET_URL_BASE": self.RESET_URL_BASE,
                "RESEND_API_KEY": getattr(self, "RESEND_API_KEY", ""),
            }
        )
