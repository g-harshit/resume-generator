"""Skill bridging: a line may name a skill the job wants only when its own words prove
it, and only by naming it."""

import json

from app.ai_providers import AIProviderError, stub
from app.ai_providers.stub import StubProvider
from app.schemas.resume import ResumeData
from app.services.bridge import (
    Claim,
    Claims,
    ClaimVerdict,
    ClaimVerification,
    Rewrite,
    Rewrites,
    RewriteVerdict,
    RewriteVerification,
    bridge,
    check_rewrite,
    missing_skills,
    names,
)

PROFILE = ResumeData.model_validate(
    {
        "basics": {"name": "Ravi Menon", "email": "ravi@example.com"},
        "experience": [
            {
                "id": "exp_1",
                "company": "Billfold",
                "title": "Backend Developer",
                "start": "2022-01",
                "current": True,
                "bullets": [
                    {"id": "b_api", "text": "Built REST APIs in Django for the billing team."},
                    {"id": "b_ship", "text": "Packaged every service with Docker."},
                    {"id": "b_deploy", "text": "Deployed services to ECS behind a load balancer."},
                ],
            }
        ],
        "skills": [{"id": "sk", "group": "", "items": ["Django", "Docker", "Python"]}],
    }
)
JOB = {"must_have": ["Python", "Kubernetes", "AWS"], "nice_to_have": [], "keywords": []}

PYTHON = Claim(skill="Python", line_id="b_api", evidence="Django", reasoning="")
KUBERNETES = Claim(skill="Kubernetes", line_id="b_ship", evidence="Docker", reasoning="")
AWS = Claim(skill="AWS", line_id="b_deploy", evidence="to ECS", reasoning="")
REWRITES = {
    "b_api": "Built REST APIs in Python (Django) for the billing team.",
    "b_ship": "Packaged every service with Docker for Kubernetes.",
    "b_deploy": "Deployed services to AWS ECS behind a load balancer.",
}


def fresh() -> tuple[ResumeData, dict]:
    resume = PROFILE.model_copy(deep=True)
    provenance = {
        b.id: {"original": b.text, "status": "kept", "attempted": None, "reason": None}
        for b in resume.experience[0].bullets
    }
    return resume, provenance


def answer(claims, proven=None, rewrites=None, clean=None):
    """Stub answers for the four steps. `proven`/`clean`: skills/line ids that pass
    (default: all)."""
    stub.answer("bridge_claims", lambda text: Claims(claims=claims))

    def judge(text):
        return ClaimVerification(
            verdicts=[
                ClaimVerdict(
                    id=i["id"],
                    reasoning="",
                    proves_skill=proven is None or i["skill"] in proven,
                )
                for i in json.loads(text)
            ]
        )

    stub.answer("judge_bridge_claims", judge)
    texts = REWRITES | (rewrites or {})
    stub.answer(
        "bridge_rewrite",
        lambda text: Rewrites(
            lines=[Rewrite(id=i["id"], text=texts[i["id"]]) for i in json.loads(text)]
        ),
    )
    stub.answer(
        "verify_bridge_rewrite",
        lambda text: RewriteVerification(
            verdicts=[
                RewriteVerdict(
                    id=i["id"],
                    reasoning="",
                    adds_anything_else=clean is not None and i["id"] not in clean,
                )
                for i in json.loads(text)
            ]
        ),
    )


def text_of(resume: ResumeData, line_id: str) -> str:
    return next(b.text for b in resume.experience[0].bullets if b.id == line_id)


def tasks() -> list[str]:
    return [c["task"] for c in stub.calls]


def test_missing_means_no_line_names_it_even_if_the_skills_list_does():
    # Python is in the Skills list, but no line shows it.
    assert missing_skills(PROFILE, JOB) == ["Python", "Kubernetes", "AWS"]
    assert missing_skills(PROFILE, {"must_have": ["Django", "REST"]}) == []


def test_a_phrase_is_named_by_its_first_word_only_when_the_rest_is_generic():
    assert names("Backend development", "a backend service")
    assert names("Distributed systems", "a distributed ledger")
    assert not names("System design", "an event-driven system")


def test_skills_the_line_proves_are_named_and_marked():
    resume, prov = fresh()
    answer([PYTHON, AWS])
    added = bridge(resume, prov, PROFILE, JOB, StubProvider())

    assert added == ["Python", "AWS"]
    assert text_of(resume, "b_api") == REWRITES["b_api"]
    assert prov["b_api"] == {
        "original": "Built REST APIs in Django for the billing team.",
        "status": "bridged",
        "skills": [{"skill": "Python", "evidence": "Django"}],
        "attempted": None,
        "reason": None,
    }
    assert tasks() == [
        "bridge_claims",
        "judge_bridge_claims",
        "bridge_rewrite",
        "verify_bridge_rewrite",
    ]
    sent = json.loads(stub.calls[0]["text"])
    assert sent["missing"] == ["Python", "Kubernetes", "AWS"]


def test_one_line_can_carry_several_skills():
    resume, prov = fresh()
    job = {"must_have": ["Python", "Backend development"]}
    backend = Claim(
        skill="Backend development", line_id="b_api", evidence="Built REST APIs", reasoning=""
    )
    answer(
        [PYTHON, backend],
        rewrites={"b_api": "Built backend REST APIs in Python (Django) for the billing team."},
    )
    bridge(resume, prov, PROFILE, job, StubProvider())
    assert [s["skill"] for s in prov["b_api"]["skills"]] == ["Python", "Backend development"]
    sent = json.loads(stub.calls[2]["text"])  # one rewrite, with both skills
    assert [(i["id"], i["skills"]) for i in sent] == [("b_api", ["Python", "Backend development"])]


