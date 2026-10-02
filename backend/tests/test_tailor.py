"""The invention guard. Each test hands `apply_plan` a plan a model might plausibly
return and checks that what reaches the resume is still only what the person wrote."""

import json

import pytest

from app.ai_providers import AIProviderError, stub
from app.ai_providers.stub import StubProvider
from app.schemas.resume import ResumeData
from app.services.tailor import (
    PlanBullet,
    PlanEntry,
    PlanSkillGroup,
    Repair,
    Repairs,
    TailorPlan,
    Verdict,
    Verification,
    apply_plan,
    check_rewording,
    numbers_in,
    repair,
    skill_terms,
    verify,
)
from tests.test_jobs import JD, northwind

PROFILE = ResumeData.model_validate(
    {
        "basics": {"name": "Asha Rao", "email": "asha@example.com", "phone": "1"},
        "summary": "Backend engineer building payment systems.",
        "experience": [
            {
                "id": "exp_pay",
                "company": "Paylane",
                "title": "Backend Engineer",
                "start": "2021-03",
                "current": True,
                "bullets": [
                    {
                        "id": "b_rec",
                        "text": "Built a reconciliation service in Go matching 3M transactions a day.",
                    },
                    {
                        "id": "b_kafka",
                        "text": "Moved settlement jobs from cron to Kafka consumers on AWS ECS.",
                    },
                    {
                        "id": "b_team",
                        "text": "Mentored four engineers and ran the on-call rotation.",
                    },
                ],
            },
            {
                "id": "exp_trade",
                "company": "Tradewise",
                "title": "Software Engineer",
                "start": "2019-07",
                "end": "2021-02",
                "bullets": [
                    {
                        "id": "b_api",
                        "text": "Built the order-matching API serving 1,200 requests per second.",
                    },
                    {
                        "id": "b_pg",
                        "text": "Introduced Postgres table partitioning for trade history.",
                    },
                ],
            },
        ],
        "education": [{"id": "edu_1", "institution": "COEP", "degree": "B.E.", "end": "2017"}],
        "skills": [
            {"id": "sk_1", "group": "", "items": ["Go", "PostgreSQL", "Kafka", "AWS", "Redis"]}
        ],
        "projects": [
            {
                "id": "prj_1",
                "name": "ledgerkit",
                "bullets": [{"id": "b_lk", "text": "A double-entry library for Go."}],
            },
            {
                "id": "prj_2",
                "name": "dotfiles",
                "bullets": [{"id": "b_df", "text": "My shell configuration."}],
            },
        ],
    }
)
JOB = northwind("").model_dump()


def plan(**overrides) -> TailorPlan:
    base = dict(
        summary="",
        experience=[
            PlanEntry(
                id="exp_pay",
                bullets=[
                    PlanBullet(
                        source_id="b_kafka",
                        text="Moved settlement jobs from cron to Kafka consumers on AWS.",
                    ),
                    PlanBullet(
                        source_id="b_rec",
                        text="Built a Go reconciliation service matching 3M transactions daily.",
                    ),
                ],
            )
        ],
        projects=[],
        skills=[],
    )
    return TailorPlan(**(base | overrides))


def bullets(resume: ResumeData, exp_id: str) -> list[tuple[str, str]]:
    exp = next(e for e in resume.experience if e.id == exp_id)
    return [(b.id, b.text) for b in exp.bullets]


# --- what an honest plan does ---------------------------------------------------------


def test_bullets_are_chosen_reordered_and_reworded():
    resume, prov = apply_plan(PROFILE, JOB, plan())
    assert bullets(resume, "exp_pay") == [
        ("b_kafka", "Moved settlement jobs from cron to Kafka consumers on AWS."),
        ("b_rec", "Built a Go reconciliation service matching 3M transactions daily."),
    ]
    assert prov["b_rec"] == {
        "original": "Built a reconciliation service in Go matching 3M transactions a day.",
        "status": "reworded",
        "attempted": None,
        "reason": None,
    }


