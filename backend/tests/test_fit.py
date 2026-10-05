"""Fitting a resume to the pages the person wants: layout, condensing, summaries."""

import json

import pytest

from app.ai_providers import stub
from app.ai_providers.stub import StubProvider
from app.rendering.render import render_html
from app.schemas.layout import Layout
from app.schemas.resume import ResumeData
from app.services import fit as fit_service
from app.services.fit import (
    Condensed,
    CondensedEntry,
    CondensedLine,
    FitError,
    Summary,
    condense,
    fill_page,
    fit_to_pages,
    write_summary,
)
from tests.test_jobs import northwind
from tests.test_tailor import PROFILE, approve_all, flag, plan, ready  # noqa: F401

JOB = northwind("").model_dump()


def merge_first(text):
    """A condenser that keeps each entry's first `target` lines word for word."""
    entries = json.loads(text)["entries"]
    return Condensed(
        entries=[
            CondensedEntry(
                id=e["id"],
                bullets=[
                    CondensedLine(text=b["text"], source_ids=[b["id"]])
                    for b in e["bullets"][: e["target"]]
                ],
            )
            for e in entries
        ]
    )


def long_resume(roles=4, lines=8) -> ResumeData:
    return ResumeData.model_validate(
        {
            "basics": {"name": "Asha Rao", "email": "asha@example.com", "phone": "1"},
            "summary": "Backend engineer building payment systems.",
            "experience": [
                {
                    "id": f"exp_{r}",
                    "company": f"Company {r}",
                    "title": "Engineer",
                    "start": f"{2022 - 2 * r}-01",
                    "end": None if r == 0 else f"{2023 - 2 * r}-12",
                    "current": r == 0,
                    "bullets": [
                        {
                            "id": f"b_{r}_{i}",
                            "text": f"Built and ran service {i} for team {r}, handling the work end to end "
                            "with careful testing and a long write-up for everyone involved.",
                        }
                        for i in range(lines)
                    ],
                }
                for r in range(roles)
            ],
        }
    )


# --- layout ---------------------------------------------------------------------------


def test_hidden_sections_are_left_out_of_the_page():
    html = render_html(PROFILE, "classic", Layout(hidden=["summary", "projects"]))
    assert "Backend engineer building payment systems." not in html
    assert "ledgerkit" not in html
    assert "Paylane" in html


def test_narrow_margins_fit_more_on_a_page():
    long = long_resume()
    normal = fit_service.count_pages(long, "classic", Layout())
    narrow = fit_service.count_pages(long, "classic", Layout(margins="narrow"))
    assert narrow <= normal
    assert "@page { margin: 10mm; }" in render_html(long, "classic", Layout(margins="narrow"))


@pytest.mark.parametrize("mm", [5, 14, 30])
def test_a_custom_margin_is_the_same_on_all_four_sides(mm):
    html = render_html(PROFILE, "classic", Layout(margins="custom", margin_mm=mm))
    assert f"@page {{ margin: {mm}mm; }}" in html
    assert f".page {{ padding: {mm}mm; }}" in html


def test_a_custom_margin_is_kept_within_limits():
    with pytest.raises(ValueError):
        Layout(margins="custom", margin_mm=2)


def test_bigger_margins_take_more_pages():
    long = long_resume(roles=5)
    small = fit_service.count_pages(long, "classic", Layout(margins="custom", margin_mm=5))
    big = fit_service.count_pages(long, "classic", Layout(margins="custom", margin_mm=30))
    assert small < big


# --- condensing -----------------------------------------------------------------------


def test_condensing_rewrites_into_fewer_lines_with_provenance():
    stub.answer(
        "tailor",
        lambda text: Condensed(
            entries=[
                CondensedEntry(
                    id="exp_pay",
                    bullets=[
                        CondensedLine(
                            text="Built a reconciliation service in Go matching 3M transactions a day, and moved settlement jobs to Kafka consumers on AWS ECS.",
                            source_ids=["b_rec", "b_kafka"],
                        )
                    ],
                )
            ]
        ),
    )
    stub.answer("verify_tailoring", approve_all)
    shorter, prov, notes = condense(PROFILE, {"exp_pay": 1}, JOB, StubProvider())
    [line] = shorter.experience[0].bullets
    assert line.id.startswith("b_") and line.id not in {"b_rec", "b_kafka"}
    assert prov[line.id]["status"] == "condensed" and prov[line.id]["sources"] == [
        "b_rec",
        "b_kafka",
    ]
    assert notes == []
    assert PROFILE.experience[0].bullets[0].id == "b_rec"  # the input isn't changed


