"""Rate limits on sign-in and sign-up, and password reset."""

import re
from datetime import timedelta

import pytest
from sqlmodel import select

from app.models import PasswordReset, utcnow
from app.services import mailer


@pytest.fixture(autouse=True)
def _empty_outbox():
    mailer.outbox.clear()
    yield
    mailer.outbox.clear()


def register(client, email="asha@example.com", password="correct horse"):
    return client.post(
        "/auth/register", json={"email": email, "password": password, "name": "Asha Rao"}
    )


def login(client, email="asha@example.com", password="correct horse"):
    return client.post("/auth/login", json={"email": email, "password": password})


# --- rate limits ---------------------------------------------------------------------


def test_ten_wrong_passwords_lock_that_account_for_a_while(client):
    register(client)
    for _ in range(10):
        assert login(client, password="wrong password").status_code == 401
    r = login(client)  # even the right password, until the window passes
    assert r.status_code == 429
    assert "15 minutes" in r.json()["detail"]


def test_successful_sign_ins_dont_count(client):
    register(client)
    for _ in range(15):
        assert login(client).status_code == 200


def test_old_failures_age_out(client, session, monkeypatch):
    from app.models import AuthAttempt

    register(client)
    for _ in range(10):
        login(client, password="wrong password")
    session.expire_all()
    for attempt in session.exec(select(AuthAttempt)).all():
        attempt.created_at = utcnow() - timedelta(minutes=16)
        session.add(attempt)
    session.commit()
    assert login(client).status_code == 200


def test_many_sign_ups_from_one_place_are_slowed(client):
    for i in range(10):
        assert register(client, email=f"user{i}@example.com").status_code == 201
    r = register(client, email="user10@example.com")
    assert r.status_code == 429


def test_forwarded_ip_is_ignored_unless_behind_a_proxy(client, monkeypatch):
    from app.config import get_settings

    register(client)
    for i in range(50):
        login(client, email=f"nobody{i}@example.com", password="x")
    # Pretending to be somewhere else doesn't help when there's no trusted proxy.
    r = client.post(
        "/auth/login",
        json={"email": "asha@example.com", "password": "correct horse"},
        headers={"X-Forwarded-For": "203.0.113.9"},
    )
    assert r.status_code == 429
    monkeypatch.setattr(get_settings(), "trust_proxy_headers", True)
    assert (
        r.status_code == 429
        and client.post(
            "/auth/login",
            json={"email": "asha@example.com", "password": "correct horse"},
            headers={"X-Forwarded-For": "203.0.113.9"},
        ).status_code
        == 200
    )


# --- password reset ------------------------------------------------------------------


def reset_link_token() -> str:
    body = mailer.outbox[-1].get_content()
    return re.search(r"reset-password\?token=([\w-]+)", body).group(1)


def test_reset_sends_a_link_that_sets_a_new_password(client):
    register(client)
    r = client.post("/auth/password-reset", json={"email": "ASHA@example.com"})
    assert r.status_code == 202
    assert mailer.outbox[-1]["To"] == "asha@example.com"
    assert "http://localhost:3100/reset-password?token=" in mailer.outbox[-1].get_content()

    r = client.post(
        "/auth/password-reset/confirm",
        json={"token": reset_link_token(), "password": "new horse battery"},
    )
    assert r.status_code == 200
    assert (
        client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['token']}"}).status_code
        == 200
    )
    assert login(client).status_code == 401
    assert login(client, password="new horse battery").status_code == 200


def test_resetting_signs_out_every_other_session(client):
    old_token = register(client).json()["token"]
    client.post("/auth/password-reset", json={"email": "asha@example.com"})
    client.post(
        "/auth/password-reset/confirm",
        json={"token": reset_link_token(), "password": "new horse battery"},
    )
    assert (
        client.get("/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401
    )


def test_an_unknown_email_gets_the_same_answer_and_no_email(client):
    r = client.post("/auth/password-reset", json={"email": "nobody@example.com"})
    assert r.status_code == 202
    assert r.json() == {"detail": "If that email has an account, a reset link is on its way."}
    assert mailer.outbox == []


def test_a_link_works_once(client):
    register(client)
    client.post("/auth/password-reset", json={"email": "asha@example.com"})
    token = reset_link_token()
    assert (
        client.post(
            "/auth/password-reset/confirm", json={"token": token, "password": "new horse battery"}
        ).status_code
        == 200
    )
    r = client.post(
        "/auth/password-reset/confirm", json={"token": token, "password": "another password"}
    )
    assert r.status_code == 400


def test_an_expired_link_is_refused(client, session):
    register(client)
    client.post("/auth/password-reset", json={"email": "asha@example.com"})
    token = reset_link_token()
    session.expire_all()
    reset = session.exec(select(PasswordReset)).one()
    reset.expires_at = utcnow() - timedelta(minutes=1)
    session.commit()
    r = client.post(
        "/auth/password-reset/confirm", json={"token": token, "password": "new horse battery"}
    )
    assert r.status_code == 400
    assert "expired" in r.json()["detail"]


def test_using_one_link_cancels_the_others(client):
    register(client)
    client.post("/auth/password-reset", json={"email": "asha@example.com"})
    first = reset_link_token()
    client.post("/auth/password-reset", json={"email": "asha@example.com"})
    second = reset_link_token()
    assert (
        client.post(
            "/auth/password-reset/confirm", json={"token": second, "password": "new horse battery"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/auth/password-reset/confirm", json={"token": first, "password": "another one"}
        ).status_code
        == 400
    )


def test_only_a_hash_of_the_token_is_stored(client, session):
    register(client)
    client.post("/auth/password-reset", json={"email": "asha@example.com"})
    token = reset_link_token()
    session.expire_all()
    stored = session.exec(select(PasswordReset)).one().token_hash
    assert token not in stored and len(stored) == 64


def test_reset_requests_are_limited_per_email(client):
    register(client)
    for _ in range(3):
        assert (
            client.post("/auth/password-reset", json={"email": "asha@example.com"}).status_code
            == 202
        )
    assert (
        client.post("/auth/password-reset", json={"email": "asha@example.com"}).status_code == 429
    )