def test_facts_come_from_the_profile_whatever_the_plan_says():
    resume, _ = apply_plan(PROFILE, JOB, plan())
    assert resume.basics == PROFILE.basics
    assert [(e.id, e.company, e.title, e.start, e.end, e.current) for e in resume.experience] == [
        (e.id, e.company, e.title, e.start, e.end, e.current) for e in PROFILE.experience
    ]
    assert resume.education == PROFILE.education


def test_a_role_the_plan_skipped_stays_with_its_own_bullets():
    resume, prov = apply_plan(PROFILE, JOB, plan())
    assert bullets(resume, "exp_trade") == [(b.id, b.text) for b in PROFILE.experience[1].bullets]
    assert prov["b_api"]["status"] == "kept"


# --- what the guard stops ---------------------------------------------------------------


def test_a_new_number_is_reverted():
    p = plan(
        experience=[
            PlanEntry(
                id="exp_pay",
                bullets=[
                    PlanBullet(
                        source_id="b_team",
                        text="Mentored 6 engineers and ran the on-call rotation.",
                    ),
                ],
            )
        ]
    )
    resume, prov = apply_plan(PROFILE, JOB, p)
    assert bullets(resume, "exp_pay") == [
        ("b_team", "Mentored four engineers and ran the on-call rotation.")
    ]
    assert prov["b_team"]["status"] == "reverted"
    assert "6" in prov["b_team"]["reason"]
    assert prov["b_team"]["attempted"] == "Mentored 6 engineers and ran the on-call rotation."


def test_a_job_skill_slipped_into_a_line_is_reverted():
    # The posting wants Kubernetes; this line was about ECS.
    p = plan(
        experience=[
            PlanEntry(
                id="exp_pay",
                bullets=[
                    PlanBullet(
                        source_id="b_kafka",
                        text="Moved settlement jobs to Kafka consumers on Kubernetes.",
                    ),
                ],
            )
        ]
    )
    resume, prov = apply_plan(PROFILE, JOB, p)
    assert bullets(resume, "exp_pay")[0][1] == PROFILE.experience[0].bullets[1].text
    assert "Kubernetes" in prov["b_kafka"]["reason"]


def test_a_skill_moved_onto_the_wrong_job_is_reverted():
    # Kafka is real — but at Paylane, not Tradewise.
    p = plan(
        experience=[
            PlanEntry(
                id="exp_trade",
                bullets=[
                    PlanBullet(
                        source_id="b_api",
                        text="Built the order-matching API on Kafka serving 1,200 requests per second.",
                    ),
                ],
            )
        ]
    )
    _, prov = apply_plan(PROFILE, JOB, p)
    assert prov["b_api"]["status"] == "reverted"
    assert "Kafka" in prov["b_api"]["reason"]


def test_a_bullet_from_another_role_is_ignored():
    p = plan(
        experience=[
            PlanEntry(
                id="exp_trade",
                bullets=[
                    PlanBullet(
                        source_id="b_rec",
                        text="Built a reconciliation service in Go matching 3M transactions a day.",
                    ),
                    PlanBullet(
                        source_id="b_pg",
                        text="Introduced PostgreSQL partitioning for trade history.",
                    ),
                ],
            )
        ]
    )
    resume, _ = apply_plan(PROFILE, JOB, p)
    assert [i for i, _ in bullets(resume, "exp_trade")] == ["b_pg"]


def test_a_made_up_bullet_id_is_ignored_and_a_role_never_ends_up_empty():
    p = plan(
        experience=[
            PlanEntry(
                id="exp_pay",
                bullets=[
                    PlanBullet(source_id="b_invented", text="Led a 40-person platform org."),
                ],
            )
        ]
    )
    resume, _ = apply_plan(PROFILE, JOB, p)
    assert bullets(resume, "exp_pay") == [(b.id, b.text) for b in PROFILE.experience[0].bullets]


