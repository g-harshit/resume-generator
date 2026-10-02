"""Cover letters: written only from the resume, checked like tailoring."""

import json

import pymupdf
import pytest

from app.ai_providers import stub
from app.ai_providers.stub import StubProvider
from app.schemas.resume import ResumeData
from app.services.cover_letter import (
    Letter,
    LetterVerification,
    RepairedSentence,
    RepairedSentences,
    SentenceVerdict,
    check_sentence,
    facts_text,
    sentences,
    write_cover_letter,
)
from tests.test_jobs import JD, northwind
from tests.test_tailor import PROFILE, plan, ready  # noqa: F401  (ready is a fixture)

JOB = northwind("").model_dump()
OPENING = "I'd like to bring my payments work to Northwind Labs' Senior Backend Engineer role."
HONEST = "At Paylane I built a reconciliation service in Go matching 3M transactions a day."
CLOSING = "I'd welcome the chance to talk about the role."


def verdicts(flag: dict[str, str] | None = None):
    """A second check that flags the sentences whose text is in `flag`."""
    flag = flag or {}

    def answer(text):
        return LetterVerification(
            verdicts=[
                SentenceVerdict(
                    id=s["id"],
                    reasoning="",
                    adds_information=s["text"] in flag,
                    added=flag.get(s["text"], ""),
                )
                for s in json.loads(text)["sentences"]
            ]
        )

    return answer


def repair_with(text: str):
    def answer(sent):
        return RepairedSentences(
            sentences=[
                RepairedSentence(id=s["id"], text=text) for s in json.loads(sent)["sentences"]
            ]
        )

    return answer


# --- the rule checks -------------------------------------------------------------------


def test_facts_include_employers_education_and_skills():
    facts = facts_text(PROFILE)
    for fact in ["Paylane", "COEP", "Kafka", "matching 3M transactions"]:
        assert fact in facts


def test_a_number_the_resume_doesnt_have_is_caught():
    reason = check_sentence("I've led teams of 12 engineers.", facts_text(PROFILE), JD, ["Go"])
    assert "12" in reason


def test_a_number_from_the_posting_is_allowed():
    assert (
        check_sentence("The role asks for 5+ years in Go.", facts_text(PROFILE), JD, ["Go"]) is None
    )


def test_embellishing_words_are_caught_unless_the_resume_uses_them():
    reason = check_sentence(
        "I moved settlement jobs to Kafka, which improved reliability.", facts_text(PROFILE), JD, []
    )
    assert "reliabilit" in reason
    assert (
        check_sentence("I moved settlement jobs to Kafka consumers.", facts_text(PROFILE), JD, [])
        is None
    )


def test_sentences_split_on_sentence_ends_only():
    assert sentences("I built 3.5 services. They ran on AWS! Next?") == [
        "I built 3.5 services.",
        "They ran on AWS!",
        "Next?",
    ]


def test_a_skill_the_resume_doesnt_have_is_caught():
    reason = check_sentence(
        "I run services on Kubernetes every day.", facts_text(PROFILE), JD, ["Kubernetes", "Go"]
    )
    assert "Kubernetes" in reason


# --- writing -------------------------------------------------------------------------


def test_an_honest_letter_is_kept_whole():
    stub.answer("tailor", lambda text: Letter(paragraphs=[OPENING, HONEST, CLOSING]))
    stub.answer("verify_tailoring", verdicts())
    letter = write_cover_letter(PROFILE, JOB, JD, StubProvider())
    assert letter == {"text": "\n\n".join([OPENING, HONEST, CLOSING]), "removed": []}
    # The model was given the resume and posting, not contact details.
    sent = json.loads(stub.calls[0]["text"])
    assert "asha@example.com" not in stub.calls[0]["text"]
    assert sent["job"]["company"] == "Northwind Labs"


def test_a_sentence_that_invents_is_rewritten_once():
    invented = "I've run Kubernetes clusters for years."
    stub.answer(
        "tailor", lambda text: Letter(paragraphs=[OPENING, invented + " " + HONEST, CLOSING])
    )
    stub.answer("verify_tailoring", verdicts())
    stub.answer("repair_tailoring", repair_with("I've run services on AWS ECS."))
    letter = write_cover_letter(PROFILE, JOB, JD, StubProvider())
    assert letter["text"] == "\n\n".join(
        [OPENING, "I've run services on AWS ECS. " + HONEST, CLOSING]
    )
    assert letter["removed"] == []


