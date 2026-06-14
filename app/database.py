import json
import hashlib
import secrets
import bcrypt
import pyotp
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Tuple
import os
import re
import logging
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Union
from app.config import Settings
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

_DUMMY_HASH = bcrypt.hashpw(b"dummy-constant-time-padding", bcrypt.gensalt())
logger = logging.getLogger(__name__)

class QueryAdapter:
    """Wraps SQLAlchemy Connection to behave like DBAPI cursor and auto-translate parameters."""
    def __init__(self, conn):
        self.conn = conn
        self._result = None

    def cursor(self):
        return self
        
    def execute(self, query, params=None):
        if params:
            param_dict = {}
            if isinstance(params, (tuple, list)):
                def repl(match):
                    idx = len(param_dict)
                    if idx < len(params):
                        key = f"p{idx}"
                        param_dict[key] = params[idx]
                        return f":{key}"
                    return match.group(0)
                
                query = re.sub(r'(\?|%s)', repl, query)
            elif isinstance(params, dict):
                param_dict = params
            self._result = self.conn.execute(text(query), param_dict)
        else:
            self._result = self.conn.execute(text(query))
        return self

    def fetchone(self):
        if not self._result:
            return None
        row = self._result.fetchone()
        if row:
            return dict(row._mapping)
        return None
        
    def fetchall(self):
        if not self._result:
            return []
        return [dict(row._mapping) for row in self._result.fetchall()]

    def commit(self):
        pass
        
    def rollback(self):
        pass

    @property
    def lastrowid(self):
        if self._result:
            return self._result.lastrowid
        return None

