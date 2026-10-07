import pytest

from app.schemas.resume import ResumeData
from app.services.match import appears_in, match, normalise

PROFILE = ResumeData.model_validate(
    {
        "basics": {"name": "Asha Rao", "headline": "Backend Engineer"},
        "summary": "Backend engineer building payment systems.",
        "experience": [
            {
                "id": "exp_pay",
                "company": "Paylane",
                "title": "Senior Backend Engineer",
                "bullets": [
                    {"text": "Built REST APIs in Go on AWS ECS, deployed with Terraform."},
                    {"text": "Moved settlement jobs to Kafka consumers."},
                ],
            },
            {
                "id": "exp_trade",
                "company": "Tradewise",
                "title": "Software Engineer",
                "bullets": [
                    {"text": "We had to go to market fast; the rest of the team used react hooks."}
                ],
            },
        ],
        "skills": [{"group": "Data", "items": ["Postgres", "Redis"]}],
        "projects": [
            {"id": "prj_1", "name": "ledgerkit", "bullets": [{"text": "A C++ ledger engine."}]}
        ],
    }
)


def covered(result, list_name):
    return {m.term: m.covered for m in result[list_name]}


def where(result, term):
    for name in ("must_have", "nice_to_have", "keywords"):
        for m in result[name]:
            if m.term == term:
                return [(e.section, e.label) for e in m.where]
    raise KeyError(term)


@pytest.mark.parametrize(
    ("a", "b"),
    [("Postgres", "PostgreSQL"), ("k8s", "Kubernetes"), ("golang", "Go"), ("CI/CD", "cicd")],
)
def test_synonyms_fold_together(a, b):
    assert normalise(a) == normalise(b)


def test_a_listed_skill_counts_under_any_spelling():
    r = match(PROFILE, ["PostgreSQL"], [], [])
    assert covered(r, "must_have") == {"PostgreSQL": True}
    assert where(r, "PostgreSQL") == [("skills", "Skills")]


def test_a_skill_used_in_a_bullet_counts_and_says_where():
    r = match(PROFILE, ["Kafka", "Terraform"], [], [])
    assert covered(r, "must_have") == {"Kafka": True, "Terraform": True}
    assert where(r, "Kafka") == [("experience", "Paylane")]


def test_missing_skills_are_not_covered():
    r = match(PROFILE, ["Kubernetes"], ["GraphQL"], [])
    assert covered(r, "must_have") == {"Kubernetes": False}
    assert covered(r, "nice_to_have") == {"GraphQL": False}
    assert (r["covered"], r["total"]) == (0, 2)


def test_ambiguous_words_only_count_written_as_the_technology():
    r = match(PROFILE, ["Go", "REST", "React"], [], [])
    # "Go" and "REST" at Paylane count; "go to market", "the rest of the team" and
    # lower-case "react hooks" at Tradewise don't.
    assert where(r, "Go") == [("experience", "Paylane")]
    assert where(r, "REST") == [("experience", "Paylane")]
    assert covered(r, "must_have")["React"] is False


def test_symbols_in_names_match_exactly():
    r = match(PROFILE, ["C++", "C#", "C"], [], [])
    assert covered(r, "must_have") == {"C++": True, "C#": False, "C": False}


def test_a_term_in_two_lists_is_counted_once_in_the_stronger():
    r = match(PROFILE, ["Kafka", "kafka"], ["Kafka", "Redis"], ["Redis", "payments"])
    assert [m.term for m in r["must_have"]] == ["Kafka"]
    assert [m.term for m in r["nice_to_have"]] == ["Redis"]
    assert [m.term for m in r["keywords"]] == ["payments"]
    assert (r["covered"], r["total"]) == (2, 2)  # keywords aren't scored


def test_display_names_use_the_usual_spelling():
    r = match(PROFILE, ["postgres", "k8s"], [], [])
    assert [m.term for m in r["must_have"]] == ["PostgreSQL", "Kubernetes"]


def test_appears_in_checks_the_job_text_itself():
    text = "You'll run services on K8s and Postgres. Nice: Go."
    assert appears_in("Kubernetes", text)
    assert appears_in("PostgreSQL", text)
    assert appears_in("Go", text)
    assert not appears_in("AWS", text)


def test_a_bracketed_other_name_counts_and_the_plain_name_is_shown():
    profile = PROFILE.model_copy(deep=True)
    profile.skills[0].items.append("K8s")
    r = match(profile, ["Kubernetes (K8s)"], [], [])
    assert [(m.term, m.covered) for m in r["must_have"]] == [("Kubernetes", True)]


def test_singular_and_plural_both_count():
    r = match(PROFILE, [], [], ["payments", "Kafka consumer", "settlements", "address"])
    # summary says "payment systems"; Paylane says "Kafka consumers" and "settlement jobs".
    assert {m.term: m.covered for m in r["keywords"]} == {
        "payments": True,
        "Kafka consumer": True,
        "settlements": True,
        "address": False,  # "-ss" is not a plural
    }


@pytest.mark.parametrize(
    ("term", "line"),
    [
        ("e-commerce", "Built checkout for an ecommerce marketplace."),
        ("High-throughput systems", "Built for high throughput and low latency."),
        ("Backend development", "Owned the backend for payouts."),
    ],
)
def test_coverage_accepts_what_the_editor_accepts(term, line):
    # A keyword the editor worked into a line must leave "missing" in the panel.
    data = ResumeData.model_validate(
        {
            "basics": {"name": "A"},
            "experience": [{"id": "e", "company": "C", "bullets": [{"id": "b", "text": line}]}],
        }
    )
    assert match(data, [term], [], [])["covered"] == 1


def test_a_job_with_no_skills_listed_is_scored_on_its_keywords():
    data = ResumeData.model_validate(
        {
            "basics": {"name": "A"},
            "experience": [
                {
                    "id": "e",
                    "company": "C",
                    "bullets": [{"id": "b", "text": "Ran the trainee program."}],
                }
            ],
        }
    )
    result = match(data, [], [], ["trainee program", "risk solutions", "life insurance"])
    assert (result["covered"], result["total"]) == (1, 3)


@pytest.mark.parametrize(
    ("degree", "term", "covered"),
    [
        ("B.COM (HONS)", "Bachelor's degree", True),
        ("M.B.A.", "Bachelor's degree", True),  # a higher degree meets it
        ("B.Tech", "Master's degree in Computer Science", False),
        ("PGDM", "Master's degree", True),
        ("12TH", "Bachelor's degree", False),
        ("B.E.", "Degree in Engineering", True),
    ],
)
def test_degree_requirements_are_checked_against_education(degree, term, covered):
    data = ResumeData.model_validate(
        {"basics": {"name": "A"}, "education": [{"id": "ed", "institution": "X", "degree": degree}]}
    )
    assert match(data, [term], [], [])["covered"] == int(covered)