@pytest.mark.parametrize(
    ("line", "sources"),
    [
        (
            "Built a reconciliation service in Go matching 9M transactions a day.",
            ["b_rec"],
        ),  # number
        ("Built a reconciliation service on Kubernetes.", ["b_rec"]),  # skill
        ("Built a robust reconciliation service in Go.", ["b_rec"]),  # embellishment
        ("Built the order-matching API.", ["b_api"]),  # another role's line
    ],
)
def test_a_condensed_line_that_adds_anything_falls_back_to_the_persons_own_lines(line, sources):
    stub.answer(
        "tailor",
        lambda text: Condensed(
            entries=[
                CondensedEntry(id="exp_pay", bullets=[CondensedLine(text=line, source_ids=sources)])
            ]
        ),
    )
    stub.answer("verify_tailoring", approve_all)
    shorter, prov, notes = condense(PROFILE, {"exp_pay": 2}, JOB, StubProvider())
    assert [b.id for b in shorter.experience[0].bullets] == ["b_rec", "b_kafka"]
    assert prov == {}
    assert "kept your top 2 lines" in notes[0]


def test_a_condensed_line_the_second_check_rejects_falls_back():
    good = "Built a reconciliation service in Go matching 3M transactions a day."
    stub.answer(
        "tailor",
        lambda text: Condensed(
            entries=[
                CondensedEntry(
                    id="exp_pay", bullets=[CondensedLine(text=good, source_ids=["b_rec"])]
                )
            ]
        ),
    )
    stub.answer("verify_tailoring", lambda text: flag({i["id"] for i in json.loads(text)})(text))
    shorter, prov, notes = condense(PROFILE, {"exp_pay": 1}, JOB, StubProvider())
    assert [b.id for b in shorter.experience[0].bullets] == ["b_rec"]
    assert prov == {} and notes


def test_entries_already_short_enough_cost_no_model_call():
    condense(PROFILE, {"exp_trade": 5}, JOB, StubProvider())
    assert stub.calls == []


# --- summary ---------------------------------------------------------------------------


def test_a_summary_is_written_from_the_resume():
    stub.answer(
        "write_summary",
        lambda text: Summary(text="Backend engineer building payment systems in Go and Kafka."),
    )
    stub.answer("verify_tailoring", approve_all)
    assert (
        write_summary(PROFILE, JOB, StubProvider())
        == "Backend engineer building payment systems in Go and Kafka."
    )
    sent = json.loads(stub.calls[0]["text"])
    assert "summary" not in sent["resume"]  # written fresh, not from the old one
    assert sent["previous"] == PROFILE.summary  # ...but different from it


def test_a_summary_that_embellishes_gets_a_second_try():
    drafts = iter(
        [
            "A results-driven engineer with a proven track record.",
            "Backend engineer building payment systems.",
        ]
    )
    stub.answer("write_summary", lambda text: Summary(text=next(drafts)))
    stub.answer("verify_tailoring", approve_all)
    assert (
        write_summary(PROFILE, JOB, StubProvider()) == "Backend engineer building payment systems."
    )
    assert "rejected_because" in json.loads(stub.calls[-2]["text"])


@pytest.mark.parametrize(
    ("length", "drafts", "expected"),
    [
        # Asked for shorter, the first draft is as long: a second try, which is shorter.
        ("shorter", ["Backend engineer building payment systems in Go.", "Backend engineer."], 1),
        ("longer", ["Backend engineer.", "Backend engineer building payment systems in Go."], 1),
        # Neither try gets the length right: the honest draft is still better than nothing.
        ("shorter", ["Backend engineer building payment systems in Go."] * 2, 1),
    ],
)
def test_a_summary_is_written_at_the_length_asked_for(length, drafts, expected):
    profile = PROFILE.model_copy(update={"summary": "Backend engineer building payment systems."})
    replies = iter(drafts)
    stub.answer("write_summary", lambda text: Summary(text=next(replies)))
    stub.answer("verify_tailoring", approve_all)
    assert write_summary(profile, JOB, StubProvider(), length) == drafts[expected]
    asked = json.loads(stub.calls[0]["text"])["length"]
    assert asked.startswith("Make it clearly shorter" if length == "shorter" else "Make it longer")
    assert "clearly" in json.loads(stub.calls[-2]["text"])["rejected_because"]


