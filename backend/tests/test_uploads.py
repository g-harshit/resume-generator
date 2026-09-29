from datetime import timedelta

from sqlmodel import select

from app.ai_providers import AIProviderError, stub
from app.models import ParseStatus, Profile, SourceDocument, utcnow
from app.services.parse_resume import ParsedResume, PBasics
from tests import fixtures


def fake_parse(name="Asha Rao"):
    def answer(text):
        return ParsedResume(
            basics=PBasics(
                name=name,
                headline="",
                email="asha.rao@example.com",
                phone="",
                location="",
                links=[],
            ),
            summary="",
            experience=[],
            education=[],
            skills=[],
            projects=[],
            certifications=[],
            unclear=[],
        )

    return answer


def upload(client, auth, data=None, filename="resume.pdf"):
    data = fixtures.two_column_pdf() if data is None else data
    return client.post("/uploads", headers=auth, files={"file": (filename, data)})


def test_upload_reads_the_resume_and_creates_the_profile(client, auth):
    stub.answer("parse_resume", fake_parse())
    r = upload(client, auth)
    assert r.status_code == 202
    doc_id = r.json()["id"]

    # TestClient runs background tasks before returning, so the parse has finished.
    status = client.get(f"/uploads/{doc_id}", headers=auth).json()
    assert status["status"] == "done"
    assert status["applied"] is True
    assert {"path": "basics.phone", "message": "No phone number found."} in status["warnings"]

    profile = client.get("/profile", headers=auth).json()
    assert profile["data"]["basics"]["name"] == "Asha Rao"
    assert profile["source_document_id"] == doc_id
    assert profile["reviewed_at"] is None
    # The model was given the extracted text, not the file.
    assert "Finlytics" in stub.calls[0]["text"]


def test_profile_is_null_before_any_upload(client, auth):
    r = client.get("/profile", headers=auth)
    assert r.status_code == 200
    assert r.json() is None


def test_the_original_file_can_be_fetched_back(client, auth):
    stub.answer("parse_resume", fake_parse())
    pdf = fixtures.two_column_pdf()
    doc_id = upload(client, auth, pdf).json()["id"]
    r = client.get(f"/uploads/{doc_id}/file", headers=auth)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == pdf


def test_word_files_work_too(client, auth):
    stub.answer("parse_resume", fake_parse())
    doc_id = upload(client, auth, fixtures.resume_docx(), "resume.docx").json()["id"]
    assert client.get(f"/uploads/{doc_id}", headers=auth).json()["status"] == "done"
    assert "asha.rao@example.com" in stub.calls[0]["text"]  # from the Word page header


def test_type_is_checked_from_the_bytes_not_the_name(client, auth):
    r = upload(client, auth, b"GIF89a not a resume", "resume.pdf")
    assert r.status_code == 415
    assert "PDF or a Word" in r.json()["detail"]


def test_files_over_5mb_are_refused(client, auth):
    r = upload(client, auth, b"%PDF-" + b"0" * (5 * 1024 * 1024))
    assert r.status_code == 413


def test_uploads_need_a_signed_in_user(client):
    assert client.post("/uploads", files={"file": ("r.pdf", b"%PDF-")}).status_code == 401


def test_someone_elses_upload_is_not_found(client, auth):
    stub.answer("parse_resume", fake_parse())
    doc_id = upload(client, auth).json()["id"]
    other = client.post(
        "/auth/register",
        json={"email": "ravi@example.com", "password": "correct horse", "name": "Ravi"},
    ).json()["token"]
    headers = {"Authorization": f"Bearer {other}"}
    assert client.get(f"/uploads/{doc_id}", headers=headers).status_code == 404
    assert client.get(f"/uploads/{doc_id}/file", headers=headers).status_code == 404


def test_a_scanned_pdf_fails_with_a_useful_message_and_no_model_call(client, auth):
    stub.answer("parse_resume", fake_parse())
    doc_id = upload(client, auth, fixtures.blank_pdf()).json()["id"]
    status = client.get(f"/uploads/{doc_id}", headers=auth).json()
    assert status["status"] == "failed"
    assert "scan or a photo" in status["error"]
    assert stub.calls == []


def test_an_ai_failure_is_reported_not_raised(client, auth):
    stub.answer("parse_resume", AIProviderError("The AI service didn't respond properly."))
    doc_id = upload(client, auth).json()["id"]
    status = client.get(f"/uploads/{doc_id}", headers=auth).json()
    assert status["status"] == "failed"
    assert status["error"] == "The AI service didn't respond properly."
    assert client.get("/profile", headers=auth).json() is None


def test_an_unexpected_crash_is_reported_without_leaking_details(client, auth):
    def boom(text):
        raise RuntimeError("secret internals")

    stub.answer("parse_resume", boom)
    doc_id = upload(client, auth).json()["id"]
    status = client.get(f"/uploads/{doc_id}", headers=auth).json()
    assert status["status"] == "failed"
    assert "secret" not in status["error"]


def test_a_new_upload_replaces_an_unreviewed_profile(client, auth):
    stub.answer("parse_resume", fake_parse("Asha Rao"))
    upload(client, auth)
    stub.answer("parse_resume", fake_parse("Asha R."))
    second = upload(client, auth).json()["id"]
    profile = client.get("/profile", headers=auth).json()
    assert profile["data"]["basics"]["name"] == "Asha R."
    assert profile["source_document_id"] == second
    assert profile["version"] == 2


def test_a_new_upload_never_silently_overwrites_a_reviewed_profile(client, auth, session):
    stub.answer("parse_resume", fake_parse("Asha Rao"))
    upload(client, auth)
    profile = session.exec(select(Profile)).one()
    profile.reviewed_at = utcnow()
    session.commit()

    stub.answer("parse_resume", fake_parse("Someone Else"))
    second = upload(client, auth).json()["id"]
    status = client.get(f"/uploads/{second}", headers=auth).json()
    assert status["status"] == "done" and status["applied"] is False
    assert client.get("/profile", headers=auth).json()["data"]["basics"]["name"] == "Asha Rao"

    # ...until the user explicitly asks for it.
    assert client.post(f"/uploads/{second}/apply", headers=auth).json()["applied"] is True
    profile = client.get("/profile", headers=auth).json()
    assert profile["data"]["basics"]["name"] == "Someone Else"
    assert profile["reviewed_at"] is None  # a new parse must be checked again


def test_a_job_killed_mid_parse_is_reported_as_failed_after_a_while(client, auth, session):
    stub.answer("parse_resume", fake_parse())
    doc_id = upload(client, auth).json()["id"]
    session.expire_all()
    doc = session.get(SourceDocument, doc_id)
    doc.parse_status = ParseStatus.RUNNING
    doc.created_at = utcnow() - timedelta(minutes=11)
    session.commit()
    status = client.get(f"/uploads/{doc_id}", headers=auth).json()
    assert status["status"] == "failed"
    assert "took too long" in status["error"]


def test_uploads_per_day_are_capped(client, auth, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "uploads_per_day", 2)
    stub.answer("parse_resume", fake_parse())
    assert upload(client, auth).status_code == 202
    assert upload(client, auth).status_code == 202
    r = upload(client, auth)
    assert r.status_code == 429
