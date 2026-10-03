"""The admin panel: only verified admins get in; numbers, users, and account actions."""

import pytest
from sqlmodel import select

from app.ai_providers import AIProviderError, stub
from app.config import get_settings
from app.models import AdminAction, SourceDocument, User, utcnow
from tests.test_uploads import fake_parse, upload

ADMIN = "boss@example.com"


def register(client, email, name="Someone"):
    r = client.post(
        "/auth/register", json={"email": email, "password": "correct horse", "name": name}
    )
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def admin(client, session, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_emails", f"{ADMIN}, other-admin@example.com")
    headers = register(client, ADMIN, "Boss")
    user = session.exec(select(User).where(User.email == ADMIN)).one()
    user.email_verified_at = utcnow()  # signed in with Google, or reset their password
    session.add(user)
    session.commit()
    return headers


def test_admins_see_the_panel_and_know_it(client, admin):
    assert client.get("/auth/me", headers=admin).json()["is_admin"] is True
    assert client.get("/admin/stats", headers=admin).status_code == 200


def test_everyone_else_gets_not_found(client, admin):
    other = register(client, "riya@example.com")
    assert client.get("/auth/me", headers=other).json()["is_admin"] is False
    for path in ["/admin/stats", "/admin/users", "/admin/users.csv", "/admin/log"]:
        assert client.get(path, headers=other).status_code == 404
    assert client.get("/admin/stats").status_code == 401


def test_an_unverified_account_with_an_admin_email_is_not_admin(client, monkeypatch):
    # Someone signs up with the admin's address before the admin does: no rights.
    monkeypatch.setattr(get_settings(), "admin_emails", ADMIN)
    squatter = register(client, ADMIN)
    assert client.get("/auth/me", headers=squatter).json()["is_admin"] is False
    assert client.get("/admin/users", headers=squatter).status_code == 404


def test_stats_count_users_and_activity(client, admin):
    register(client, "riya@example.com")
    stub.answer("parse_resume", fake_parse())
    upload(client, register(client, "neha@example.com"))
    s = client.get("/admin/stats", headers=admin).json()
    assert s["users"] == 3 and s["users_today"] == 3 and s["password_users"] == 3
    assert s["uploads"] == 1 and s["profiles"] == 1
    assert len(s["signups_by_day"]) == 30 and s["signups_by_day"][-1]["count"] == 3
    assert s["active_7d"] >= 1  # the admin, just now


def test_users_list_searches_and_counts(client, admin):
    register(client, "riya@example.com", "Riya Shah")
    stub.answer("parse_resume", fake_parse())
    upload(client, register(client, "neha@example.com", "Neha K"))
    page = client.get("/admin/users", headers=admin, params={"q": "neha"}).json()
    assert page["total"] == 1
    [row] = page["users"]
    assert row["email"] == "neha@example.com" and row["uploads"] == 1
    assert row["profile"] == "draft" and row["sign_in"] == ["password"]
    assert client.get("/admin/users", headers=admin).json()["total"] == 3


def test_users_export_as_csv_and_is_logged(client, admin, session):
    register(client, "riya@example.com", "Riya Shah")
    r = client.get("/admin/users.csv", headers=admin)
    assert r.headers["content-type"].startswith("text/csv")
    assert "riya@example.com,Riya Shah,password" in r.text
    assert session.exec(select(AdminAction)).one().action == "export_users"


def test_user_detail_shows_activity_not_content(client, admin):
    stub.answer("parse_resume", lambda text: (_ for _ in ()).throw(AIProviderError("model down")))
    headers = register(client, "neha@example.com")
    upload(client, headers)
    user_id = client.get("/auth/me", headers=headers).json()["id"]
    detail = client.get(f"/admin/users/{user_id}", headers=admin).json()
    assert (
        detail["uploads"][0]["status"] == "failed" and "model down" in detail["uploads"][0]["error"]
    )
    assert "content" not in str(detail["resumes"])
    failed = client.get("/admin/uploads/failed", headers=admin).json()
    assert failed[0]["user_email"] == "neha@example.com"


def test_disable_blocks_signing_in_and_every_session_until_enabled(client, admin):
    headers = register(client, "riya@example.com")
    user_id = client.get("/auth/me", headers=headers).json()["id"]
    assert client.post(f"/admin/users/{user_id}/disable", headers=admin).json()["user"]["disabled"]
    assert client.get("/auth/me", headers=headers).status_code == 401
    login = {"email": "riya@example.com", "password": "correct horse"}
    r = client.post("/auth/login", json=login)
    assert r.status_code == 403 and "disabled" in r.json()["detail"]
    client.post(f"/admin/users/{user_id}/enable", headers=admin)
    assert client.post("/auth/login", json=login).status_code == 200
    log = [a["action"] for a in client.get("/admin/log", headers=admin).json()]
    assert log == ["enable", "disable"]


def test_sign_out_everywhere_ends_existing_sessions(client, admin):
    headers = register(client, "riya@example.com")
    user_id = client.get("/auth/me", headers=headers).json()["id"]
    client.post(f"/admin/users/{user_id}/sign-out", headers=admin)
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_delete_removes_the_account_its_data_and_files(client, admin, session):
    stub.answer("parse_resume", fake_parse())
    headers = register(client, "neha@example.com")
    upload(client, headers)
    user_id = client.get("/auth/me", headers=headers).json()["id"]
    key = session.exec(select(SourceDocument.storage_key)).one()

    wrong = client.request(
        "DELETE", f"/admin/users/{user_id}", headers=admin, json={"confirm_email": "nope@x.com"}
    )
    assert wrong.status_code == 400
    r = client.request(
        "DELETE",
        f"/admin/users/{user_id}",
        headers=admin,
        json={"confirm_email": "Neha@Example.com"},
    )
    assert r.status_code == 204
    assert session.exec(select(User).where(User.id == user_id)).first() is None
    assert session.exec(select(SourceDocument)).all() == []
    from app.services.storage import get_storage

    with pytest.raises(FileNotFoundError):
        get_storage().get(key)
    [entry] = client.get("/admin/log", headers=admin).json()
    assert entry["action"] == "delete" and entry["target_email"] == "neha@example.com"


def test_admins_cant_disable_or_delete_themselves(client, admin):
    me = client.get("/auth/me", headers=admin).json()["id"]
    assert client.post(f"/admin/users/{me}/disable", headers=admin).status_code == 400
    r = client.request("DELETE", f"/admin/users/{me}", headers=admin, json={"confirm_email": ADMIN})
    assert r.status_code == 400