def test_a_summary_that_keeps_inventing_is_refused():
    stub.answer(
        "write_summary", lambda text: Summary(text="Backend engineer with 12 years on Kubernetes.")
    )
    with pytest.raises(FitError, match="couldn't write a summary"):
        write_summary(PROFILE, JOB, StubProvider())


# --- fit to pages ----------------------------------------------------------------------


def test_already_fitting_fills_the_rest_of_the_page():
    # Nothing of the person's is left out and the summary can't be written (no answer):
    # the room is used by spacing alone, and the content is untouched.
    result = fit_to_pages(PROFILE, Layout(), "classic", 1, JOB, StubProvider())
    assert (result.pages_before, result.pages_after) == (1, 1)
    assert result.resume == PROFILE
    assert result.layout.spacing and result.layout.spacing > 1
    assert "Spaced sections and lines out to use the whole page." in result.steps


def _short(resume: ResumeData, keep: int = 1) -> ResumeData:
    """`resume` with only the first `keep` lines of each role."""
    short = resume.model_copy(deep=True)
    for e in short.experience:
        e.bullets = e.bullets[:keep]
    short.projects = []
    return short


def test_filling_adds_back_the_persons_own_lines_first():
    short = _short(PROFILE)
    result = fill_page(short, Layout(), "classic", PROFILE, JOB, StubProvider())
    lines = {b.text for e in result.resume.experience for b in e.bullets}
    own = {b.text for e in PROFILE.experience for b in e.bullets}
    assert lines == own  # every line came back, and all are the person's own
    assert [p.id for p in result.resume.projects] == [p.id for p in PROFILE.projects]
    assert result.pages_after == 1
    assert any(s.startswith("Added back") for s in result.steps)


def test_filling_never_adds_a_page():
    long = PROFILE.model_copy(deep=True)
    long.experience[0].bullets = [
        long.experience[0].bullets[0].model_copy(update={"id": f"b{i}"}) for i in range(60)
    ]
    profile = long.model_copy(deep=True)
    short = long.model_copy(deep=True)
    short.experience[0].bullets = short.experience[0].bullets[:20]
    before = fit_service.count_pages(short, "classic", Layout())
    result = fill_page(short, Layout(), "classic", profile, JOB, StubProvider())
    assert result.pages_after == before
    assert fit_service.count_pages(result.resume, "classic", result.layout) == before


def test_spacing_reaches_the_rendering():
    html = render_html(PROFILE, "classic", Layout(spacing=1.5))
    assert ".section { margin-top: 1.275em; }" in html
    assert "1.275em" not in render_html(PROFILE, "classic", Layout())


def test_narrow_margins_are_tried_first(monkeypatch):
    monkeypatch.setattr(
        fit_service, "count_pages", lambda r, slug, layout: 1 if layout.margins == "narrow" else 2
    )
    result = fit_to_pages(PROFILE, Layout(), "classic", 1, JOB, StubProvider())
    assert result.layout.margins == "narrow" and result.pages_after == 1
    assert result.resume == PROFILE and stub.calls == []  # no content lost


def test_fitting_keeps_the_most_lines_for_the_latest_role():
    stub.answer("tailor", merge_first)
    stub.answer("verify_tailoring", approve_all)
    long = long_resume()
    result = fit_to_pages(long, Layout(), "classic", 1, JOB, StubProvider())
    assert result.pages_before > 1 and result.pages_after == 1
    counts = [len(e.bullets) for e in result.resume.experience]  # newest first
    assert counts == sorted(counts, reverse=True) and counts[0] > counts[-1]
    assert result.layout.pages == 1 and result.layout.margins == "narrow"


# --- the endpoints ---------------------------------------------------------------------


@pytest.fixture
def resume(client, auth, ready):  # noqa: F811
    stub.answer("tailor", lambda text: plan())
    return client.post(
        "/resumes", headers=auth, json={"job_id": ready, "template": "classic"}
    ).json()


def test_layout_is_saved_and_used_for_the_preview(client, auth, resume):
    body = {
        "version": resume["version"],
        "content": resume["content"],
        "template": "classic",
        "layout": {"margins": "narrow", "hidden": ["summary"], "pages": 1},
    }
    saved = client.put(f"/resumes/{resume['id']}", headers=auth, json=body).json()
    assert saved["layout"] == {
        "margins": "narrow",
        "hidden": ["summary"],
        "pages": 1,
        "order": None,
        "margin_mm": None,
        "hidden_header": [],
        "spacing": None,
        "font_scale": None,
    }
    html = client.get(f"/resumes/{resume['id']}/preview", headers=auth).json()["html"]
    assert "<h2>Summary</h2>" not in html


