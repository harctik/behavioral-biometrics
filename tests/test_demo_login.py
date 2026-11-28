"""The test sign-in must stay off everywhere except an opted-in local run."""

import pytest

from app.demo_login import DEMO_EMAIL

URL = "/api/v1/auth/login"
CREDS = {"username": "admin", "password": "admin"}
MARKERS = (
    "DEMO_LOGIN",
    "FLASK_ENV",
    "RENDER",
    "VERCEL",
    "DYNO",
    "RAILWAY_ENVIRONMENT",
    "K_SERVICE",
)


@pytest.fixture(autouse=True)
def clean_env(app, monkeypatch):
    for name in MARKERS:
        monkeypatch.delenv(name, raising=False)


def post(client, remote="127.0.0.1", headers=None):
    return client.post(
        URL, json=CREDS, headers=headers or {}, environ_base={"REMOTE_ADDR": remote}
    )


def test_off_by_default(client):
    assert post(client).status_code == 401


def test_works_locally_when_enabled(client, monkeypatch):
    monkeypatch.setenv("DEMO_LOGIN", "1")
    response = post(client)
    assert response.status_code == 200
    assert response.get_json()["data"]["challenge_token"]
    # A second sign-in reuses the same account.
    assert post(client).status_code == 200


def test_password_is_not_stored(app, client, monkeypatch):
    monkeypatch.setenv("DEMO_LOGIN", "1")
    assert post(client).status_code == 200
    from app.extensions import get_db

    with app.app_context():
        assert get_db().authenticate_user("admin", "admin") is None


def test_refused_from_another_computer(client, monkeypatch):
    monkeypatch.setenv("DEMO_LOGIN", "1")
    assert post(client, remote="192.168.1.20").status_code == 401


@pytest.mark.parametrize("header", ["X-Forwarded-For", "Forwarded", "X-Real-IP"])
def test_refused_through_a_proxy(client, monkeypatch, header):
    monkeypatch.setenv("DEMO_LOGIN", "1")
    assert (
        post(client, remote="203.0.113.9", headers={header: "127.0.0.1"}).status_code
        == 401
    )


@pytest.mark.parametrize(
    "name,value", [("FLASK_ENV", "production"), ("RENDER", "true"), ("VERCEL", "1")]
)
def test_refused_in_production_or_on_a_host(client, monkeypatch, name, value):
    monkeypatch.setenv("DEMO_LOGIN", "1")
    monkeypatch.setenv(name, value)
    assert post(client).status_code == 401


def test_never_opens_an_existing_real_account(app, client, monkeypatch):
    monkeypatch.setenv("DEMO_LOGIN", "1")
    from app.extensions import get_db

    with app.app_context():
        get_db().create_user("admin", "someone@example.com", "A-real-Passw0rd!")
        assert get_db().get_user_by_username("admin")["email"] != DEMO_EMAIL
    assert post(client).status_code == 401
