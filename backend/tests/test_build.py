"""Building a profile from scratch: lines from notes, a summary, a fresher's layout."""

import pytest

from app.ai_providers import stub
from app.ai_providers.stub import StubProvider
from app.rendering.render import render_html
from app.schemas.layout import FRESHER_ORDER, Layout, default_layout
from app.schemas.resume import ResumeData
from app.services.draft import DraftedLines, DraftError, draft_lines
from app.services.fit import Summary
from tests.test_tailor import approve_all, flag, plan

NOTES = (
    "made a campus events app with react and firebase for our college fest, "
    "about 800 students signed up. i did the login and the event calendar."
)

FRESHER = ResumeData.model_validate(
    {
        "basics": {"name": "Riya Shah", "email": "riya@example.com"},
        "education": [
            {
                "id": "edu_1",
                "institution": "VIT Pune",
                "degree": "B.Tech",
                "field": "Computer Science",
                "start": "2021",
                "end": "2025",
                "details": "CGPA 8.7",
            }
        ],
        "skills": [{"id": "sk_1", "group": "", "items": ["React", "Firebase", "Python"]}],
        "projects": [
            {
                "id": "prj_1",
                "name": "FestApp",
                "bullets": [{"id": "bp_1", "text": "Built a campus events app in React"}],
            }
        ],
    }
)


def lines(*texts):
    return lambda text: DraftedLines(lines=list(texts))


# --- lines from notes ------------------------------------------------------------------


def test_lines_are_written_from_the_notes():
    honest = "Built the login and event calendar for a campus events app in React and Firebase"
    stub.answer("tailor", lines(honest, "Reached about 800 student sign-ups for the college fest"))
    stub.answer("verify_tailoring", approve_all)
    kept, left_out = draft_lines("project", "Project: FestApp", NOTES, FRESHER, StubProvider())
    assert kept == [honest, "Reached about 800 student sign-ups for the college fest"]
    assert left_out == []


@pytest.mark.parametrize(
    ("line", "why"),
    [
        ("Built an events app used by 1,200 students", "number"),
        ("Built an events app in React with a Node.js backend", "Node.js"),
        ("Built a scalable events app in React", "scalab"),
    ],
)
def test_a_line_that_says_more_than_the_notes_is_left_out(line, why):
    honest = "Built the login and event calendar in React"
    stub.answer("tailor", lines(honest, line))
    stub.answer("verify_tailoring", approve_all)
    kept, left_out = draft_lines("project", "Project: FestApp", NOTES, FRESHER, StubProvider())
    assert kept == [honest]
    assert left_out[0]["text"] == line and why in left_out[0]["reason"]


def test_a_line_the_second_check_flags_is_left_out():
    claim = "Led the team that built a campus events app"
    stub.answer("tailor", lines("Built the event calendar in React", claim))
    stub.answer("verify_tailoring", flag({"l1"}, "led the team"))
    kept, left_out = draft_lines("project", "Project: FestApp", NOTES, FRESHER, StubProvider())
    assert kept == ["Built the event calendar in React"]
    assert "led the team" in left_out[0]["reason"]


def test_nothing_usable_is_an_error():
    stub.answer("tailor", lines("Built an app for 5,000 users"))
    with pytest.raises(DraftError, match="stick to what you wrote"):
        draft_lines("project", "FestApp", NOTES, FRESHER, StubProvider())


def test_notes_that_are_too_thin_cost_no_call():
    with pytest.raises(DraftError, match="Write a little more"):
        draft_lines("project", "FestApp", "an app", FRESHER, StubProvider())
    assert stub.calls == []


# --- a fresher's resume ------------------------------------------------------------------


def test_a_fresher_gets_education_and_projects_first():
    assert default_layout(FRESHER).order == FRESHER_ORDER
    intern = ResumeData.model_validate(
        {**FRESHER.model_dump(), "experience": [{"title": "Software Intern", "company": "Acme"}]}
    )
    assert default_layout(intern).order == FRESHER_ORDER
    worked = ResumeData.model_validate(
        {**FRESHER.model_dump(), "experience": [{"title": "Engineer", "company": "Acme"}]}
    )
    assert default_layout(worked).order is None


