"""MFA end-to-end flow test using shared conftest fixtures."""
import pyotp
from freezegun import freeze_time
from app.database import reset_engine
from app import create_app
import os


@freeze_time("2023-01-01 12:00:00")
def test_mfa_flow():
    os.environ["SECRET_KEY"] = "test-secret-key-for-testing-32bytes!"
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-for-testing-32bytes!"
    os.environ["DATABASE_PATH"] = ":memory:"
    reset_engine()

    app = create_app("testing")
    client = app.test_client()

    # Register a new user
    register_resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": "mfa_user",
            "email": "mfa@example.com",
            "password": "StrongPass123!",
        },
    )
    assert register_resp.status_code == 200
    data = register_resp.get_json()["data"]
    # Retrieve TOTP secret from the DB
    user_id = data["user_id"]
    with app.app_context():
        from app.extensions import get_db

        user_record = get_db().get_user_for_mfa(user_id)
        secret = user_record["mfa_secret"]

    assert secret is not None

    # Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "mfa_user", "password": "StrongPass123!"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.get_json()["data"]
    token = login_data["access_token"]
    session_id = login_data["session_id"]

    # Verify MFA
    otp = pyotp.TOTP(secret).now()
    verify_resp = client.post(
        "/api/v1/auth/mfa/verify",
        json={"session_id": session_id, "otp": otp},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verify_resp.status_code == 200
    assert verify_resp.get_json()["success"] is True