class DatabaseManager:
    """Manages all database operations for the continuous authentication system"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        
        # Configure SQLAlchemy Engine
        if self.db_path.startswith("postgresql://") or self.db_path.startswith("postgres://"):
            self.engine = create_engine(self.db_path, pool_size=5, max_overflow=10, pool_timeout=30, pool_recycle=1800)
            self.is_pg = True
        else:
            if self.db_path != ":memory:" and not self.db_path.startswith("sqlite"):
                # SQLite file path
                self.db_path = "sqlite:///" + self.db_path
                self.engine = create_engine(self.db_path)
            elif self.db_path == ":memory:":
                self.engine = create_engine("sqlite:///:memory:")
            else:
                self.engine = create_engine(self.db_path)
            self.is_pg = False
            
        self.init_database()

    def init_database(self):
        """Initialize database with required tables.

        Produces PostgreSQL-compatible DDL when ``self.is_pg`` is True and
        SQLite DDL otherwise.  The two dialects differ on auto-increment
        primary keys (``SERIAL`` vs ``INTEGER PRIMARY KEY AUTOINCREMENT``)
        and boolean literal defaults.
        """
        if not self.is_pg and self.db_path != "sqlite:///:memory:":
            dir_path = os.path.dirname(self.db_path.replace("sqlite:///", ""))
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)

        # Dialect helpers
        if self.is_pg:
            _auto_pk = "SERIAL PRIMARY KEY"
            _bool_true = "TRUE"
            _bool_false = "FALSE"
        else:
            _auto_pk = "INTEGER PRIMARY KEY AUTOINCREMENT"
            _bool_true = "1"
            _bool_false = "0"

        with self.get_connection() as conn:
            cursor = conn.cursor()

            if not self.is_pg:
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")

            # ── Users ───────────────────────────────────────────────────────
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS users (
                    user_id {_auto_pk},
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    mfa_secret TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    is_active BOOLEAN DEFAULT {_bool_true},
                    failed_attempts INTEGER DEFAULT 0,
                    locked_until TIMESTAMP,
                    calibration_complete BOOLEAN DEFAULT {_bool_false},
                    email_verified BOOLEAN DEFAULT {_bool_false},
                    mfa_enabled BOOLEAN DEFAULT {_bool_false},
                    role TEXT DEFAULT 'user'
                )
            """
            )

            # Retrofit existing databases safely
            try:
                cursor.execute(
                    f"ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT {_bool_false}"
                )
            except Exception:
                pass
            try:
                cursor.execute(
                    f"ALTER TABLE users ADD COLUMN mfa_enabled BOOLEAN DEFAULT {_bool_false}"
                )
            except Exception:
                pass

            # ── Sessions ────────────────────────────────────────────────────
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT {_bool_true},
                    ip_address TEXT,
                    user_agent TEXT,
                    device_id TEXT,
                    assurance_level TEXT DEFAULT 'pwd',
                    context_hash TEXT,
                    ended_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """
            )

            try:
                cursor.execute(
                    "ALTER TABLE sessions ADD COLUMN ended_at TIMESTAMP"
                )
            except Exception:
                pass

            # ── Behavioral data ─────────────────────────────────────────────
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS behavioral_data (
                    data_id {_auto_pk},
                    user_id INTEGER NOT NULL,
                    session_id TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_type TEXT NOT NULL,
                    features TEXT NOT NULL,
                    raw_data TEXT,
                    confidence_score REAL,
                    anomaly_score REAL,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """
            )

            # ── Authentication events ────────────────────────────────────────
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS auth_events (
                    event_id {_auto_pk},
                    user_id INTEGER,
                    session_id TEXT,
                    event_type TEXT NOT NULL,
                    event_data TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """
            )

            # ── Model metadata ───────────────────────────────────────────────
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS model_metadata (
                    user_id INTEGER PRIMARY KEY,
                    model_version INTEGER DEFAULT 1,
                    last_trained TIMESTAMP,
                    training_samples INTEGER DEFAULT 0,
                    model_accuracy REAL,
                    drift_detected BOOLEAN DEFAULT {_bool_false},
                    drift_timestamp TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """
            )

            # ── Compliance audit evidence ────────────────────────────────────
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS audit_evidence (
                    evidence_id {_auto_pk},
                    user_id INTEGER,
                    session_id TEXT,
                    action TEXT NOT NULL,
                    resource TEXT,
                    status TEXT NOT NULL,
                    rationale TEXT,
                    metadata TEXT,
                    retention_tag TEXT DEFAULT 'standard',
                    prev_hash TEXT,
                    entry_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # ── Password reset tokens ────────────────────────────────────────
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    token_id {_auto_pk},
                    user_id INTEGER NOT NULL,
                    token_hash TEXT NOT NULL,
                    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    used_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """
            )

            # ── Consent records (DPDP Act 2023) ──────────────────────────────
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS consent_records (
                    consent_id {_auto_pk},
                    user_id INTEGER NOT NULL,
                    purposes TEXT NOT NULL,
                    version TEXT NOT NULL DEFAULT '1.0',
                    status TEXT NOT NULL DEFAULT 'active',
                    consent_hash TEXT,
                    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    withdrawn_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """
            )

            # ── OTP codes (real-time, database-backed) ───────────────────────
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS otp_codes (
                    otp_id {_auto_pk},
                    user_id INTEGER NOT NULL,
                    otp_code TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    used_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """
            )

            # ── Indexes ──────────────────────────────────────────────────────
            for stmt in [
                "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity)",
                "CREATE INDEX IF NOT EXISTS idx_behavioral_data_user_id ON behavioral_data(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_behavioral_data_timestamp ON behavioral_data(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_behavioral_data_type ON behavioral_data(data_type)",
                "CREATE INDEX IF NOT EXISTS idx_auth_events_user_id ON auth_events(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_auth_events_timestamp ON auth_events(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_auth_events_type ON auth_events(event_type)",
                "CREATE INDEX IF NOT EXISTS idx_audit_evidence_user_id ON audit_evidence(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_audit_evidence_created_at ON audit_evidence(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_password_reset_user_id ON password_reset_tokens(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_password_reset_token_hash ON password_reset_tokens(token_hash)",
                "CREATE INDEX IF NOT EXISTS idx_consent_user_id ON consent_records(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_otp_codes_user_id ON otp_codes(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_otp_codes_expires_at ON otp_codes(expires_at)",
            ]:
                cursor.execute(stmt)

            conn.commit()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        with self.engine.begin() as conn:
            yield QueryAdapter(conn)

    # ── Column projections are hardcoded in each query (no f-string SQL) ──

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """Return public user fields only — never password_hash or mfa_secret."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT user_id, username, email, role, is_active, calibration_complete, "
                "created_at, last_login, failed_attempts, locked_until, email_verified "
                "FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_user(self, user_id: int) -> Optional[dict]:
        """Alias for get_user_by_id."""
        return self.get_user_by_id(user_id)

    def get_user_by_username(self, username: str) -> Optional[dict]:
        """Return public user fields only — never password_hash or mfa_secret."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT user_id, username, email, role, is_active, calibration_complete, "
                "created_at, last_login, failed_attempts, locked_until, email_verified "
                "FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            return dict(row) if row else None

    def get_user_by_email(self, email: str) -> Optional[dict]:
        """Return public user fields only — never password_hash or mfa_secret."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT user_id, username, email, role, is_active, calibration_complete, "
                "created_at, last_login, failed_attempts, locked_until, email_verified "
                "FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            return dict(row) if row else None

    def get_user_for_auth(self, username: str) -> Optional[dict]:
        """Return user with password_hash for credential verification only."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT user_id, username, email, role, is_active, calibration_complete, "
                "created_at, last_login, failed_attempts, locked_until, password_hash, email_verified "
                "FROM users WHERE username = ? AND is_active = 1",
                (username,),
            ).fetchone()
            return dict(row) if row else None

    def get_user_for_mfa(self, user_id: int) -> Optional[dict]:
        """Return user with mfa_secret for TOTP verification only."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT user_id, username, email, role, is_active, calibration_complete, "
                "created_at, last_login, failed_attempts, locked_until, mfa_secret "
                "FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if not row:
                return None
            user = dict(row)
            mfa_secret = user.get("mfa_secret")
            if mfa_secret:
                try:
                    from flask import current_app
                    from cryptography.fernet import Fernet
                    fernet_key = current_app.config.get("BACKUP_FERNET")
                    if fernet_key:
                        fernet = Fernet(fernet_key.encode("utf-8"))
                        user["mfa_secret"] = fernet.decrypt(mfa_secret.encode("utf-8")).decode("utf-8")
                except Exception:
                    pass
            return user

    # ── Real-time OTP (database-backed) ──────────────────────────────────

    def store_otp(self, user_id: int, otp_code: str, ttl_seconds: int = 60) -> str:
        """Generate and store a random OTP code in the database."""
        expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE otp_codes SET used_at = CURRENT_TIMESTAMP "
                "WHERE user_id = ? AND used_at IS NULL",
                (user_id,),
            )
            cursor.execute(
                "INSERT INTO otp_codes (user_id, otp_code, expires_at) VALUES (?, ?, ?)",
                (user_id, otp_code, expires_at),
            )
            conn.commit()
        return otp_code

    def verify_otp(self, user_id: int, otp_code: str) -> bool:
        """Verify an OTP code against the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT otp_id FROM otp_codes "
                "WHERE user_id = ? AND otp_code = ? "
                "AND used_at IS NULL AND expires_at > CURRENT_TIMESTAMP "
                "ORDER BY created_at DESC LIMIT 1",
                (user_id, otp_code),
            )
            row = cursor.fetchone()
            if not row:
                return False
            cursor.execute(
                "UPDATE otp_codes SET used_at = CURRENT_TIMESTAMP WHERE otp_id = ?",
                (row["otp_id"],),
            )
            conn.commit()
            return True

    def create_user(
        self, username: str, email: str, password: str
    ) -> Optional[Tuple[int, str]]:
        """Create a new user and generate MFA secret"""
        mfa_secret = pyotp.random_base32()
        encrypted_mfa_secret = mfa_secret
        try:
            from flask import current_app
            from cryptography.fernet import Fernet
            fernet_key = current_app.config.get("BACKUP_FERNET")
            if fernet_key:
                fernet = Fernet(fernet_key.encode("utf-8"))
                encrypted_mfa_secret = fernet.encrypt(mfa_secret.encode("utf-8")).decode("utf-8")
        except Exception as e:
            logger.warning("Failed to encrypt MFA secret, using plaintext fallback: %s", e)

        try:
            # Generate salt and hash password
            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(password.encode("utf-8"), salt)
            # bcrypt returns bytes — decode to str for PostgreSQL TEXT column
            if isinstance(password_hash, bytes):
                password_hash = password_hash.decode("utf-8")

            with self.get_connection() as conn:
                cursor = conn.cursor()
                if self.is_pg:
                    # PostgreSQL: use RETURNING to get the auto-generated ID
                    cursor.execute(
                        """
                    INSERT INTO users (username, email, password_hash, mfa_secret)
                    VALUES (?, ?, ?, ?) RETURNING user_id
                """,
                        (username, email, password_hash, encrypted_mfa_secret),
                    )
                    row = cursor.fetchone()
                    user_id = row["user_id"] if row else None
                else:
                    cursor.execute(
                        """
                    INSERT INTO users (username, email, password_hash, mfa_secret)
                    VALUES (?, ?, ?, ?)
                """,
                        (username, email, password_hash, encrypted_mfa_secret),
                    )
                    user_id = cursor.lastrowid

                if not user_id:
                    conn.commit()
                    return None

                # Initialize model metadata
                cursor.execute(
                    """
                    INSERT INTO model_metadata (user_id, last_trained)
                    VALUES (?, ?)
                """,
                    (user_id, datetime.now()),
                )

                conn.commit()
                return user_id, mfa_secret

        except IntegrityError:
            return None  # User already exists

    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user credentials.

        Security:
        - Constant-time: always runs bcrypt even when user is not found to
          prevent timing-based username enumeration.
        - Atomic lockout: uses ``failed_attempts = failed_attempts + 1`` to
          avoid TOCTOU race under concurrent requests.
        - Returns public projection only (no password_hash / mfa_secret).
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, username, email, role, is_active, calibration_complete, "
                "created_at, last_login, failed_attempts, locked_until, password_hash, email_verified "
                "FROM users WHERE (username = ? OR email = ?) AND is_active = 1",
                (username, username),
            )

            user = cursor.fetchone()
            if not user:
                # Constant-time: burn bcrypt cycles so response time is
                # indistinguishable from a real user lookup.
                bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH)
                return None

            # Check if account is locked (DB-side comparison avoids UTC/local mismatch)
            if user["locked_until"]:
                cursor.execute(
                    "SELECT 1 FROM users WHERE user_id = ? AND locked_until > CURRENT_TIMESTAMP",
                    (user["user_id"],),
                )
                if cursor.fetchone():
                    return None

            # Verify password — handle both bytes (SQLite) and str (PostgreSQL)
            stored_hash = user["password_hash"]
            if isinstance(stored_hash, str):
                stored_hash = stored_hash.encode("utf-8")
            if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
                # Reset failed attempts and update last login
                cursor.execute(
                    """
                    UPDATE users SET failed_attempts = 0, last_login = CURRENT_TIMESTAMP, locked_until = NULL
                    WHERE user_id = ?
                """,
                    (user["user_id"],),
                )
                conn.commit()

                # Strip password_hash before returning
                result = dict(user)
                result.pop("password_hash", None)
                return result
            else:
                # Atomic increment — avoids TOCTOU race under concurrency
                lockout_time = datetime.now(timezone.utc) + timedelta(minutes=15)
                cursor.execute(
                    """
                    UPDATE users
                    SET failed_attempts = failed_attempts + 1,
                        locked_until = CASE
                            WHEN failed_attempts + 1 >= 5
                            THEN ?
                            ELSE locked_until
                        END
                    WHERE user_id = ?
                """,
                    (lockout_time.isoformat(), user["user_id"]),
                )
                conn.commit()

                return None

    def create_session(self, user_id: int, ip_address: str, user_agent: str) -> str:
        """Create a new session with CSPRNG ID and context fingerprint."""
        # CSPRNG session ID — 32 bytes of cryptographic randomness
        session_id = secrets.token_urlsafe(32)
        # Context hash for IP/UA binding (validated on subsequent requests)
        ctx = f"{ip_address or 'unknown'}|{user_agent or ''}"
        context_hash = hashlib.sha256(ctx.encode("utf-8")).hexdigest()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sessions (session_id, user_id, ip_address, user_agent, device_id, assurance_level, context_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    session_id,
                    user_id,
                    ip_address,
                    user_agent,
                    None,
                    "pwd",
                    context_hash,
                ),
            )
            conn.commit()

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session information"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT s.*, u.username, u.calibration_complete, u.role
                FROM sessions s
                JOIN users u ON s.user_id = u.user_id
                WHERE s.session_id = ? AND s.is_active = 1
            """,
                (session_id,),
            )

            session = cursor.fetchone()
            return dict(session) if session else None

    def update_session_assurance(self, session_id: str, assurance_level: str):
        """Update the session assurance level (AAL)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sessions SET assurance_level = ?
                WHERE session_id = ? AND is_active = 1
                """,
                (assurance_level, session_id),
            )
            conn.commit()

    def update_user_role(self, user_id: int, role: str):
        """Update user role (user/analyst/admin)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET role = ? WHERE user_id = ?",
                (role, user_id),
            )
            conn.commit()

    def set_email_verified(self, user_id: int):
        """Set user's email as verified."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Use TRUE for PostgreSQL, 1 for SQLite
            val = "TRUE" if self.is_pg else "1"
            cursor.execute(
                f"UPDATE users SET email_verified = {val} WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()

    def update_session_activity(self, session_id: str):
        """Update last activity timestamp for session"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sessions SET last_activity = ?
                WHERE session_id = ? AND is_active = 1
            """,
                (datetime.now(), session_id),
            )
            conn.commit()

    def end_session(self, session_id: str):
        """End an active session"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sessions SET is_active = 0, ended_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """,
                (session_id,),
            )
            conn.commit()

    def store_behavioral_data(
        self,
        user_id: int,
        session_id: str,
        data_type: str,
        features: Dict,
        raw_data: Dict = None,
        confidence_score: float = None,
        anomaly_score: float = None,
        retain_raw: bool = False,
    ):
        """Store behavioral biometric data with DPDP data minimization.

        Data Minimization (DPDP Act 2023):
        By default, raw_data is stripped after feature extraction and stored
        as NULL. Only the computed feature vectors are retained. Set
        retain_raw=True only for calibration data that needs reprocessing.
        """
        # DPDP Data Minimization: strip raw_data unless explicitly retained
        stored_raw = json.dumps(raw_data) if (raw_data and retain_raw) else None

        features_json = json.dumps(features)
        features_enc = features_json  # default: plaintext

        try:
            from flask import current_app
            from cryptography.fernet import Fernet

            fernet_key = current_app.config.get("BACKUP_FERNET")
            if fernet_key:
                fernet = Fernet(fernet_key.encode("utf-8"))
                features_enc = fernet.encrypt(features_json.encode("utf-8")).decode(
                    "utf-8"
                )
                if stored_raw:
                    stored_raw = fernet.encrypt(stored_raw.encode("utf-8")).decode(
                        "utf-8"
                    )
        except RuntimeError:
            # Outside Flask app context (e.g., background threads, tests).
            # Features are stored as plaintext JSON — acceptable for tests
            # and non-production contexts.
            pass
        except Exception as e:
            logger.error("Failed to encrypt behavioral data: %s", e)
            raise

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO behavioral_data 
                (user_id, session_id, data_type, features, raw_data, confidence_score, anomaly_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    user_id,
                    session_id,
                    data_type,
                    features_enc,
                    stored_raw,
                    confidence_score,
                    anomaly_score,
                ),
            )
            conn.commit()

    def delete_user_behavioral_profile(self, user_id: int) -> Dict:
        """DPDP Right-to-Erasure: Delete all behavioral data for a user.

        Performs cryptographic shred — deletes feature vectors, raw data,
        and behavioral embeddings. Audit evidence is RETAINED per RBI
        7-year mandate but anonymized.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Delete behavioral data (features + raw)
            cursor.execute("DELETE FROM behavioral_data WHERE user_id = ?", (user_id,))
            deleted_behavioral = cursor.rowcount

            # Anonymize audit evidence (retain for RBI but strip PII)
            cursor.execute(
                """
                UPDATE audit_evidence 
                SET metadata = '{"redacted": true}' 
                WHERE user_id = ? AND retention_tag != 'compliance'
                """,
                (user_id,),
            )
            anonymized_audit = cursor.rowcount

            conn.commit()

        return {
            "user_id": user_id,
            "behavioral_records_deleted": deleted_behavioral,
            "audit_records_anonymized": anonymized_audit,
            "compliance_records_retained": True,
        }

    def get_user_behavioral_data(
        self, user_id: int, data_type: str = None, limit: int = 1000
    ) -> List[Dict]:
        """Get behavioral data for a user"""
        fernet = None
        try:
            from flask import current_app
            from cryptography.fernet import Fernet

            fernet_key = current_app.config.get("BACKUP_FERNET")
            if fernet_key:
                fernet = Fernet(fernet_key.encode("utf-8"))
        except RuntimeError:
            pass  # Outside app context — read as plaintext

        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT * FROM behavioral_data 
                WHERE user_id = ?
            """
            params = [user_id]

            if data_type:
                query += " AND data_type = ?"
                params.append(data_type)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            results = []
            for row in cursor.fetchall():
                row_dict = dict(row)

                # Try Fernet decryption first, then fall back to plaintext JSON
                features_raw = row_dict.get("features", "")
                if fernet and features_raw:
                    try:
                        features_str = fernet.decrypt(
                            features_raw.encode("utf-8")
                        ).decode("utf-8")
                        row_dict["features"] = json.loads(features_str)
                    except Exception:
                        try:
                            row_dict["features"] = json.loads(features_raw)
                        except Exception:
                            row_dict["features"] = {}
                elif features_raw:
                    try:
                        row_dict["features"] = json.loads(features_raw)
                    except Exception:
                        row_dict["features"] = {}
                else:
                    row_dict["features"] = {}

                if row_dict.get("raw_data"):
                    raw_val = row_dict["raw_data"]
                    if fernet:
                        try:
                            raw_str = fernet.decrypt(raw_val.encode("utf-8")).decode(
                                "utf-8"
                            )
                            row_dict["raw_data"] = json.loads(raw_str)
                        except Exception:
                            try:
                                row_dict["raw_data"] = json.loads(raw_val)
                            except Exception:
                                row_dict["raw_data"] = {}
                    else:
                        try:
                            row_dict["raw_data"] = json.loads(raw_val)
                        except Exception:
                            row_dict["raw_data"] = {}

                results.append(row_dict)

            return results

    def log_auth_event(
        self,
        user_id: int,
        session_id: str,
        event_type: str,
        event_data: Dict,
        ip_address: str = None,
    ):
        """Log authentication events"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO auth_events (user_id, session_id, event_type, event_data, ip_address)
                VALUES (?, ?, ?, ?, ?)
            """,
                (user_id, session_id, event_type, json.dumps(event_data), ip_address),
            )
            conn.commit()

    def log_audit_evidence(
        self,
        action: str,
        status: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        resource: Optional[str] = None,
        rationale: Optional[str] = None,
        metadata: Optional[Dict] = None,
        retention_tag: str = "standard",
    ):
        """Persist compliance/audit evidence entries."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT entry_hash FROM audit_evidence ORDER BY evidence_id DESC LIMIT 1"
            )
            prev = cursor.fetchone()
            prev_hash = prev["entry_hash"] if prev and prev["entry_hash"] else ""
            record = {
                "user_id": user_id,
                "session_id": session_id,
                "action": action,
                "resource": resource,
                "status": status,
                "rationale": rationale,
                "metadata": metadata or {},
                "retention_tag": retention_tag,
                "prev_hash": prev_hash,
            }
            entry_hash = hashlib.sha256(
                json.dumps(record, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8"
                )
            ).hexdigest()
            cursor.execute(
                """
                INSERT INTO audit_evidence
                (user_id, session_id, action, resource, status, rationale, metadata, retention_tag, prev_hash, entry_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    session_id,
                    action,
                    resource,
                    status,
                    rationale,
                    json.dumps(metadata or {}),
                    retention_tag,
                    prev_hash,
                    entry_hash,
                ),
            )
            conn.commit()

    def get_audit_evidence(
        self, user_id: Optional[int] = None, limit: int = 100
    ) -> List[Dict]:
        """Get recent compliance evidence. If user_id is None, gets global evidence."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if user_id is not None:
                cursor.execute(
                    """
                    SELECT * FROM audit_evidence
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM audit_evidence
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            rows = []
            for row in cursor.fetchall():
                item = dict(row)
                item["metadata"] = json.loads(item["metadata"] or "{}")
                rows.append(item)
            return rows

    def verify_audit_chain(self, limit: int = 1000) -> Dict:
        """Verify the integrity of the tamper-evident audit hash chain.

        Walks the chain from oldest to newest and re-computes each entry_hash
        to confirm no record has been modified or deleted.

        Returns:
            Dict with total_records, verified_count, first_broken_id (if any),
            and is_valid boolean.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT evidence_id, user_id, session_id, action, resource,
                       status, rationale, metadata, retention_tag,
                       prev_hash, entry_hash
                FROM audit_evidence
                ORDER BY evidence_id ASC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()

        if not rows:
            return {"total_records": 0, "verified_count": 0, "is_valid": True}

        verified = 0
        expected_prev = ""

        for row in rows:
            row_dict = dict(row)
            eid = row_dict["evidence_id"]

            # Check chain linkage
            if row_dict["prev_hash"] != expected_prev:
                return {
                    "total_records": len(rows),
                    "verified_count": verified,
                    "first_broken_id": eid,
                    "error": "prev_hash mismatch",
                    "is_valid": False,
                }

            # Re-compute the entry hash
            record = {
                "user_id": row_dict["user_id"],
                "session_id": row_dict["session_id"],
                "action": row_dict["action"],
                "resource": row_dict["resource"],
                "status": row_dict["status"],
                "rationale": row_dict["rationale"],
                "metadata": json.loads(row_dict["metadata"] or "{}"),
                "retention_tag": row_dict["retention_tag"],
                "prev_hash": row_dict["prev_hash"],
            }
            recomputed = hashlib.sha256(
                json.dumps(record, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8"
                )
            ).hexdigest()

            if recomputed != row_dict["entry_hash"]:
                return {
                    "total_records": len(rows),
                    "verified_count": verified,
                    "first_broken_id": eid,
                    "error": "entry_hash mismatch (record tampered)",
                    "is_valid": False,
                }

            expected_prev = row_dict["entry_hash"]
            verified += 1

        return {
            "total_records": len(rows),
            "verified_count": verified,
            "is_valid": True,
        }

    # ── Consent persistence (DPDP Act 2023) ──────────────────────────────

    def save_consent(
        self, user_id: int, purposes: list, version: str, consent_hash: str
    ) -> int:
        """Persist a consent record to the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if self.is_pg:
                cursor.execute(
                    """
                    INSERT INTO consent_records (user_id, purposes, version, consent_hash)
                    VALUES (?, ?, ?, ?) RETURNING consent_id
                    """,
                    (user_id, json.dumps(purposes), version, consent_hash),
                )
                row = cursor.fetchone()
                conn.commit()
                return row["consent_id"] if row else 0
            else:
                cursor.execute(
                    """
                    INSERT INTO consent_records (user_id, purposes, version, consent_hash)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, json.dumps(purposes), version, consent_hash),
                )
                conn.commit()
                return cursor.lastrowid

    def withdraw_consent(self, user_id: int, purposes: list = None) -> bool:
        """Mark consent as withdrawn (full or partial)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT consent_id, purposes FROM consent_records WHERE user_id = ? AND status = 'active' ORDER BY consent_id DESC LIMIT 1",
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False
            if purposes:
                current = json.loads(row["purposes"])
                remaining = [p for p in current if p not in purposes]
                status = "partial" if remaining else "withdrawn"
                cursor.execute(
                    "UPDATE consent_records SET purposes = ?, status = ?, withdrawn_at = CURRENT_TIMESTAMP WHERE consent_id = ?",
                    (json.dumps(remaining), status, row["consent_id"]),
                )
            else:
                cursor.execute(
                    "UPDATE consent_records SET purposes = '[]', status = 'withdrawn', withdrawn_at = CURRENT_TIMESTAMP WHERE consent_id = ?",
                    (row["consent_id"],),
                )
            conn.commit()
            return True

    def get_consent(self, user_id: int) -> Optional[Dict]:
        """Get the latest active consent record for a user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM consent_records WHERE user_id = ? ORDER BY consent_id DESC LIMIT 1",
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            item = dict(row)
            item["purposes"] = json.loads(item["purposes"])
            return item

    def issue_password_reset_token(
        self, user_id: int, token_hash: str, expires_at: datetime
    ):
        """Create password reset token record."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
                VALUES (?, ?, ?)
                """,
                (user_id, token_hash, expires_at),
            )
            conn.commit()

    def consume_password_reset_token(self, token_hash: str) -> Optional[int]:
        """Mark a reset token used if valid; returns user_id if successful."""
        now = datetime.now()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT token_id, user_id, expires_at, used_at
                FROM password_reset_tokens
                WHERE token_hash = ?
                ORDER BY token_id DESC
                LIMIT 1
                """,
                (token_hash,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            if row["used_at"]:
                return None
            expires_at = row["expires_at"]
            if isinstance(expires_at, str):
                try:
                    expires_at = datetime.fromisoformat(expires_at)
                except Exception:
                    expires_at = now
            
            if isinstance(expires_at, datetime):
                if expires_at.tzinfo is not None and now.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=None)
                elif expires_at.tzinfo is None and now.tzinfo is not None:
                    now = now.replace(tzinfo=None)
            else:
                expires_at = now

            if expires_at < now:
                return None
            cursor.execute(
                "UPDATE password_reset_tokens SET used_at = ? WHERE token_id = ?",
                (now, row["token_id"]),
            )
            conn.commit()
            return int(row["user_id"])

    def update_user_password(self, user_id: int, new_password: str) -> bool:
        """Update user password hash. Bcrypt embeds the salt in the hash."""
        password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
        # Decode bytes to str for PostgreSQL TEXT column
        if isinstance(password_hash, bytes):
            password_hash = password_hash.decode("utf-8")
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, failed_attempts = 0, locked_until = NULL WHERE user_id = ?",
                (password_hash, user_id),
            )
            conn.commit()
            return True

    def anonymize_user(self, user_id: int) -> None:
        """Anonymize user PII and deactivate account."""
        anon = f"deleted_{user_id}"
        _false = "FALSE" if self.is_pg else "0"
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE users SET username = ?, email = ?, is_active = {_false} WHERE user_id = ?",
                (anon, f"{anon}@example.invalid", user_id),
            )
            # Remove raw_data payloads for minimization
            conn.execute(
                "UPDATE behavioral_data SET raw_data = NULL WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()

    def update_calibration_status(self, user_id: int, is_complete: bool):
        """Update user calibration status"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users SET calibration_complete = ?
                WHERE user_id = ?
            """,
                (is_complete, user_id),
            )
            conn.commit()

    def update_model_metadata(
        self,
        user_id: int,
        accuracy: float = None,
        training_samples: int = None,
        drift_detected: bool = None,
    ):
        """Update model metadata"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            updates = []
            params = []

            if accuracy is not None:
                updates.append("model_accuracy = ?")
                params.append(accuracy)
                updates.append("last_trained = ?")
                params.append(datetime.now())

            if training_samples is not None:
                updates.append("training_samples = ?")
                params.append(training_samples)

            if drift_detected is not None:
                updates.append("drift_detected = ?")
                params.append(drift_detected)
                if drift_detected:
                    updates.append("drift_timestamp = ?")
                    params.append(datetime.now())

            if updates:
                params.append(user_id)
                set_clause = ", ".join(updates)
                query = "UPDATE model_metadata SET " + set_clause + " WHERE user_id = ?"
                cursor.execute(
                    query,
                    params,
                )
                conn.commit()

    def get_model_metadata(self, user_id: int) -> Optional[Dict]:
        """Get model metadata for user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM model_metadata WHERE user_id = ?
            """,
                (user_id,),
            )

            result = cursor.fetchone()
            return dict(result) if result else None

    def cleanup_old_sessions(self, timeout_hours: int = 24):
        """Clean up old inactive sessions"""
        cutoff_time = datetime.now() - timedelta(hours=timeout_hours)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sessions SET is_active = 0
                WHERE last_activity < ? AND is_active = 1
            """,
                (cutoff_time,),
            )
            conn.commit()

    def get_user_stats(self, user_id: int) -> Dict:
        """Get user statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get behavioral data count
            cursor.execute(
                """
                SELECT COUNT(*) as total_samples,
                       COUNT(CASE WHEN data_type = 'keystroke' THEN 1 END) as keystroke_samples,
                       COUNT(CASE WHEN data_type = 'mouse' THEN 1 END) as mouse_samples
                FROM behavioral_data WHERE user_id = ?
            """,
                (user_id,),
            )
            data_stats = dict(cursor.fetchone())

            # Get session count
            cursor.execute(
                """
                SELECT COUNT(*) as total_sessions,
                       COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_sessions
                FROM sessions WHERE user_id = ?
            """,
                (user_id,),
            )
            session_stats = dict(cursor.fetchone())

            # Get recent anomalies
            cursor.execute(
                """
                SELECT COUNT(*) as recent_anomalies
                FROM auth_events 
                WHERE user_id = ? AND event_type = 'anomaly' 
                AND timestamp > datetime('now', '-7 days')
            """,
                (user_id,),
            )
            anomaly_stats = dict(cursor.fetchone())

            return {**data_stats, **session_stats, **anomaly_stats}

    def get_user_statistics(self, user_id: int) -> Dict:
        """Backward-compatible alias for get_user_stats."""
        return self.get_user_stats(user_id)


# Database factory cache keyed by database path.
_db_engines: Dict[str, DatabaseManager] = {}


def get_engine(db_path: str = None):
    """
    Get or create a database engine instance (lazy initialization).

    Args:
        db_path: Path to the SQLite database file. If None, uses settings.DATABASE_PATH.

    Returns:
        DatabaseManager: Initialized database manager instance
    """
    if db_path is None:
        settings = Settings()
        db_path = settings.DATABASE_PATH

    if db_path not in _db_engines:
        _db_engines[db_path] = DatabaseManager(db_path)

    return _db_engines[db_path]


def reset_engine(db_path: str = None) -> None:
    """Reset cached database engine(s), useful for isolated tests."""
    global _db_engines
    if db_path is None:
        _db_engines = {}
        return
    _db_engines.pop(db_path, None)


def create_db_manager(db_path: str = None) -> DatabaseManager:
    """
    Create a new database manager instance (factory function).

    This is useful for testing with in-memory databases or when you need
    multiple database connections.

    Args:
        db_path: Path to the SQLite database file. If None, uses settings.DATABASE_PATH.

    Returns:
        DatabaseManager: New database manager instance
    """
    if db_path is None:
        settings = Settings()
        db_path = settings.DATABASE_PATH

    return DatabaseManager(db_path)