def test_sections_render_in_the_layout_order():
    html = render_html(FRESHER, "classic", Layout(order=FRESHER_ORDER))
    assert html.index("<h2>Education</h2>") < html.index("<h2>Projects</h2>")
    html = render_html(FRESHER, "classic", Layout(order=["projects"]))
    assert html.index("<h2>Projects</h2>") < html.index("<h2>Education</h2>")


def test_an_order_names_every_section_once():
    assert Layout(order=["projects", "projects", "skills"]).sections() == [
        "projects",
        "skills",
        "summary",
        "experience",
        "education",
        "certifications",
    ]


def test_a_students_summary_may_mention_their_degree_and_year():
    stub.answer(
        "write_summary",
        lambda text: Summary(
            text="Computer Science student at VIT Pune graduating in 2025 who built FestApp in React."
        ),
    )
    stub.answer("verify_tailoring", approve_all)
    from app.services.fit import write_summary

    assert "2025" in write_summary(FRESHER, {}, StubProvider())


# --- the endpoints ------------------------------------------------------------------------


@pytest.fixture
def fresher(client, auth):
    client.put(
        "/profile", headers=auth, json={"version": 0, "data": FRESHER.model_dump(mode="json")}
    )
    return auth


def test_lines_endpoint(client, fresher):
    stub.answer("tailor", lines("Built the event calendar in React", "Built a mobile app in Swift"))
    stub.answer("verify_tailoring", approve_all)
    r = client.post(
        "/profile/lines",
        headers=fresher,
        json={"kind": "project", "context": "Project: FestApp", "notes": NOTES},
    )
    assert r.status_code == 200, r.text
    assert r.json()["lines"] == ["Built the event calendar in React"]
    assert r.json()["left_out"][0]["text"] == "Built a mobile app in Swift"


def test_summary_endpoint_for_a_profile(client, fresher):
    stub.answer("write_summary", lambda text: Summary(text="Computer Science student at VIT Pune."))
    stub.answer("verify_tailoring", approve_all)
    r = client.post("/profile/summary", headers=fresher, json={"length": "shorter"})
    assert r.status_code == 200, r.text
    assert r.json() == {"text": "Computer Science student at VIT Pune."}


def test_a_summary_needs_something_to_write_from(client, auth):
    client.put(
        "/profile",
        headers=auth,
        json={"version": 0, "data": {"basics": {"name": "Riya Shah"}}},
    )
    r = client.post("/profile/summary", headers=auth, json={})
    assert r.status_code == 422 and "education" in r.json()["detail"]


def test_a_new_resume_for_a_fresher_leads_with_education(client, fresher):
    client.post("/profile/confirm", headers=fresher, json={"version": 1})
    from tests.test_jobs import northwind

    stub.answer("parse_jd", northwind)
    job = client.post("/jobs", headers=fresher, json={"text": "x" * 300}).json()
    stub.answer("tailor", lambda text: plan())
    r = client.post("/resumes", headers=fresher, json={"job_id": job["id"], "template": "classic"})
    assert r.status_code == 201, r.text
    assert r.json()["layout"]["order"] == FRESHER_ORDER


@pytest.mark.parametrize(
    "draft",
    [
        "Riya Shah is a Computer Science student at VIT Pune.",
        "Computer Science student at VIT Pune. She built FestApp in React.",
        "I am a Computer Science student at VIT Pune.",
    ],
)
def test_a_summary_names_no_one_and_assumes_no_pronouns(draft):
    from app.services.tailor import not_resume_voice

    assert not_resume_voice(draft, "Riya Shah")
    assert (
        not_resume_voice("Computer Science student at VIT Pune who built FestApp.", "Riya Shah")
        is None
    )
