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


def about(notes, target, field=None):
    """Messages of the notes pointing at `target` (and `field`, if given)."""
    return [
        n["message"]
        for n in notes
        if n["target"] == target and (field is None or n["field"] == field)
    ]


def test_a_clean_parse_becomes_resume_data_with_ids():
    data, _ = to_resume_data(parsed(), SOURCE)
    assert data.basics.name == "Asha Rao"
    assert [e.company for e in data.experience] == ["Finlytics", "Cartwheel"]
    assert data.experience[0].start == "2021-03"
    assert data.experience[0].current and data.experience[0].end is None
    assert data.experience[0].id.startswith("exp_")
    assert data.experience[0].bullets[0].id.startswith("b_")


def test_a_bullet_broken_across_lines_still_counts_as_verbatim():
    data, notes = to_resume_data(parsed(), SOURCE)
    assert about(notes, data.experience[0].bullets[0].id) == []


def test_a_bullet_that_is_not_in_the_file_is_flagged():
    exp = (
        parsed()
        .experience[0]
        .model_copy(update={"bullets": ["Led a team of 40 engineers across three continents."]})
    )
    data, notes = to_resume_data(parsed(experience=[exp]), SOURCE)
    assert about(notes, data.experience[0].bullets[0].id, "text")


def test_a_bare_two_digit_year_is_flagged_not_guessed():
    # What a real model did with "Jul 2019 – 21" when asked for YYYY-MM: "2021",
    # month dropped, no warning. Now it copies "21" and code refuses to guess.
    data, notes = to_resume_data(parsed(), SOURCE)
    cartwheel = data.experience[1]
    assert cartwheel.start == "2019-07" and cartwheel.end is None and not cartwheel.current
    assert about(notes, cartwheel.id, "end") == ["We couldn't read the date “21”. Please enter it."]


def test_notes_follow_the_entry_not_its_position():
    data, notes = to_resume_data(parsed(), SOURCE)
    moved = data.model_copy(update={"experience": list(reversed(data.experience))})
    assert about(notes, moved.experience[0].id, "end")  # Cartwheel, now first


def test_end_before_start_is_dropped_and_flagged():
    exp = parsed().experience[1].model_copy(update={"start": "May 2021", "end": "Jan 2020"})
    data, notes = to_resume_data(parsed(experience=[exp]), SOURCE)
    assert data.experience[0].end is None
    assert "“Jan 2020” is before the start date" in about(notes, data.experience[0].id, "end")[0]


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
        ("April-2022", "2022-04", False),
        ("Apr-2022", "2022-04", False),
        ("Mar/2021", "2021-03", False),
        ("Jan - 2020", "2020-01", False),
        ("2022-Apr", "2022-04", False),
        ("2022 April", "2022-04", False),
        ("Apr’22", "2022-04", False),
        ("Summer 2020", "2020", False),
        ("Present", None, True),
        ("till date", None, True),
        ("", None, False),
    ],
)
def test_read_date_accepts_unambiguous_forms(text, value, current):
    reading = read_date(text)
    assert (reading.value, reading.current, reading.readable) == (value, current, True)


@pytest.mark.parametrize(
    "text", ["21", "13/2021", "Foo 2021", "2021-13", "Q3 2021", "1850", "Apr-22", "April"]
)
def test_read_date_refuses_to_guess(text):
    assert read_date(text) == (None, False, False)


def test_what_profile_checks_can_recompute_is_not_a_parse_note():
    # Missing contact details and dates are the live checks' job (test_profile.py);
    # repeating them here would show the user the same thing twice.
    exp = parsed().experience[1].model_copy(update={"end": ""})
    basics = parsed().basics.model_copy(update={"email": "", "phone": ""})
    data, notes = to_resume_data(parsed(experience=[exp], basics=basics), SOURCE)
    assert about(notes, data.experience[0].id) == []
    assert about(notes, "basics") == []


def test_skills_are_trimmed_and_deduplicated():
    data, _ = to_resume_data(parsed(), SOURCE)
    assert data.skills[0].items == ["Go", "PostgreSQL", "Kafka"]


def test_what_the_model_found_unclear_is_passed_on():
    _, notes = to_resume_data(parsed(), SOURCE)
    assert about(notes, "") == ["End date reads “Jul 2019 – 21”."]


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
