import pytest

from app.ai_providers import stub
from app.ai_providers.stub import StubProvider
from app.services.parse_resume import (
    MAX_TEXT_CHARS,
    ParsedResume,
    PBasics,
    PExperience,
    PSkillGroup,
    PUnclear,
    TooLongError,
    parse_resume,
    read_date,
    to_resume_data,
)

SOURCE = """Asha Rao
asha.rao@example.com  +91 90000 00000
Backend Engineer, Finlytics   Mar 2021 – Present
• Designed a double-entry ledger service in Go
  handling 2.1M transactions a day.
Software Engineer, Cartwheel   Jul 2019 – 21
• Built the order-routing service in Go serving 40 warehouses.
Skills: Go, PostgreSQL, go, Kafka
"""


def parsed(**overrides) -> ParsedResume:
    base = dict(
        basics=PBasics(
            name="Asha Rao",
            headline="",
            email="asha.rao@example.com",
            phone="+91 90000 00000",
            location="",
            links=[],
        ),
        summary="",
        experience=[
            PExperience(
                company="Finlytics",
                title="Backend Engineer",
                location="",
                start="Mar 2021",
                end="Present",
                bullets=[
                    "Designed a double-entry ledger service in Go handling 2.1M transactions a day."
                ],
            ),
            PExperience(
                company="Cartwheel",
                title="Software Engineer",
                location="",
                start="Jul 2019",
                end="21",
                bullets=["Built the order-routing service in Go serving 40 warehouses."],
            ),
        ],
        education=[],
        skills=[PSkillGroup(group="", items=["Go", "PostgreSQL", "go", " Kafka ", ""])],
        projects=[],
        certifications=[],
        unclear=[PUnclear(section="experience.1.end", detail="End date reads “Jul 2019 – 21”.")],
    )
    return ParsedResume(**(base | overrides))


def paths(warnings):
    return [w["path"] for w in warnings]


def test_a_clean_parse_becomes_resume_data_with_ids():
    data, _ = to_resume_data(parsed(), SOURCE)
    assert data.basics.name == "Asha Rao"
    assert [e.company for e in data.experience] == ["Finlytics", "Cartwheel"]
    assert data.experience[0].start == "2021-03"
    assert data.experience[0].current and data.experience[0].end is None
    assert data.experience[0].id.startswith("exp_")
    assert data.experience[0].bullets[0].id.startswith("b_")


def test_a_bullet_broken_across_lines_still_counts_as_verbatim():
    _, warnings = to_resume_data(parsed(), SOURCE)
    assert not any(".bullets." in p for p in paths(warnings))


def test_a_bullet_that_is_not_in_the_file_is_flagged():
    exp = (
        parsed()
        .experience[0]
        .model_copy(update={"bullets": ["Led a team of 40 engineers across three continents."]})
    )
    _, warnings = to_resume_data(parsed(experience=[exp]), SOURCE)
    assert "experience.0.bullets.0" in paths(warnings)


def test_a_bare_two_digit_year_is_flagged_not_guessed():
    # What a real model did with "Jul 2019 – 21" when asked for YYYY-MM: "2021",
    # month dropped, no warning. Now it copies "21" and code refuses to guess.
    data, warnings = to_resume_data(parsed(), SOURCE)
    cartwheel = data.experience[1]
    assert cartwheel.start == "2019-07" and cartwheel.end is None and not cartwheel.current
    assert {
        "path": "experience.1.end",
        "message": "We couldn't read the date “21”. Please enter it.",
    } in warnings


def test_end_before_start_is_dropped_and_flagged():
    exp = parsed().experience[1].model_copy(update={"start": "May 2021", "end": "Jan 2020"})
    data, warnings = to_resume_data(parsed(experience=[exp]), SOURCE)
    assert data.experience[0].end is None
    assert "experience.0.end" in paths(warnings)


@pytest.mark.parametrize(
    ("text", "value", "current"),
    [
        ("2019", "2019", False),
        ("2021-03", "2021-03", False),
        ("03/2021", "2021-03", False),
        ("3.2021", "2021-03", False),
        ("Mar 2021", "2021-03", False),
        ("March, 2021", "2021-03", False),
        ("Sept. 2020", "2020-09", False),
        ("Jul '19", "2019-07", False),
        ("Summer 2020", "2020", False),
        ("Present", None, True),
        ("till date", None, True),
        ("", None, False),
    ],
)
def test_read_date_accepts_unambiguous_forms(text, value, current):
    reading = read_date(text)
    assert (reading.value, reading.current, reading.readable) == (value, current, True)


@pytest.mark.parametrize("text", ["21", "13/2021", "Foo 2021", "2021-13", "Q3 2021", "1850"])
def test_read_date_refuses_to_guess(text):
    assert read_date(text) == (None, False, False)


def test_no_end_date_at_all_asks_whether_the_role_is_current():
    exp = parsed().experience[1].model_copy(update={"end": ""})
    _, warnings = to_resume_data(parsed(experience=[exp]), SOURCE)
    assert "experience.0.end" in paths(warnings)


def test_skills_are_trimmed_and_deduplicated():
    data, _ = to_resume_data(parsed(), SOURCE)
    assert data.skills[0].items == ["Go", "PostgreSQL", "Kafka"]


def test_what_the_model_found_unclear_is_passed_on():
    _, warnings = to_resume_data(parsed(), SOURCE)
    assert {"path": "experience.1.end", "message": "End date reads “Jul 2019 – 21”."} in warnings


def test_missing_contact_details_are_flagged():
    basics = parsed().basics.model_copy(update={"email": "", "phone": ""})
    _, warnings = to_resume_data(parsed(basics=basics), SOURCE)
    assert {"basics.email", "basics.phone"} <= set(paths(warnings))


def test_parse_resume_sends_the_text_to_the_provider():
    stub.answer("parse_resume", lambda text: parsed())
    data, _ = parse_resume(SOURCE, StubProvider())
    assert data.basics.email == "asha.rao@example.com"
    assert stub.calls[0]["text"] == SOURCE
    assert "Never invent" in stub.calls[0]["instructions"]


def test_something_far_longer_than_a_resume_is_refused_before_paying_for_it():
    with pytest.raises(TooLongError):
        parse_resume("x" * (MAX_TEXT_CHARS + 1), StubProvider())
    assert stub.calls == []