def test_related_is_not_proof_the_judge_decides_before_any_rewrite():
    resume, prov = fresh()
    answer([PYTHON, KUBERNETES], proven={"Python"})  # Docker doesn't prove Kubernetes
    bridge(resume, prov, PROFILE, JOB, StubProvider())

    assert text_of(resume, "b_ship") == "Packaged every service with Docker."
    assert prov["b_ship"]["status"] == "kept"
    assert [i["id"] for i in json.loads(stub.calls[2]["text"])] == ["b_api"]


def test_an_unanswered_claim_is_not_proven():
    resume, prov = fresh()
    answer([PYTHON])
    stub.answer("judge_bridge_claims", lambda text: ClaimVerification(verdicts=[]))
    bridge(resume, prov, PROFILE, JOB, StubProvider())
    assert prov["b_api"]["status"] == "kept"
    assert tasks() == ["bridge_claims", "judge_bridge_claims"]


def test_a_quote_that_isnt_in_the_line_is_refused_before_judging():
    resume, prov = fresh()
    answer([PYTHON.model_copy(update={"evidence": "Flask"})])
    bridge(resume, prov, PROFILE, JOB, StubProvider())
    assert tasks() == ["bridge_claims"]


def test_a_skill_not_missing_or_claimed_twice_is_ignored():
    resume, prov = fresh()
    django = PYTHON.model_copy(update={"skill": "Django"})  # a line already says it
    again = PYTHON.model_copy(update={"line_id": "b_deploy", "evidence": "ECS"})
    answer([django, PYTHON, again])
    bridge(resume, prov, PROFILE, JOB, StubProvider())
    judged = json.loads(stub.calls[1]["text"])
    assert [(i["skill"], i["line"]) for i in judged] == [
        ("Python", PROFILE.experience[0].bullets[0].text)
    ]


def test_a_rewrite_may_add_the_skills_and_nothing_else():
    line = "Deployed services to ECS behind a load balancer."
    terms = ["AWS", "Terraform", "Kubernetes"]

    def why(new):
        return check_rewrite(new, line, ["AWS"], terms)

    assert why("Deployed services to AWS ECS behind a load balancer.") is None
    assert why("Deployed services to ECS behind a load balancer.") == "didn't name AWS"
    assert why("Deployed 12 services to AWS ECS behind a load balancer.") == "added a number (12)"
    assert why("Deployed services to AWS ECS with Terraform behind a load balancer.") == (
        "also mentioned Terraform"
    )
    assert why("Deployed services to AWS ECS behind a load balancer, ensuring uptime.") == (
        "added “ensuring”"
    )


def test_a_rewrite_failing_the_rules_never_reaches_the_last_check():
    resume, prov = fresh()
    answer([PYTHON], rewrites={"b_api": "Built robust REST APIs in Python (Django)."})
    bridge(resume, prov, PROFILE, JOB, StubProvider())
    assert "verify_bridge_rewrite" not in tasks()
    assert prov["b_api"]["status"] == "kept"


def test_a_rewrite_the_last_check_flags_is_not_applied():
    resume, prov = fresh()
    answer([PYTHON, AWS], clean={"b_deploy"})
    bridge(resume, prov, PROFILE, JOB, StubProvider())
    assert prov["b_api"]["status"] == "kept"
    assert prov["b_deploy"]["status"] == "bridged"


def test_bridging_again_keeps_the_persons_original_and_earlier_skills():
    resume, prov = fresh()
    answer([PYTHON])
    bridge(resume, prov, PROFILE, JOB, StubProvider())
    backend = Claim(skill="Backend development", line_id="b_api", evidence="Django", reasoning="")
    answer(
        [backend],
        rewrites={"b_api": "Built backend REST APIs in Python (Django) for the billing team."},
    )
    bridge(resume, prov, PROFILE, {"must_have": ["Backend development"]}, StubProvider())
    assert prov["b_api"]["original"] == "Built REST APIs in Django for the billing team."
    assert [s["skill"] for s in prov["b_api"]["skills"]] == ["Python", "Backend development"]


def test_nothing_missing_means_no_call():
    resume, prov = fresh()
    bridge(resume, prov, PROFILE, {"must_have": ["Django"]}, StubProvider())
    assert stub.calls == []


def test_an_ai_failure_leaves_the_resume_as_it_was():
    resume, prov = fresh()
    stub.answer("bridge_claims", AIProviderError("down"))
    assert bridge(resume, prov, PROFILE, JOB, StubProvider()) == []
    assert resume == PROFILE


def test_a_keyword_in_one_line_is_still_offered_for_the_others():
    from app.services.bridge import missing_by_line

    job = {"must_have": ["Django", "Kubernetes"]}
    per_line = missing_by_line(PROFILE, job)
    assert per_line["b_api"] == ["Kubernetes"]  # this line already says Django
    assert per_line["b_ship"] == ["Django", "Kubernetes"]  # Django is elsewhere: still offered
    assert missing_skills(PROFILE, job) == ["Kubernetes"]
