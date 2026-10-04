"""Skill bridging: a line may name a skill the job wants only when its own words prove
it, and only by naming it."""

import json

from app.ai_providers import AIProviderError, stub
from app.ai_providers.stub import StubProvider
from app.schemas.resume import ResumeData
from app.services.bridge import (
    Bridge,
    Bridges,
    BridgeVerdict,
    BridgeVerification,
    bridge,
    check_bridge,
    missing_skills,
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
        "skills": [{"id": "sk", "group": "", "items": ["Django", "Docker"]}],
    }
)
JOB = {"must_have": ["Python", "Kubernetes", "AWS"], "nice_to_have": [], "keywords": []}

PYTHON = Bridge(
    skill="Python",
    line_id="b_api",
    evidence="Django",
    reasoning="Django is a Python framework.",
    text="Built REST APIs in Python (Django) for the billing team.",
)
KUBERNETES = Bridge(
    skill="Kubernetes",
    line_id="b_ship",
    evidence="Docker",
    reasoning="Containers usually run on Kubernetes.",
    text="Packaged every service with Docker for Kubernetes.",
)


def fresh() -> tuple[ResumeData, dict]:
    resume = PROFILE.model_copy(deep=True)
    provenance = {
        b.id: {"original": b.text, "status": "kept", "attempted": None, "reason": None}
        for b in resume.experience[0].bullets
    }
    return resume, provenance


def verdicts(passing: set[str]):
    def answer(text):
        return BridgeVerification(
            verdicts=[
                BridgeVerdict(
                    id=i["id"],
                    reasoning="",
                    evidence_proves_skill=i["id"] in passing,
                    adds_anything_else=False,
                )
                for i in json.loads(text)
            ]
        )

    return answer


def text_of(resume: ResumeData, line_id: str) -> str:
    return next(b.text for b in resume.experience[0].bullets if b.id == line_id)


def test_missing_skills_are_the_ones_the_resume_never_names():
    assert missing_skills(PROFILE, JOB) == ["Python", "Kubernetes", "AWS"]


def test_a_skill_the_line_proves_is_named_and_marked():
    resume, prov = fresh()
    stub.answer("bridge_skills", lambda text: Bridges(bridges=[PYTHON]))
    stub.answer("verify_bridge", verdicts({"b_api"}))
    bridge(resume, prov, PROFILE, JOB, StubProvider())

    assert text_of(resume, "b_api") == PYTHON.text
    assert prov["b_api"] == {
        "original": "Built REST APIs in Django for the billing team.",
        "status": "bridged",
        "skill": "Python",
        "evidence": "Django",
        "attempted": None,
        "reason": None,
    }
    sent = json.loads(stub.calls[0]["text"])
    assert sent["missing"] == ["Python", "Kubernetes", "AWS"]
    assert {line["id"] for line in sent["lines"]} == {"b_api", "b_ship", "b_deploy"}


def test_related_is_not_used_the_verifier_has_the_last_word():
    resume, prov = fresh()
    stub.answer("bridge_skills", lambda text: Bridges(bridges=[PYTHON, KUBERNETES]))
    stub.answer("verify_bridge", verdicts({"b_api"}))  # Docker doesn't prove Kubernetes
    bridge(resume, prov, PROFILE, JOB, StubProvider())

    assert text_of(resume, "b_ship") == "Packaged every service with Docker."
    assert prov["b_ship"]["status"] == "kept"
    assert prov["b_api"]["status"] == "bridged"


def test_a_line_the_verifier_skipped_is_not_bridged():
    resume, prov = fresh()
    stub.answer("bridge_skills", lambda text: Bridges(bridges=[PYTHON]))
    stub.answer("verify_bridge", lambda text: BridgeVerification(verdicts=[]))
    bridge(resume, prov, PROFILE, JOB, StubProvider())
    assert prov["b_api"]["status"] == "kept"


def test_evidence_must_be_quoted_from_the_line():
    assert check_bridge(
        "Python", "Flask", PYTHON.text, PROFILE.experience[0].bullets[0].text,
        PROFILE.experience[0].bullets[0].text, ["Python"],
    ) == "quoted words that aren't in your line"  # fmt: skip


def test_a_bridge_may_add_the_skill_and_nothing_else():
    line = "Deployed services to ECS behind a load balancer."
    terms = ["AWS", "Terraform", "Kubernetes"]

    def why(new):
        return check_bridge("AWS", "ECS", new, line, line, terms)

    assert why("Deployed services to AWS ECS behind a load balancer.") is None
    assert why("Deployed services to ECS behind a load balancer.") == "didn't name AWS"
    assert why("Deployed 12 services to AWS ECS behind a load balancer.") == "added a number (12)"
    assert why("Deployed services to AWS ECS with Terraform behind a load balancer.") == (
        "also mentioned Terraform"
    )
    assert why("Deployed services to AWS ECS behind a load balancer, ensuring uptime.") == (
        "added “ensuring”"
    )


def test_a_bridge_failing_the_rules_never_reaches_the_verifier():
    resume, prov = fresh()
    padded = PYTHON.model_copy(update={"text": "Built robust REST APIs in Python (Django)."})
    stub.answer("bridge_skills", lambda text: Bridges(bridges=[padded]))
    bridge(resume, prov, PROFILE, JOB, StubProvider())
    assert [c["task"] for c in stub.calls] == ["bridge_skills"]
    assert prov["b_api"]["status"] == "kept"


def test_a_skill_not_missing_or_a_line_twice_is_ignored():
    resume, prov = fresh()
    django = PYTHON.model_copy(update={"skill": "Django"})  # already on the resume
    twice = Bridge(skill="AWS", line_id="b_api", evidence="Django", reasoning="", text=PYTHON.text)
    stub.answer("bridge_skills", lambda text: Bridges(bridges=[django, PYTHON, twice]))
    stub.answer("verify_bridge", verdicts({"b_api"}))
    bridge(resume, prov, PROFILE, JOB, StubProvider())
    assert prov["b_api"]["skill"] == "Python"
    assert [i["id"] for i in json.loads(stub.calls[-1]["text"])] == ["b_api"]


def test_nothing_missing_means_no_call():
    resume, prov = fresh()
    bridge(resume, prov, PROFILE, {"must_have": ["Django"]}, StubProvider())
    assert stub.calls == []


def test_an_ai_failure_leaves_the_resume_as_it_was():
    resume, prov = fresh()
    stub.answer("bridge_skills", AIProviderError("down"))
    bridge(resume, prov, PROFILE, JOB, StubProvider())
    assert resume == PROFILE