def test_an_embellished_line_is_reverted():
    p = plan(
        experience=[
            PlanEntry(
                id="exp_trade",
                bullets=[
                    PlanBullet(
                        source_id="b_pg",
                        text="Introduced Postgres table partitioning for trade history, a large initiative "
                        "that transformed how the whole company thought about data, storage and reliability.",
                    )
                ],
            )
        ]
    )
    _, prov = apply_plan(PROFILE, JOB, p)
    assert prov["b_pg"]["reason"] == "made it much longer than your original"


def test_the_jobs_name_for_the_same_thing_is_allowed():
    p = plan(
        experience=[
            PlanEntry(
                id="exp_trade",
                bullets=[
                    PlanBullet(
                        source_id="b_pg",
                        text="Introduced PostgreSQL table partitioning for trade history.",
                    ),
                ],
            )
        ]
    )
    _, prov = apply_plan(PROFILE, JOB, p)
    assert prov["b_pg"]["status"] == "reworded"


def test_skills_not_in_the_profile_are_dropped_and_none_are_lost():
    p = plan(
        skills=[
            PlanSkillGroup(group="Core", items=["Go", "Kubernetes", "postgres", "gRPC"]),
            PlanSkillGroup(group="Data", items=["Kafka"]),
        ]
    )
    resume, _ = apply_plan(PROFILE, JOB, p)
    assert [(g.group, g.items) for g in resume.skills] == [
        ("Core", ["Go", "PostgreSQL"]),  # the profile's spelling, Kubernetes and gRPC gone
        ("Data", ["Kafka"]),
        ("Other", ["AWS", "Redis"]),  # left out by the plan, kept anyway
    ]


def test_a_summary_with_facts_from_the_profile_is_used():
    p = plan(summary="Backend engineer building payment systems in Go, PostgreSQL and Kafka.")
    resume, prov = apply_plan(PROFILE, JOB, p)
    assert resume.summary.startswith("Backend engineer building payment systems in Go")
    assert prov["summary"]["status"] == "reworded"


@pytest.mark.parametrize(
    ("summary", "reason"),
    [
        ("Backend engineer with 9 years of payments experience.", "number"),
        ("Backend engineer who runs Kubernetes and gRPC at scale.", "Kubernetes"),
    ],
)
def test_a_summary_inventing_facts_falls_back_to_the_profile(summary, reason):
    resume, prov = apply_plan(PROFILE, JOB, plan(summary=summary))
    assert resume.summary == PROFILE.summary
    assert reason in prov["summary"]["reason"]


def test_projects_can_be_chosen_but_not_invented():
    p = plan(
        projects=[
            PlanEntry(
                id="prj_1",
                bullets=[
                    PlanBullet(source_id="b_lk", text="A double-entry accounting library for Go.")
                ],
            ),
            PlanEntry(id="prj_fake", bullets=[]),
        ]
    )
    resume, _ = apply_plan(PROFILE, JOB, p)
    assert [p.id for p in resume.projects] == ["prj_1"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Cut p99 from 840 ms to 190 ms", {"99", "840", "190"}),
        ("Handled 1,200 requests and 3M rows, 60% fewer", {"1200", "3m", "60%"}),
        ("Mentored four engineers", {"4"}),
    ],
)
def test_numbers_in(text, expected):
    assert numbers_in(text) == expected


def test_check_rewording_allows_a_number_written_as_a_word():
    assert check_rewording("Mentored 4 engineers.", "Mentored four engineers.", []) is None


# --- the verifier (second check) --------------------------------------------------------


def approve_all(text):
    return Verification(
        verdicts=[
            Verdict(id=i["id"], reasoning="", adds_information=False, added="")
            for i in json.loads(text)
        ]
    )


