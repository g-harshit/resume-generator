from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlmodel import select

from app.config import DEV_JWT_SECRET, Settings, get_settings
from app.models import User


def register(client, email="asha@example.com", password="correct horse", name="Asha Rao"):
    return client.post("/auth/register", json={"email": email, "password": password, "name": name})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_returns_a_token_that_signs_you_in(client):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == "asha@example.com"
    assert body["user"]["name"] == "Asha Rao"

    me = client.get("/auth/me", headers=bearer(body["token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "asha@example.com"


def test_the_password_is_stored_hashed(client, session):
    register(client, password="correct horse")
    user = session.exec(select(User)).one()
    assert "correct horse" not in user.password_hash
    assert user.password_hash.startswith("$argon2")


def test_email_is_case_insensitive_and_trimmed(client):
    assert register(client, email="  Asha@Example.COM ").status_code == 201
    assert register(client, email="asha@example.com").status_code == 409

    r = client.post("/auth/login", json={"email": "ASHA@example.com", "password": "correct horse"})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "asha@example.com"


def test_duplicate_email_is_a_clear_conflict(client):
    register(client)
    r = register(client, name="Someone Else")
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": "correct horse", "name": "A"},
        {"email": "a@example.com", "password": "short", "name": "A"},
        {"email": "a@example.com", "password": "x" * 129, "name": "A"},
        {"email": "a@example.com", "password": "correct horse", "name": "   "},
    ],
)
def test_register_rejects_bad_input(client, payload):
    assert client.post("/auth/register", json=payload).status_code == 422


def test_login(client):
    register(client)
    r = client.post("/auth/login", json={"email": "asha@example.com", "password": "correct horse"})
    assert r.status_code == 200
    assert client.get("/auth/me", headers=bearer(r.json()["token"])).status_code == 200


def test_wrong_password_and_unknown_email_look_the_same(client):
    register(client)
    wrong = client.post("/auth/login", json={"email": "asha@example.com", "password": "nope nope"})
    unknown = client.post("/auth/login", json={"email": "nobody@example.com", "password": "x"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_me_needs_a_token(client):
    r = client.get("/auth/me")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_garbage_token_is_rejected(client):
    assert client.get("/auth/me", headers=bearer("not.a.token")).status_code == 401


def _token(user_id, *, secret=DEV_JWT_SECRET, expires_in=timedelta(days=1)):
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + expires_in}, secret, algorithm="HS256"
    )


def test_expired_token_is_rejected(client):
    user_id = register(client).json()["user"]["id"]
    assert client.get("/auth/me", headers=bearer(_token(user_id))).status_code == 200
    expired = _token(user_id, expires_in=timedelta(seconds=-1))
    assert client.get("/auth/me", headers=bearer(expired)).status_code == 401


def test_token_signed_with_another_secret_is_rejected(client):
    user_id = register(client).json()["user"]["id"]
    forged = _token(user_id, secret="someone-elses-secret-that-is-long-enough")
    assert client.get("/auth/me", headers=bearer(forged)).status_code == 401


def test_token_for_a_deleted_account_is_rejected(client, session):
    body = register(client).json()
    session.delete(session.get(User, body["user"]["id"]))
    session.commit()
    assert client.get("/auth/me", headers=bearer(body["token"])).status_code == 401


def test_production_refuses_the_dev_jwt_secret():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(environment="production")
    with pytest.raises(ValueError, match="32 bytes"):
        Settings(environment="production", jwt_secret="too-short")
    Settings(environment="production", jwt_secret="x" * 32)  # fine
    assert get_settings().environment == "development"