def test_only_the_offending_sentence_is_left_out_not_its_paragraph():
    overclaim = "That work single-handedly rebuilt the whole payments stack."
    stub.answer(
        "tailor", lambda text: Letter(paragraphs=[OPENING, HONEST + " " + overclaim, CLOSING])
    )
    stub.answer("verify_tailoring", verdicts({overclaim: "rebuilt the whole payments stack"}))
    stub.answer("repair_tailoring", repair_with(overclaim))
    letter = write_cover_letter(PROFILE, JOB, JD, StubProvider())
    assert letter["text"] == "\n\n".join([OPENING, HONEST, CLOSING])  # Paylane paragraph kept
    assert letter["removed"][0]["text"] == overclaim
    assert "rebuilt the whole payments stack" in letter["removed"][0]["reason"]


def test_a_rewrite_that_repeats_another_sentence_is_said_once():
    # A real model, fixing the second sentence, returned a copy of the first.
    stub.answer(
        "tailor",
        lambda text: Letter(paragraphs=[OPENING + " It has a robust track record.", CLOSING]),
    )
    stub.answer("verify_tailoring", verdicts())
    stub.answer("repair_tailoring", repair_with(OPENING))
    letter = write_cover_letter(PROFILE, JOB, JD, StubProvider())
    assert letter["text"] == "\n\n".join([OPENING, CLOSING])


def test_a_sentence_the_rewrite_drops_is_left_out():
    stub.answer(
        "tailor",
        lambda text: Letter(paragraphs=[OPENING, "I have a proven track record.", CLOSING]),
    )
    stub.answer("verify_tailoring", verdicts())
    stub.answer("repair_tailoring", repair_with(""))
    letter = write_cover_letter(PROFILE, JOB, JD, StubProvider())
    assert letter["text"] == "\n\n".join([OPENING, CLOSING])
    assert letter["removed"][0]["text"] == "I have a proven track record."


# --- the endpoints -------------------------------------------------------------------


@pytest.fixture
def resume(client, auth, ready):  # noqa: F811
    stub.answer("tailor", lambda text: plan())
    resume = client.post(
        "/resumes", headers=auth, json={"job_id": ready, "template": "classic"}
    ).json()
    stub.answer("tailor", lambda text: Letter(paragraphs=[OPENING, HONEST, CLOSING]))
    stub.answer("verify_tailoring", verdicts())
    return resume


def test_writing_saving_and_downloading_a_letter(client, auth, resume):
    assert resume["cover_letter"] is None
    r = client.post(f"/resumes/{resume['id']}/cover-letter", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["cover_letter"]["text"].startswith(OPENING)

    edited = OPENING + "\n\nMy own paragraph."
    r = client.put(f"/resumes/{resume['id']}/cover-letter", headers=auth, json={"text": edited})
    assert r.json()["cover_letter"]["text"] == edited

    r = client.get(f"/resumes/{resume['id']}/cover-letter/pdf", headers=auth)
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"] == 'attachment; filename="Asha-Rao-Cover-Letter.pdf"'
    text = " ".join(pymupdf.open(stream=r.content, filetype="pdf")[0].get_text().split())
    assert "Dear hiring team at Northwind Labs," in text
    assert "My own paragraph." in text
    assert text.rstrip().endswith("Sincerely, Asha Rao")


def test_no_letter_yet(client, auth, resume):
    assert (
        client.put(
            f"/resumes/{resume['id']}/cover-letter", headers=auth, json={"text": "x"}
        ).status_code
        == 404
    )
    assert client.get(f"/resumes/{resume['id']}/cover-letter/pdf", headers=auth).status_code == 404


def test_someone_elses_resume_gets_no_letter(client, resume):
    other = client.post(
        "/auth/register",
        json={"email": "ravi@example.com", "password": "correct horse", "name": "Ravi"},
    ).json()["token"]
    r = client.post(
        f"/resumes/{resume['id']}/cover-letter", headers={"Authorization": f"Bearer {other}"}
    )
    assert r.status_code == 404


def test_cover_letters_per_day_are_capped(client, auth, resume, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "cover_letters_per_day", 1)
    assert client.post(f"/resumes/{resume['id']}/cover-letter", headers=auth).status_code == 200
    assert client.post(f"/resumes/{resume['id']}/cover-letter", headers=auth).status_code == 429


def test_letter_text_is_escaped_in_the_pdf_html(client, auth, resume):
    from app.rendering.render import render_letter_html

    html = render_letter_html(
        ResumeData.model_validate(resume["content"]), "<script>x</script>", "Acme", "classic"
    )
    assert "<script>x" not in html and "&lt;script&gt;" in html