def flag(ids, added="a claim"):
    def answer(text):
        return Verification(
            verdicts=[
                Verdict(
                    id=i["id"],
                    reasoning="",
                    adds_information=i["id"] in ids,
                    added=added if i["id"] in ids else "",
                )
                for i in json.loads(text)
            ]
        )

    return answer


def test_the_verifier_sees_each_reworded_line_beside_its_original():
    resume, prov = apply_plan(PROFILE, JOB, plan())
    stub.answer("verify_tailoring", approve_all)
    verify(resume, prov, PROFILE, StubProvider())
    sent = {i["id"]: i for i in json.loads(stub.calls[-1]["text"])}
    assert set(sent) == {"b_kafka", "b_rec"}  # only reworded lines, not kept ones
    assert sent["b_rec"]["original"] == PROFILE.experience[0].bullets[0].text
    assert prov["b_rec"]["status"] == "reworded"


def test_a_line_the_verifier_flags_is_reverted():
    # What a real model wrote, which no rule caught.
    p = plan(
        experience=[
            PlanEntry(
                id="exp_pay",
                bullets=[
                    PlanBullet(
                        source_id="b_kafka",
                        text="Moved settlement jobs from cron to Kafka consumers on AWS ECS, optimizing job scheduling.",
                    ),
                ],
            )
        ]
    )
    resume, prov = apply_plan(PROFILE, JOB, p)
    assert prov["b_kafka"]["status"] == "reworded"  # the rules let it through
    stub.answer("verify_tailoring", flag({"b_kafka"}, "optimizing job scheduling"))
    verify(resume, prov, PROFILE, StubProvider())
    assert bullets(resume, "exp_pay") == [("b_kafka", PROFILE.experience[0].bullets[1].text)]
    assert prov["b_kafka"]["status"] == "reverted"
    assert "optimizing job scheduling" in prov["b_kafka"]["reason"]
    assert "optimizing" in prov["b_kafka"]["attempted"]


def test_a_line_the_verifier_skipped_is_not_trusted():
    resume, prov = apply_plan(PROFILE, JOB, plan())
    stub.answer("verify_tailoring", lambda text: Verification(verdicts=[]))
    verify(resume, prov, PROFILE, StubProvider())
    assert prov["b_rec"]["status"] == prov["b_kafka"]["status"] == "reverted"


def test_a_summary_the_verifier_flags_falls_back():
    resume, prov = apply_plan(
        PROFILE, JOB, plan(summary="Backend engineer building payment systems in Go.")
    )
    stub.answer("verify_tailoring", flag({"summary"}))
    verify(resume, prov, PROFILE, StubProvider())
    assert resume.summary == PROFILE.summary


def test_nothing_reworded_means_no_verifier_call():
    resume, prov = apply_plan(PROFILE, JOB, plan(experience=[]))
    verify(resume, prov, PROFILE, StubProvider())
    assert stub.calls == []


# --- the repair round ------------------------------------------------------------------


def test_a_rejected_line_gets_one_more_try_and_keeps_the_good_one():
    p = plan(
        experience=[
            PlanEntry(
                id="exp_pay",
                bullets=[
                    PlanBullet(
                        source_id="b_team",
                        text="Mentored 6 engineers and ran the on-call rotation.",
                    ),
                ],
            )
        ]
    )
    resume, prov = apply_plan(PROFILE, JOB, p)
    assert prov["b_team"]["status"] == "reverted"
    stub.answer(
        "repair_tailoring",
        lambda text: Repairs(
            lines=[
                Repair(id="b_team", text="Ran the on-call rotation and mentored four engineers.")
            ]
        ),
    )
    stub.answer("verify_tailoring", approve_all)
    repair(resume, prov, PROFILE, JOB, StubProvider())
    assert bullets(resume, "exp_pay") == [
        ("b_team", "Ran the on-call rotation and mentored four engineers.")
    ]
    assert prov["b_team"]["status"] == "reworded"
    sent = json.loads(next(c["text"] for c in stub.calls if c["task"] == "repair_tailoring"))
    assert sent[0]["rejected"] == "Mentored 6 engineers and ran the on-call rotation."
    assert "6" in sent[0]["why"]


