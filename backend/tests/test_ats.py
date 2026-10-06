"""The free ATS checker: the checks, the public endpoint, the 24-hour keep and the claim."""

from datetime import timedelta

from app.ai_providers import stub
from app.models import AtsCheck, JobDescription, utcnow
from app.rendering.render import render_html, render_pdf
from app.routers.ats import purge_expired
from app.services.ats_check import analyse
from tests.fixtures import blank_pdf, resume_docx, two_column_pdf
from tests.test_jobs import JD, northwind
from tests.test_tailor import PROFILE
from tests.test_uploads import fake_parse

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def statuses(report: dict) -> dict[str, str]:
    return {c["id"]: c["status"] for c in report["checks"]}


def our_pdf(slug: str = "classic") -> bytes:
    return render_pdf(render_html(PROFILE, slug)).content


# --- the checks ---------------------------------------------------------------------


def test_our_own_templates_pass_the_layout_checks():
    layout = {"text", "garbled", "columns", "tables", "images", "headings", "dates", "file"}
    for slug in ("classic", "modern", "compact", "executive"):
        s = statuses(analyse(our_pdf(slug), PDF, "r.pdf"))
        assert {k: v for k, v in s.items() if k in layout and v != "pass"} == {}, slug


def test_two_columns_are_flagged_and_the_text_shows_how_they_read():
    report = analyse(two_column_pdf(), PDF, "r.pdf")
    assert statuses(report)["columns"] == "warn"
    # Read straight across, a sidebar's lines sit beside the main column's.
    assert "Experience" in report["ats_text"] and "asha.rao@example.com" in report["ats_text"]


def test_a_scan_has_no_text_to_read():
    assert statuses(analyse(blank_pdf(), PDF, "r.pdf"))["text"] == "fail"


def test_word_header_contact_details_and_tables_are_flagged():
    s = statuses(analyse(resume_docx(contact_in_header=True), DOCX, "r.docx"))
    assert s["header_footer"] == "fail" and s["tables"] == "warn"
    assert (
        statuses(analyse(resume_docx(contact_in_header=False), DOCX, "r.docx"))["header_footer"]
        == "pass"
    )


# --- the endpoint -------------------------------------------------------------------


def check(client, data=None, name="resume.pdf", job_text=""):
    return client.post(
        "/ats-check",
        files={"file": (name, data if data is not None else our_pdf())},
        data={"job_text": job_text} if job_text else {},
    )


def test_anyone_can_check_a_resume_without_an_account(client):
    r = check(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body["token"]) >= 24
    assert body["report"]["file_type"] == "pdf" and body["report"]["keywords"] is None
    assert client.get(f"/ats-check/{body['token']}").json()["report"] == body["report"]


def test_a_pasted_job_adds_keyword_coverage(client):
    stub.answer("parse_jd", northwind)
    report = check(client, job_text=JD).json()["report"]
    kw = report["keywords"]
    assert kw["job_title"] == "Senior Backend Engineer — Northwind Labs"
    assert "Kafka" in kw["covered"] and "Kubernetes (K8s)" in kw["missing"]


def test_only_pdf_and_word_files(client):
    assert check(client, b"hello", "r.txt").status_code == 415


def test_checks_are_limited_per_address(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "ats_checks_per_day", 2)
    assert check(client).status_code == 201
    assert check(client).status_code == 201
    assert check(client).status_code == 429


def test_a_check_is_kept_24_hours_then_deleted_with_its_file(client, session):
    from app.services.storage import get_storage

    token = check(client).json()["token"]
    row = session.get(AtsCheck, token)
    key = row.storage_key
    assert get_storage().get(key)[:5] == b"%PDF-"
    row.created_at = utcnow() - timedelta(hours=25)
    session.commit()
    assert client.get(f"/ats-check/{token}").status_code == 404
    assert purge_expired(session) == 1
    assert session.get(AtsCheck, token) is None
    try:
        get_storage().get(key)
        raise AssertionError("the file should be gone")
    except FileNotFoundError:
        pass


def test_signing_up_claims_the_file_and_the_job(client, auth, session):
    stub.answer("parse_jd", northwind)
    stub.answer("parse_resume", fake_parse())
    token = check(client, job_text=JD).json()["token"]
    calls = len(stub.calls)

    r = client.post(f"/ats-check/{token}/claim", headers=auth)
    assert r.status_code == 200, r.text
    out = r.json()
    # The file was read into the profile, as an upload is.
    upload = client.get(f"/uploads/{out['upload_id']}", headers=auth).json()
    assert upload["status"] == "done" and upload["applied"] is True
    # The job came along without being read again.
    job = session.get(JobDescription, out["job_id"])
    assert job.title == "Senior Backend Engineer"
    assert "parse_jd" not in [c["task"] for c in stub.calls[calls:]]
    # The check is gone, and can't be claimed twice.
    session.expire_all()
    assert session.get(AtsCheck, token) is None
    assert client.post(f"/ats-check/{token}/claim", headers=auth).status_code == 404


def test_claiming_needs_an_account(client):
    token = check(client).json()["token"]
    assert client.post(f"/ats-check/{token}/claim").status_code == 401
