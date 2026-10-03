"""Sign in with Google: only tokens Google signed for us, and safe account linking."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlmodel import select

from app.config import get_settings
from app.models import User
from app.services import google_auth

CLIENT_ID = "1234-test.apps.googleusercontent.com"
GOOGLE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def google_token(key=GOOGLE_KEY, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "google-sub-riya",
        "email": "riya@example.com",
        "email_verified": True,
        "name": "Riya Shah",
        "iat": now,
        "exp": now + 3600,
    } | overrides
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})


@pytest.fixture(autouse=True)
def google(monkeypatch):
    """Google's keys are our test key; the API knows our client ID."""
    monkeypatch.setattr(get_settings(), "google_client_id", CLIENT_ID)
    monkeypatch.setattr(google_auth, "_signing_key", lambda token: GOOGLE_KEY.public_key())


def sign_in(client, token):
    return client.post("/auth/google", json={"credential": token})


def test_a_new_person_gets_an_account_without_a_password(client, session):
    r = sign_in(client, google_token())
    assert r.status_code == 200, r.text
    assert r.json()["user"]["email"] == "riya@example.com"
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['token']}"})
    assert me.json()["name"] == "Riya Shah"
    user = session.exec(select(User).where(User.email == "riya@example.com")).one()
    assert user.password_hash is None and user.google_sub == "google-sub-riya"
    assert user.email_verified_at is not None


def test_signing_in_again_finds_the_same_account_even_if_the_email_changed(client):
    first = sign_in(client, google_token()).json()["user"]["id"]
    again = sign_in(client, google_token(email="riya.shah@example.com")).json()["user"]["id"]
    assert again == first


def test_an_existing_password_account_is_linked_and_its_unverified_password_removed(
    client, session
):
    created = client.post(
        "/auth/register",
        json={"email": "riya@example.com", "password": "set-by-someone", "name": "Riya"},
    ).json()
    old_token = created["token"]
    r = sign_in(client, google_token())
    assert r.json()["user"]["id"] == created["user"]["id"]
    # Whoever set that password never proved the inbox was theirs: it no longer works,
    # and their session is over.
    assert (
        client.post(
            "/auth/login", json={"email": "riya@example.com", "password": "set-by-someone"}
        ).status_code
        == 401
    )
    assert (
        client.get("/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401
    )


def test_a_password_login_on_a_google_account_says_to_use_google(client):
    sign_in(client, google_token())
    r = client.post("/auth/login", json={"email": "riya@example.com", "password": "anything12"})
    assert r.status_code == 401 and "Google" in r.json()["detail"]


@pytest.mark.parametrize(
    "token",
    [
        google_token(key=OTHER_KEY),  # not signed by Google
        google_token(aud="someone-elses-client-id"),  # meant for another app
        google_token(iss="https://evil.example"),  # not from Google
        google_token(exp=int(time.time()) - 600),  # expired
        google_token(email_verified=False),  # Google hasn't verified the address
        google_token(email=None),
        "not-a-token-at-all-not-a-token",
    ],
)
def test_untrusted_tokens_are_refused(client, session, token):
    r = sign_in(client, token)
    assert r.status_code == 401
    assert session.exec(select(User)).all() == []


def test_off_when_no_client_id_is_set(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", "")
    assert sign_in(client, google_token()).status_code == 401


def test_an_email_linked_to_another_google_account_is_not_taken_over(client):
    sign_in(client, google_token())
    r = sign_in(client, google_token(sub="someone-else"))
    assert r.status_code == 409


def test_a_password_reset_marks_the_email_verified(client, session, monkeypatch):
    from app.routers import auth as auth_router

    client.post(
        "/auth/register",
        json={"email": "asha@example.com", "password": "correct horse", "name": "Asha"},
    )
    sent = {}
    monkeypatch.setattr(auth_router, "send_email", lambda to, subject, body: sent.update(body=body))
    client.post("/auth/password-reset", json={"email": "asha@example.com"})
    token = sent["body"].split("token=")[1].split()[0]
    client.post("/auth/password-reset/confirm", json={"token": token, "password": "new password 1"})
    user = session.exec(select(User).where(User.email == "asha@example.com")).one()
    assert user.email_verified_at is not None
    # A verified account keeps its password when Google is linked later.
    sign_in(client, google_token(sub="g-asha", email="asha@example.com", name="Asha"))
    assert (
        client.post(
            "/auth/login", json={"email": "asha@example.com", "password": "new password 1"}
        ).status_code
        == 200
    )