def test_a_second_attempt_that_still_invents_keeps_the_original():
    p = plan(
        experience=[
            PlanEntry(
                id="exp_pay",
                bullets=[
                    PlanBullet(
                        source_id="b_team",
                        text="Mentored 6 engineers and ran the on-call rotation.",
                    ),
                ],
            )
        ]
    )
    resume, prov = apply_plan(PROFILE, JOB, p)
    stub.answer(
        "repair_tailoring",
        lambda text: Repairs(lines=[Repair(id="b_team", text="Mentored 8 engineers.")]),
    )
    repair(resume, prov, PROFILE, JOB, StubProvider())
    assert (
        bullets(resume, "exp_pay")[0][1] == "Mentored four engineers and ran the on-call rotation."
    )
    assert prov["b_team"]["status"] == "reverted"


def test_a_second_attempt_the_verifier_rejects_keeps_the_original():
    p = plan(
        experience=[
            PlanEntry(
                id="exp_pay",
                bullets=[
                    PlanBullet(
                        source_id="b_team",
                        text="Mentored 6 engineers and ran the on-call rotation.",
                    ),
                ],
            )
        ]
    )
    resume, prov = apply_plan(PROFILE, JOB, p)
    stub.answer(
        "repair_tailoring",
        lambda text: Repairs(
            lines=[
                Repair(id="b_team", text="Led the on-call rotation and mentored four engineers.")
            ]
        ),
    )
    stub.answer("verify_tailoring", flag({"b_team"}, "led"))
    repair(resume, prov, PROFILE, JOB, StubProvider())
    assert (
        bullets(resume, "exp_pay")[0][1] == "Mentored four engineers and ran the on-call rotation."
    )
    assert "led" in prov["b_team"]["reason"]


def test_a_repaired_summary_that_is_the_whole_profile_is_refused():
    # A real model, told "return ORIGINAL unchanged" with the whole profile as
    # ORIGINAL, did exactly that: the summary became a dump of every line.
    resume, prov = apply_plan(PROFILE, JOB, plan(summary="Backend engineer with 9 years."))
    dump = "\n".join([PROFILE.summary, *(b.text for b in PROFILE.experience[0].bullets)])
    stub.answer("repair_tailoring", lambda text: Repairs(lines=[Repair(id="summary", text=dump)]))
    repair(resume, prov, PROFILE, JOB, StubProvider())
    assert resume.summary == PROFILE.summary
    sent = json.loads(next(c["text"] for c in stub.calls if c["task"] == "repair_tailoring"))
    assert sent[0]["original"] == PROFILE.summary and "facts" in sent[0]


def test_nothing_rejected_means_no_repair_call():
    resume, prov = apply_plan(PROFILE, JOB, plan())
    repair(resume, prov, PROFILE, JOB, StubProvider())
    assert stub.calls == []


def test_a_domain_word_is_left_to_the_verifier_not_the_skill_rule():
    # "payments" is a job keyword, not a skill: the rules let it through to the verifier.
    assert (
        check_rewording(
            "Built a payments reconciliation service in Go matching 3M transactions a day.",
            "Built a reconciliation service in Go matching 3M transactions a day.",
            skill_terms(PROFILE, JOB),
        )
        is None
    )


# --- the endpoint ------------------------------------------------------------------------


@pytest.fixture
def ready(client, auth):
    """A reviewed profile and a read job: what tailoring needs."""
    client.put(
        "/profile", headers=auth, json={"version": 0, "data": PROFILE.model_dump(mode="json")}
    )
    client.post("/profile/confirm", headers=auth, json={"version": 1})
    stub.answer("parse_jd", northwind)
    stub.answer("verify_tailoring", approve_all)
    return client.post("/jobs", headers=auth, json={"text": JD}).json()["id"]


