"""Shared pytest fixtures for the Behavior-Based Authentication test suite.

Provides reusable ``app``, ``client``, ``registered_user``, ``logged_in_user``,
and ``auth_headers`` fixtures so individual test modules stay DRY.
"""
import os
import sys
import uuid
import pytest
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Ensure project root is on sys.path
root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if root not in sys.path:
    sys.path.insert(0, root)

from app import create_app
from app.database import reset_engine


# ── 32+ byte keys to silence JWT InsecureKeyLengthWarning ────────────────────
_TEST_SECRET = "test-secret-key-for-testing-32bytes!"
_TEST_JWT_SECRET = "test-jwt-secret-for-testing-32bytes!"
# Stable Fernet key for tests — silences the ephemeral key warning and ensures
# MFA secret encryption/decryption is exercised rather than silently skipped.
_TEST_FERNET_KEY = "A6m3vqcXQ20GUuSCGELx79Za0lz16K2qtq72KA3xQuw="

# Test database - use TEST PostgreSQL DB URL or create a separate Supabase test project
_TEST_DB_URI = os.environ.get("TEST_DATABASE_URL", "")


@pytest.fixture
def app():
    """Create a fresh test application with a SQLite in-memory test database."""
    os.environ["SECRET_KEY"] = _TEST_SECRET
    os.environ["JWT_SECRET_KEY"] = _TEST_JWT_SECRET
    os.environ["BACKUP_FERNET"] = _TEST_FERNET_KEY
    os.environ["MAIL_BACKEND"] = "console"

    # Use test database URL if provided, otherwise use SQLite memory DB
    if _TEST_DB_URI:
        os.environ["SQLALCHEMY_DATABASE_URI"] = _TEST_DB_URI
    else:
        # Force SQLite for tests to avoid connecting to production Supabase
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    # Flush the cached DB engine so each test app gets a pristine schema
    reset_engine()

    application = create_app("testing")
    
    # Truncate tables to ensure isolated state for tests
    with application.app_context():
        from app.extensions import get_db
        db = get_db()
        try:
            # PostgreSQL fast truncate
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    TRUNCATE TABLE 
                        users, sessions, behavioral_data, auth_events, model_metadata, 
                        audit_evidence, password_reset_tokens, consent_records, otp_codes, 
                        investments, beneficiaries, cards, notifications,
                        enrollment_state, enrollment_history, digraph_profiles, device_fingerprints
                    CASCADE;
                """)
                conn.commit()
        except Exception:
            # SQLite fallback
            with db.get_connection() as conn:
                cursor = conn.cursor()
                for table in ["users", "sessions", "behavioral_data", "auth_events", "model_metadata", 
                              "audit_evidence", "password_reset_tokens", "consent_records", "otp_codes", 
                              "investments", "beneficiaries", "cards", "notifications",
                              "enrollment_state", "enrollment_history", "digraph_profiles", "device_fingerprints"]:
                    try:
                        cursor.execute(f"DELETE FROM {table}")
                    except Exception:
                        pass
                conn.commit()

    yield application

    # Teardown: clear cached engines so the next test starts clean
    reset_engine()


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def registered_user(client):
    """Register a unique user and return its details."""
    uid = uuid.uuid4().hex[:8]
    username = f"user_{uid}"
    password = "TestPassword123!"
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": password,
        },
    )
    assert resp.status_code == 200, f"Registration failed: {resp.get_json()}"
    data = resp.get_json()["data"]

    # Retrieve MFA secret directly from the DB for testing,
    # since the registration API no longer leaks it.
    mfa_secret = ""
    with client.application.app_context():
        from app.extensions import get_db
        db = get_db()
        db.set_email_verified(data["user_id"])

        user_record = db.get_user_for_mfa(data["user_id"])
        if user_record:
            mfa_secret = user_record["mfa_secret"]

    return {
        "username": username,
        "password": password,
        "user_id": data["user_id"],
        "mfa_secret": mfa_secret,
        "mfa_provisioning_uri": "",
    }


@pytest.fixture
def logged_in_user(client, registered_user):
    """Log in a registered user and return auth context."""
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "username": registered_user["username"],
            "password": registered_user["password"],
        },
    )
    assert resp.status_code == 200, f"Login failed: {resp.get_json()}"
    data = resp.get_json()["data"]
    return {
        **registered_user,
        "access_token": data["access_token"],
        "session_id": data["session_id"],
    }


@pytest.fixture
def auth_headers(logged_in_user):
    """Return ``Authorization`` header dict for an authenticated user."""
    return {"Authorization": f"Bearer {logged_in_user['access_token']}"}


@pytest.fixture
def mfa_logged_in_user(client, logged_in_user):
    """Perform the full MFA flow and return context with an aal=mfa JWT.

    Uses the registered user's MFA secret to generate a valid TOTP code,
    verifies it, and returns the elevated access token.
    """
    import pyotp
    from freezegun import freeze_time

    mfa_secret = logged_in_user["mfa_secret"]
    assert mfa_secret, "MFA secret is missing — cannot elevate to aal=mfa"

    otp = pyotp.TOTP(mfa_secret).now()
    resp = client.post(
        "/api/v1/auth/mfa/verify",
        json={"session_id": logged_in_user["session_id"], "otp": otp},
        headers={"Authorization": f"Bearer {logged_in_user['access_token']}"},
    )
    assert resp.status_code == 200, f"MFA verify failed: {resp.get_json()}"
    mfa_token = resp.get_json()["data"]["access_token"]
    return {
        **logged_in_user,
        "access_token": mfa_token,
    }


@pytest.fixture
def mfa_auth_headers(mfa_logged_in_user):
    """Return ``Authorization`` header dict for an MFA-authenticated user."""
    return {"Authorization": f"Bearer {mfa_logged_in_user['access_token']}"}
