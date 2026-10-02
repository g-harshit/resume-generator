"""Editing a resume, re-tailoring it, and "I have this"."""

import pytest
from sqlmodel import select

from app.ai_providers import stub
from app.models import Resume, ResumeRevision
from app.routers import resumes as resumes_router
from tests.test_tailor import PROFILE, plan, ready  # noqa: F401  (ready is a fixture)


@pytest.fixture
def resume(client, auth, ready):  # noqa: F811
    stub.answer("tailor", lambda text: plan())
    return client.post(
        "/resumes", headers=auth, json={"job_id": ready, "template": "classic"}
    ).json()


def save(client, auth, resume, **changes):
    body = {
        "version": resume["version"],
        "content": resume["content"],
        "template": resume["template"],
    }
    return client.put(f"/resumes/{resume['id']}", headers=auth, json=body | changes)


def revisions(session, resume_id):
    session.expire_all()
    return [
        r.reason
        for r in session.exec(
            select(ResumeRevision)
            .where(ResumeRevision.resume_id == resume_id)
            .order_by(ResumeRevision.created_at)
        ).all()
    ]


# --- saving --------------------------------------------------------------------------


def test_saving_edits_and_the_template(client, auth, resume):
    content = resume["content"]
    content["experience"][0]["bullets"][0]["text"] = "My own words, about Kubernetes even."
    r = save(client, auth, resume, content=content, template="modern")
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["version"] == resume["version"] + 1
    assert saved["template"] == "modern"
    # The person's edits aren't checked against the profile: it's their resume.
    assert (
        saved["content"]["experience"][0]["bullets"][0]["text"]
        == "My own words, about Kubernetes even."
    )


def test_a_stale_version_is_refused(client, auth, resume):
    assert save(client, auth, resume).status_code == 200
    r = save(client, auth, resume)  # still holding the old version
    assert r.status_code == 409
    assert "another tab" in r.json()["detail"]


def test_an_unknown_template_is_refused(client, auth, resume):
    assert save(client, auth, resume, template="fancy").status_code == 422


def test_autosaves_close_together_make_one_revision(client, auth, resume, session):
    first = save(client, auth, resume).json()
    save(client, auth, first)
    assert revisions(session, resume["id"]) == ["tailor", "edit"]


def test_edits_further_apart_make_separate_revisions(client, auth, resume, session, monkeypatch):
    from datetime import timedelta

    monkeypatch.setattr(resumes_router, "EDIT_REVISION_WINDOW", timedelta(0))
    first = save(client, auth, resume).json()
    save(client, auth, first)
    assert revisions(session, resume["id"]) == ["tailor", "edit", "edit"]


def test_someone_elses_resume_cant_be_saved(client, auth, resume):
    other = client.post(
        "/auth/register",
        json={"email": "ravi@example.com", "password": "correct horse", "name": "Ravi"},
    ).json()["token"]
    r = save(client, {"Authorization": f"Bearer {other}"}, resume)
    assert r.status_code == 404


# --- re-tailoring --------------------------------------------------------------------


def test_retailor_rebuilds_from_the_profile_as_it_is_now(client, auth, resume, session):
    profile = client.get("/profile", headers=auth).json()
    profile["data"]["basics"]["name"] = "Asha R."
    client.put(
        "/profile", headers=auth, json={"version": profile["version"], "data": profile["data"]}
    )

    r = client.post(f"/resumes/{resume['id']}/retailor", headers=auth)
    assert r.status_code == 200, r.text
    again = r.json()
    assert again["content"]["basics"]["name"] == "Asha R."
    assert again["version"] == resume["version"] + 1
    assert revisions(session, resume["id"]) == ["tailor", "retailor"]


def test_an_edit_made_while_retailoring_is_not_thrown_away(client, auth, resume, session):
    def tailor_while_someone_saves(text):
        # The editor autosaves during the 20-40 s the model takes.
        row = session.get(Resume, resume["id"])
        row.version += 1
        session.commit()
        return plan()

    stub.answer("tailor", tailor_while_someone_saves)
    r = client.post(f"/resumes/{resume['id']}/retailor", headers=auth)
    assert r.status_code == 409
    assert revisions(session, resume["id"]) == ["tailor"]


def test_retailoring_counts_towards_the_daily_cap(client, auth, resume, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "resumes_per_day", 1)
    r = client.post(f"/resumes/{resume['id']}/retailor", headers=auth)
    assert r.status_code == 429