def make(client, auth, job_id, template="classic"):
    return client.post("/resumes", headers=auth, json={"job_id": job_id, "template": template})


def test_tailoring_makes_a_resume_with_its_provenance_and_match(client, auth, ready):
    stub.answer("tailor", lambda text: plan())
    r = make(client, auth, ready)
    assert r.status_code == 201, r.text
    resume = r.json()
    assert resume["title"] == "Senior Backend Engineer — Northwind Labs"
    assert resume["template"] == "classic"
    assert resume["provenance"]["b_rec"]["status"] == "reworded"
    assert resume["match"]["total"] == resume["total"] > 0
    # The model was given the profile with its ids, but not contact details.
    sent = next(c["text"] for c in stub.calls if c["task"] == "tailor")
    assert '"b_rec"' in sent and "asha@example.com" not in sent
    assert [c["task"] for c in stub.calls[-2:]] == ["tailor", "verify_tailoring"]


def test_a_resume_is_a_snapshot(client, auth, ready):
    stub.answer("tailor", lambda text: plan())
    resume_id = make(client, auth, ready).json()["id"]
    profile = client.get("/profile", headers=auth).json()
    profile["data"]["basics"]["name"] = "Changed Later"
    client.put(
        "/profile", headers=auth, json={"version": profile["version"], "data": profile["data"]}
    )
    assert (
        client.get(f"/resumes/{resume_id}", headers=auth).json()["content"]["basics"]["name"]
        == "Asha Rao"
    )


def test_tailoring_needs_a_confirmed_profile(client, auth):
    client.put(
        "/profile", headers=auth, json={"version": 0, "data": PROFILE.model_dump(mode="json")}
    )
    stub.answer("parse_jd", northwind)
    job_id = client.post("/jobs", headers=auth, json={"text": JD}).json()["id"]
    r = make(client, auth, job_id)
    assert r.status_code == 409
    assert "confirm your profile" in r.json()["detail"]


def test_tailoring_someone_elses_job_is_not_found(client, auth, ready):
    other = client.post(
        "/auth/register",
        json={"email": "ravi@example.com", "password": "correct horse", "name": "Ravi"},
    ).json()["token"]
    r = make(client, {"Authorization": f"Bearer {other}"}, ready)
    assert r.status_code == 404


def test_an_unknown_template_is_refused(client, auth, ready):
    assert make(client, auth, ready, "fancy").status_code == 422


def test_an_ai_failure_makes_no_resume(client, auth, ready):
    stub.answer("tailor", AIProviderError("The AI service didn't respond properly."))
    assert make(client, auth, ready).status_code == 502
    assert client.get("/resumes", headers=auth).json() == []


def test_list_preview_and_pdf(client, auth, ready):
    stub.answer("tailor", lambda text: plan())
    resume_id = make(client, auth, ready).json()["id"]
    listed = client.get("/resumes", headers=auth).json()
    assert [r["id"] for r in listed] == [resume_id]
    preview = client.get(f"/resumes/{resume_id}/preview?template=modern", headers=auth).json()
    assert "Moved settlement jobs from cron to Kafka consumers on AWS." in preview["html"]
    r = client.get(f"/resumes/{resume_id}/pdf", headers=auth)
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"] == 'attachment; filename="Asha-Rao-Resume.pdf"'


def test_the_first_revision_is_stored(client, auth, ready, session):
    from sqlmodel import select

    from app.models import ResumeRevision

    stub.answer("tailor", lambda text: plan())
    resume_id = make(client, auth, ready).json()["id"]
    revisions = session.exec(
        select(ResumeRevision).where(ResumeRevision.resume_id == resume_id)
    ).all()
    assert [r.reason for r in revisions] == ["tailor"]
