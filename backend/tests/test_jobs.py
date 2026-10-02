import pytest

from app.ai_providers import AIProviderError, stub
from app.services.jobs import ParsedJob, content_hash, is_written

JD = """Senior Backend Engineer — Northwind Labs
Remote (India) · Full-time

About the role
You'll own the services behind our payments platform: ledgers, settlement and payouts.

What you'll need
• 5+ years building backend services, mostly in Go
• Deep Postgres — schema design, query plans, partitioning
• Services talking gRPC, deployed on K8s on AWS
• Experience with distributed systems and on-call

Nice to have
• Kafka or another event log
• Terraform
"""

PROFILE = {
    "basics": {"name": "Asha Rao", "email": "asha@example.com", "phone": "1"},
    "experience": [
        {
            "id": "exp_pay",
            "company": "Paylane",
            "title": "Backend Engineer",
            "start": "2021-03",
            "current": True,
            "bullets": [{"id": "b_1", "text": "Built gRPC services in Go, on AWS."}],
        }
    ],
    "skills": [{"id": "sk_1", "group": "", "items": ["PostgreSQL", "Kafka"]}],
}


def northwind(text):
    return ParsedJob(
        title="Senior Backend Engineer",
        company="Northwind Labs",
        location="Remote (India)",
        seniority="5+ years",
        must_have=["Go", "PostgreSQL", "gRPC", "Kubernetes (K8s)", "AWS", "Distributed systems"],
        # "Docker" isn't in the posting: a model adding what usually goes with the job.
        nice_to_have=["Kafka", "Terraform", "Docker"],
        keywords=["payments", "on-call", "ledgers"],
    )


@pytest.fixture
def with_profile(client, auth):
    assert (
        client.put("/profile", headers=auth, json={"version": 0, "data": PROFILE}).status_code
        == 200
    )


def add(client, auth, text=JD, **extra):
    return client.post("/jobs", headers=auth, json={"text": text, **extra})


def terms(job, list_name):
    return {m["term"]: m["covered"] for m in job["match"][list_name]}


def test_a_job_is_read_and_matched_against_the_profile(client, auth, with_profile):
    stub.answer("parse_jd", northwind)
    r = add(client, auth)
    assert r.status_code == 200, r.text
    job = r.json()
    assert (job["title"], job["company"], job["location"]) == (
        "Senior Backend Engineer",
        "Northwind Labs",
        "Remote (India)",
    )
    assert job["seniority"] == "5+ years"
    assert terms(job, "must_have") == {
        "Go": True,
        "PostgreSQL": True,
        "gRPC": True,
        "Kubernetes": False,
        "AWS": True,
        "Distributed systems": False,
    }
    assert terms(job, "nice_to_have") == {"Kafka": True, "Terraform": False}
    assert (job["match"]["covered"], job["match"]["total"]) == (5, 8)
    go = next(m for m in job["match"]["must_have"] if m["term"] == "Go")
    assert go["where"] == [{"section": "experience", "label": "Paylane", "id": "exp_pay"}]


def test_requirements_not_written_in_the_posting_are_dropped(client, auth, with_profile):
    stub.answer("parse_jd", northwind)
    job = add(client, auth).json()
    assert "Docker" not in terms(job, "nice_to_have")


def test_the_same_posting_twice_is_read_once(client, auth, with_profile):
    stub.answer("parse_jd", northwind)
    first = add(client, auth).json()
    # Same text, different whitespace and case.
    second = add(client, auth, JD.upper().replace("\n", "\n\n  ")).json()
    assert second["id"] == first["id"]
    assert len(stub.calls) == 1


def test_the_match_follows_the_profile(client, auth, with_profile):
    stub.answer("parse_jd", northwind)
    job_id = add(client, auth).json()["id"]
    profile = client.get("/profile", headers=auth).json()
    profile["data"]["skills"][0]["items"].append("Kubernetes")
    client.put(
        "/profile", headers=auth, json={"version": profile["version"], "data": profile["data"]}
    )
    job = client.get(f"/jobs/{job_id}", headers=auth).json()
    assert terms(job, "must_have")["Kubernetes"] is True


def test_without_a_profile_there_is_no_match_yet(client, auth):
    stub.answer("parse_jd", northwind)
    job = add(client, auth).json()
    assert job["title"] == "Senior Backend Engineer"
    assert job["match"] is None


def test_too_short_text_is_refused_before_paying_for_it(client, auth):
    r = add(client, auth, "Backend engineer, Go, Postgres.")
    assert r.status_code == 422
    assert "too short" in r.json()["detail"]
    assert stub.calls == []


def test_an_ai_failure_is_a_clear_error(client, auth):
    stub.answer("parse_jd", AIProviderError("The AI service didn't respond properly."))
    r = add(client, auth)
    assert r.status_code == 502
    assert r.json()["detail"] == "The AI service didn't respond properly."


def test_extension_jobs_keep_their_url(client, auth):
    stub.answer("parse_jd", northwind)
    job = add(client, auth, source="extension", url="https://jobs.example.com/42").json()
    assert (job["source"], job["url"]) == ("extension", "https://jobs.example.com/42")
    assert add(client, auth, source="email").status_code == 422


def test_someone_elses_job_is_not_found(client, auth):
    stub.answer("parse_jd", northwind)
    job_id = add(client, auth).json()["id"]
    other = client.post(
        "/auth/register",
        json={"email": "ravi@example.com", "password": "correct horse", "name": "Ravi"},
    ).json()["token"]
    r = client.get(f"/jobs/{job_id}", headers={"Authorization": f"Bearer {other}"})
    assert r.status_code == 404


def test_jobs_per_day_are_capped(client, auth, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "jobs_per_day", 1)
    stub.answer("parse_jd", northwind)
    assert add(client, auth).status_code == 200
    assert add(client, auth, JD + "\nAlso: Rust.").status_code == 429


@pytest.mark.parametrize(
    ("term", "written"),
    [
        ("Kubernetes (K8s)", True),
        ("AWS ECS", False),  # ECS isn't in the posting
        ("Postgres", True),
        ("Distributed systems", True),
        ("Docker", False),
        ("on-call", True),
    ],
)
def test_is_written(term, written):
    assert is_written(term, JD) is written


def test_hash_ignores_whitespace_and_case():
    assert content_hash("A  b\nC") == content_hash("a b c")
