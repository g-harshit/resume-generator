from sqlmodel import select

from app.ai_providers import stub
from app.models import Profile, SourceDocument
from tests import fixtures
from tests.test_uploads import fake_parse

FULL = {
    "basics": {"name": "Asha Rao", "email": "asha@example.com", "phone": "+91 90000 00000"},
    "experience": [
        {
            "id": "exp_1",
            "company": "Finlytics",
            "title": "Backend Engineer",
            "start": "2021-03",
            "current": True,
            "bullets": [{"id": "b_1", "text": "Built a ledger"}],
        }
    ],
}


def checks_on(profile, target, field=None):
    return [
        c["message"]
        for c in profile["checks"]
        if c["target"] == target and (field is None or c["field"] == field)
    ]


def create(client, auth, data=FULL):
    r = client.put("/profile", headers=auth, json={"version": 0, "data": data})
    assert r.status_code == 200, r.text
    return r.json()


def test_a_profile_can_be_started_from_scratch(client, auth):
    profile = create(client, auth)
    assert profile["version"] == 1
    assert profile["data"]["experience"][0]["id"] == "exp_1"
    assert profile["checks"] == []
    assert profile["reviewed_at"] is None


def test_saving_bumps_the_version_and_keeps_ids(client, auth):
    profile = create(client, auth)
    data = profile["data"]
    data["experience"][0]["bullets"].append({"id": "b_2", "text": "Mentored three engineers"})
    r = client.put("/profile", headers=auth, json={"version": 1, "data": data})
    assert r.status_code == 200
    saved = r.json()
    assert saved["version"] == 2
    assert [b["id"] for b in saved["data"]["experience"][0]["bullets"]] == ["b_1", "b_2"]


def test_a_stale_version_is_refused_not_overwritten(client, auth):
    profile = create(client, auth)
    data = profile["data"]
    assert (
        client.put("/profile", headers=auth, json={"version": 1, "data": data}).status_code == 200
    )
    # A second tab still holding version 1:
    data["basics"]["name"] = "Someone Else"
    r = client.put("/profile", headers=auth, json={"version": 1, "data": data})
    assert r.status_code == 409
    assert "another tab" in r.json()["detail"]
    assert client.get("/profile", headers=auth).json()["data"]["basics"]["name"] == "Asha Rao"


def test_creating_twice_is_a_conflict(client, auth):
    create(client, auth)
    assert (
        client.put("/profile", headers=auth, json={"version": 0, "data": FULL}).status_code == 409
    )


def test_invalid_data_is_rejected(client, auth):
    create(client, auth)
    bad = {
        **FULL,
        "experience": [
            {**FULL["experience"][0], "start": "2021-03", "end": "2020-01", "current": False}
        ],
    }
    assert client.put("/profile", headers=auth, json={"version": 1, "data": bad}).status_code == 422


def test_checks_are_recomputed_and_vanish_once_fixed(client, auth):
    data = {
        "basics": {"name": "Asha Rao"},
        "experience": [{"id": "exp_1", "company": "Finlytics", "bullets": []}],
    }
    profile = create(client, auth, data)
    assert checks_on(profile, "basics", "email")
    assert checks_on(profile, "exp_1", "start")
    assert checks_on(profile, "exp_1", "end")

    data["basics"]["email"] = "asha@example.com"
    data["experience"][0].update({"start": "2021-03", "current": True})
    profile = client.put("/profile", headers=auth, json={"version": 1, "data": data}).json()
    assert not checks_on(profile, "basics", "email")
    assert not checks_on(profile, "exp_1", "start")
    assert not checks_on(profile, "exp_1", "end")


def test_confirm_marks_the_profile_reviewed(client, auth):
    create(client, auth)
    r = client.post("/profile/confirm", headers=auth, json={"version": 1})
    assert r.status_code == 200
    assert r.json()["reviewed_at"] is not None


def test_confirm_needs_the_latest_version(client, auth):
    create(client, auth)
    client.put("/profile", headers=auth, json={"version": 1, "data": FULL})
    assert client.post("/profile/confirm", headers=auth, json={"version": 1}).status_code == 409


def test_confirm_is_refused_while_something_blocking_is_missing(client, auth):
    create(client, auth, {"basics": {"email": "asha@example.com"}})
    r = client.post("/profile/confirm", headers=auth, json={"version": 1})
    assert r.status_code == 422
    assert r.json()["detail"] == "Add your name."


def test_parse_notes_are_shown_until_the_profile_is_confirmed(client, auth, session):
    stub.answer("parse_resume", fake_parse())
    client.post("/uploads", headers=auth, files={"file": ("r.pdf", fixtures.two_column_pdf())})
    profile = client.get("/profile", headers=auth).json()
    assert profile["source_mime"] == "application/pdf"

    # Pretend the parse left a note, as a real one would.
    row = session.exec(select(Profile)).one()
    doc_id = row.source_document_id

    doc = session.get(SourceDocument, doc_id)
    doc.parse_warnings = [{"target": "", "field": None, "message": "Couldn't place “Hobbies”."}]
    session.commit()
    assert client.get("/profile", headers=auth).json()["notes"][0]["message"].startswith("Couldn't")

    version = client.get("/profile", headers=auth).json()["version"]
    client.post("/profile/confirm", headers=auth, json={"version": version})
    assert client.get("/profile", headers=auth).json()["notes"] == []


def test_old_path_shaped_notes_still_load(client, auth, session):
    stub.answer("parse_resume", fake_parse())
    doc_id = client.post(
        "/uploads", headers=auth, files={"file": ("r.pdf", fixtures.two_column_pdf())}
    ).json()["id"]

    session.expire_all()
    doc = session.get(SourceDocument, doc_id)
    doc.parse_warnings = [{"path": "experience.0.end", "message": "Old style"}]
    session.commit()
    notes = client.get(f"/uploads/{doc_id}", headers=auth).json()["notes"]
    assert notes == [{"target": "", "field": None, "message": "Old style"}]


def test_the_text_we_read_is_available(client, auth):
    stub.answer("parse_resume", fake_parse())
    doc_id = client.post(
        "/uploads", headers=auth, files={"file": ("r.docx", fixtures.resume_docx())}
    ).json()["id"]
    text = client.get(f"/uploads/{doc_id}/text", headers=auth).json()["text"]
    assert text.startswith("Asha Rao · asha.rao@example.com")