def test_a_save_without_layout_keeps_it(client, auth, resume):
    body = {
        "version": resume["version"],
        "content": resume["content"],
        "template": "classic",
        "layout": {"margins": "narrow", "hidden": [], "pages": 1},
    }
    saved = client.put(f"/resumes/{resume['id']}", headers=auth, json=body).json()
    body = {"version": saved["version"], "content": saved["content"], "template": "classic"}
    assert (
        client.put(f"/resumes/{resume['id']}", headers=auth, json=body).json()["layout"]["margins"]
        == "narrow"
    )


def test_summary_endpoint(client, auth, resume):
    stub.answer(
        "write_summary",
        lambda text: Summary(text="Backend engineer building payment systems in Go."),
    )
    r = client.post(
        f"/resumes/{resume['id']}/summary", headers=auth, json={"version": resume["version"]}
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["content"]["summary"] == "Backend engineer building payment systems in Go."
    asked = json.loads(stub.calls[-2]["text"])  # the summary call, before its check
    assert asked["length"].startswith("Keep it about as long")
    assert out["provenance"]["summary"]["status"] == "written"


def test_condense_endpoint(client, auth, resume):
    stub.answer("tailor", merge_first)
    r = client.post(
        f"/resumes/{resume['id']}/condense",
        headers=auth,
        json={"version": resume["version"], "entry_id": "exp_pay", "bullets": 1},
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["resume"]["content"]["experience"][0]["bullets"]) == 1


def test_fit_endpoint_reports_what_it_did(client, auth, resume):
    r = client.post(
        f"/resumes/{resume['id']}/fit",
        headers=auth,
        json={"version": resume["version"], "pages": 1},
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["pages_after"] == 1 and out["steps"]
    assert out["resume"]["layout"]["pages"] == 1


def test_an_ai_edit_on_a_stale_version_is_refused(client, auth, resume):
    r = client.post(
        f"/resumes/{resume['id']}/summary", headers=auth, json={"version": resume["version"] - 1}
    )
    assert r.status_code == 409


def test_an_unknown_entry_is_not_found(client, auth, resume):
    r = client.post(
        f"/resumes/{resume['id']}/condense",
        headers=auth,
        json={"version": resume["version"], "entry_id": "exp_nope", "bullets": 1},
    )
    assert r.status_code == 404


def test_a_merge_no_longer_in_the_resume_doesnt_hide_lines():
    short = _short(PROFILE)
    stale = {"b_gone": {"original": "", "status": "condensed", "sources": ["b_kafka", "b_team"]}}
    result = fill_page(short, Layout(), "classic", PROFILE, JOB, StubProvider(), stale)
    lines = {b.id for e in result.resume.experience for b in e.bullets}
    assert {"b_kafka", "b_team"} <= lines


def test_a_short_resume_is_filled_to_the_bottom_margin():
    # Larger text first, then spacing: a short resume reaches its bottom margin.
    # Half a page of content (54%) to begin with.
    result = fill_page(PROFILE, Layout(), "classic", PROFILE, JOB, StubProvider())
    pages, fill = fit_service._fill(PROFILE, "classic", result.layout)
    assert pages == 1 and fill >= fit_service.FULL
    assert result.layout.font_scale and result.layout.font_scale > 1


def test_fill_says_honestly_when_the_layout_cant_stretch_further():
    tiny = _short(PROFILE).model_copy(update={"experience": _short(PROFILE).experience[:1]})
    tiny = tiny.model_copy(update={"summary": "", "skills": [], "education": []})
    result = fill_page(tiny, Layout(), "classic", tiny, JOB, StubProvider(), add_content=False)
    assert any("as far as the layout can stretch" in s for s in result.steps)


def test_fitting_takes_out_the_fill_stretch_first():
    # Filled to one page, then a section came back and it ran to two: fitting to one
    # page undoes the stretch and fills again, without condensing anything.
    stretched = Layout(spacing=5.0, font_scale=1.2)
    assert fit_service.count_pages(PROFILE, "classic", stretched) > 1
    result = fit_to_pages(PROFILE, stretched, "classic", 1, JOB, StubProvider())
    assert result.pages_after == 1
    assert fit_service.count_pages(result.resume, "classic", result.layout) == 1
    assert result.resume == PROFILE and result.layout.margins == "normal"
    assert result.steps[0].startswith("Took out the extra spacing")
