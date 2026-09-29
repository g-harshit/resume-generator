import pytest
from pydantic import ValidationError

from app.schemas.export import SCHEMA_PATH, current_schema
from app.schemas.resume import Bullet, Experience, ResumeData


def sample() -> dict:
    return {
        "basics": {"name": "Asha Rao", "email": "asha@example.com"},
        "experience": [
            {
                "company": "Finlytics",
                "title": "Backend Engineer",
                "start": "2021-03",
                "current": True,
                "bullets": [{"text": "Built a ledger"}, {"text": "Cut p99 latency"}],
            }
        ],
        "skills": [{"group": "Languages", "items": ["Go", "SQL"]}],
    }


def test_ids_are_generated_for_every_entry():
    data = ResumeData.model_validate(sample())
    exp = data.experience[0]
    assert exp.id.startswith("exp_")
    assert all(b.id.startswith("b_") for b in exp.bullets)
    assert data.skills[0].id.startswith("sk_")
    assert len(set(data.all_ids())) == len(data.all_ids())


def test_ids_survive_a_round_trip():
    data = ResumeData.model_validate(sample())
    again = ResumeData.model_validate(data.model_dump())
    assert again.all_ids() == data.all_ids()


def test_duplicate_ids_are_rejected():
    raw = sample()
    raw["experience"][0]["bullets"] = [{"id": "b_1", "text": "a"}, {"id": "b_1", "text": "b"}]
    with pytest.raises(ValidationError, match="Duplicate id"):
        ResumeData.model_validate(raw)


@pytest.mark.parametrize("value", ["2021", "2021-03", "1999-12", None])
def test_valid_dates(value):
    assert Experience(start=value).start == value


@pytest.mark.parametrize("value", ["2021-13", "03/2021", "Mar 2021", "21", "2021-3"])
def test_invalid_dates(value):
    with pytest.raises(ValidationError, match="YYYY"):
        Experience(start=value)


def test_end_before_start_is_rejected():
    with pytest.raises(ValidationError, match="before start"):
        Experience(start="2021-03", end="2020-11")
    Experience(start="2021-03", end="2021")  # same year, coarser: fine


def test_a_current_role_has_no_end_date():
    with pytest.raises(ValidationError, match="current role"):
        Experience(start="2021", end="2023", current=True)


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        ResumeData.model_validate({"basics": {"name": "A", "age": 30}})


def test_text_is_trimmed_and_capped():
    assert Bullet(text="  spaced  ").text == "spaced"
    with pytest.raises(ValidationError):
        Bullet(text="x" * 2001)


def test_all_skills_flattens_groups():
    data = ResumeData.model_validate(sample())
    assert data.all_skills() == ["Go", "SQL"]


def test_generated_typescript_schema_is_up_to_date():
    assert SCHEMA_PATH.read_text() == current_schema(), (
        "ResumeData changed: run `pnpm gen:schema` and commit packages/schema"
    )