# --- "I have this" -------------------------------------------------------------------


def add_skill(client, auth, **body):
    return client.post("/profile/skills", headers=auth, json=body)


def test_i_have_this_adds_the_skill_to_the_profile(client, auth, ready):  # noqa: F811
    r = add_skill(client, auth, skill="Kubernetes")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["bullet"] is None
    skills = [s for g in out["profile"]["data"]["skills"] for s in g["items"]]
    assert "Kubernetes" in skills
    assert out["profile"]["version"] == 2  # created at 1 (confirming keeps it); this is 2


def test_saying_where_adds_the_persons_own_line_to_that_role(client, auth, ready):  # noqa: F811
    r = add_skill(
        client,
        auth,
        skill="Kubernetes",
        entry_id="exp_pay",
        line="Ran our ECS services on Kubernetes for a year.",
    )
    out = r.json()
    paylane = next(e for e in out["profile"]["data"]["experience"] if e["id"] == "exp_pay")
    assert paylane["bullets"][-1] == out["bullet"]
    assert out["bullet"]["text"] == "Ran our ECS services on Kubernetes for a year."
    assert out["bullet"]["id"].startswith("b_")


def test_a_skill_already_in_the_profile_is_not_added_twice(client, auth, ready):  # noqa: F811
    out = add_skill(client, auth, skill="postgres").json()
    skills = [s for g in out["profile"]["data"]["skills"] for s in g["items"]]
    assert skills.count("PostgreSQL") == 1 and "postgres" not in skills


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"skill": "Kubernetes", "entry_id": "exp_pay", "line": "k8s"}, 422),
        (
            {"skill": "Kubernetes", "entry_id": "exp_nope", "line": "Ran services on Kubernetes."},
            404,
        ),
        ({"skill": ""}, 422),
    ],
)
def test_i_have_this_needs_a_real_line_and_a_real_place(client, auth, ready, body, status):  # noqa: F811
    assert add_skill(client, auth, **body).status_code == status


# --- my resumes: list, duplicate, delete -------------------------------------------------


def test_the_list_says_which_job_each_resume_is_for(client, auth, resume):
    [row] = client.get("/resumes", headers=auth).json()
    assert (row["company"], row["job_title"], row["source"]) == (
        "Northwind Labs",
        "Senior Backend Engineer",
        "paste",
    )
    assert row["covered"] is not None and row["total"] > 0


def test_duplicate_makes_an_independent_copy(client, auth, resume, session):
    r = client.post(f"/resumes/{resume['id']}/duplicate", headers=auth)
    assert r.status_code == 201
    copy = r.json()
    assert copy["id"] != resume["id"]
    assert copy["title"] == resume["title"] + " (copy)"
    assert copy["content"] == resume["content"] and copy["provenance"] == resume["provenance"]
    assert revisions(session, copy["id"]) == ["copy"]

    content = copy["content"]
    content["summary"] = "Only in the copy."
    save(client, auth, copy, content=content)
    original = client.get(f"/resumes/{resume['id']}", headers=auth).json()
    assert original["content"]["summary"] != "Only in the copy."


def test_duplicating_doesnt_count_towards_the_daily_cap(client, auth, resume, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "resumes_per_day", 1)
    assert client.post(f"/resumes/{resume['id']}/duplicate", headers=auth).status_code == 201


def test_delete_removes_the_resume_and_its_history_but_not_the_job(client, auth, resume, session):
    assert client.delete(f"/resumes/{resume['id']}", headers=auth).status_code == 204
    assert client.get(f"/resumes/{resume['id']}", headers=auth).status_code == 404
    assert revisions(session, resume["id"]) == []
    assert client.get(f"/jobs/{resume['job_id']}", headers=auth).status_code == 200


def test_someone_elses_resume_cant_be_deleted_or_copied(client, auth, resume):
    other = client.post(
        "/auth/register",
        json={"email": "ravi@example.com", "password": "correct horse", "name": "Ravi"},
    ).json()["token"]
    headers = {"Authorization": f"Bearer {other}"}
    assert client.delete(f"/resumes/{resume['id']}", headers=headers).status_code == 404
    assert client.post(f"/resumes/{resume['id']}/duplicate", headers=headers).status_code == 404
