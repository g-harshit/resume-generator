"""The feedback button, and reading it in the admin panel."""

from tests.test_admin import admin, register  # noqa: F401  (admin is a fixture)


def send(client, headers=None, **body):
    return client.post("/feedback", headers=headers or {}, json={"message": "It broke", **body})


def test_a_signed_in_user_sends_feedback_and_the_admin_reads_it(client, admin):  # noqa: F811
    user = register(client, "ravi@example.com", "Ravi")
    r = send(
        client, user, kind="problem", message="The PDF cut my last line.", page="/app/resume?id=3"
    )
    assert r.status_code == 201, r.text

    items = client.get("/admin/feedback", headers=admin).json()
    assert len(items) == 1
    item = items[0]
    assert (item["kind"], item["status"], item["email"]) == ("problem", "new", "ravi@example.com")
    assert item["message"] == "The PDF cut my last line." and item["page"] == "/app/resume?id=3"
    assert client.get("/admin/stats", headers=admin).json()["feedback_new"] == 1


def test_a_visitor_can_send_feedback_and_leave_an_email(client, admin):  # noqa: F811
    assert (
        send(client, kind="idea", message="Add a Hindi resume", email="v@example.com").status_code
        == 201
    )
    item = client.get("/admin/feedback", headers=admin).json()[0]
    assert item["user_id"] is None and item["email"] == "v@example.com"


def test_feedback_can_be_marked_filtered_and_exported(client, admin):  # noqa: F811
    send(client, kind="idea", message="Dark mode")
    send(client, kind="problem", message="Slow upload")
    first = client.get("/admin/feedback", headers=admin).json()[0]
    r = client.patch(f"/admin/feedback/{first['id']}", headers=admin, json={"status": "done"})
    assert r.json()["status"] == "done"
    assert [
        f["message"] for f in client.get("/admin/feedback?status=new", headers=admin).json()
    ] == ["Dark mode"]
    assert [
        f["message"] for f in client.get("/admin/feedback?kind=idea", headers=admin).json()
    ] == ["Dark mode"]
    csv = client.get("/admin/feedback.csv", headers=admin).text
    assert csv.splitlines()[0] == "id,date,kind,status,email,page,message" and "Slow upload" in csv


def test_feedback_needs_a_message_and_is_limited(client, monkeypatch):
    from app.config import get_settings

    assert send(client, message="  ").status_code == 422
    monkeypatch.setattr(get_settings(), "feedback_per_day", 2)
    assert send(client).status_code == 201
    assert send(client).status_code == 201
    assert send(client).status_code == 429


def test_only_admins_read_feedback(client):
    user = register(client, "ravi@example.com")
    assert client.get("/admin/feedback", headers=user).status_code == 404
