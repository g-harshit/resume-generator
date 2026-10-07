"""A cover letter for one resume's job, with the same rule as tailoring: nothing about
the person that isn't in their resume.

The model writes the body paragraphs only; the greeting, sign-off, name and contact
details come from code. Each paragraph then gets the tailoring checks — no number and
no skill the resume doesn't have — and a second call that reads it against the
resume. A paragraph that fails gets one rewrite with the reason; if it still fails it
is left out, and the person is told what was left out and why.
"""

import json
import logging
import re

from pydantic import BaseModel

from app.ai_providers import AIProvider
from app.rendering.render import date_range, format_date
from app.schemas.resume import ResumeData
from app.services.tailor import new_numbers, new_terms, skill_terms

log = logging.getLogger(__name__)


class Letter(BaseModel):
    paragraphs: list[str]


WRITE_INSTRUCTIONS = """\
You write the body of a cover letter for one job, for the person whose resume you are
given. Return 4 paragraphs (no greeting, no sign-off, no name).

- Open with the role and why it fits them, using what the posting says about the job
  and the company.
- Then connect two or three of their real achievements from the resume to what the job
  asks for. Use the resume's own facts and numbers; don't round, inflate or combine them.
- End with a full closing paragraph of 3 or 4 sentences that reads as a natural
  conclusion, not an afterthought: link back to what the posting says the team or
  company is working on and name, from the resume, the experience they would bring to
  it ("I'd like to bring my work on payment reconciliation and Kafka-based settlement to
  Northwind's ledger platform"); say they would welcome a conversation about the role;
  and thank the reader for their time. Warm and confident, plain words. Express
  interest and intent ("I'd like to", "I'd welcome"), never promised results ("I will
  drive growth", "help scale the team", "deliver impact").

Never state anything about the person that isn't in the resume: no skill, tool,
employer, number, title, responsibility, outcome or quality they haven't written down.
That includes characterising their work: no "track record of scalable solutions",
"strong experience", "which improved reliability", "demonstrates my focus on" — state
what they did and let it speak. If the job asks for something the resume doesn't show,
leave it out; don't claim it and don't apologise for it. Plain, specific; no clichés
("I am writing to express my interest", "team player", "passionate").
"""


class SentenceVerdict(BaseModel):
    id: str
    reasoning: str  # first, so the model reasons before it answers (see tailor.Verdict)
    adds_information: bool
    added: str


class LetterVerification(BaseModel):
    verdicts: list[SentenceVerdict]


VERIFY_INSTRUCTIONS = """\
You check the sentences of a cover letter against the person's RESUME and the job
POSTING. For each sentence, decide whether it states anything about the PERSON that the
RESUME does not support: a skill, tool, employer, number, title, responsibility,
achievement, outcome, scale or quality claim.

Characterising the person or their work is a claim too: "improved reliability",
"track record of", "strong experience", "ensuring", "demonstrates my focus on",
"commitment to", "practical exposure to leadership" — unless the RESUME says exactly
that, it adds information.

Statements about the job or the company are fine when the POSTING supports them.
Plain interest in the role is fine, and so is a closing's courtesy: wanting to bring
experience the RESUME shows to work the POSTING describes ("I'd like to bring my work
on X to your Y"), welcoming a conversation, thanking the reader. A promised outcome
("supporting the team's growth", "driving impact", "helping you scale") is a claim.
Restating the resume's facts in other words is fine.

For each id, give one or two sentences of reasoning first, then the verdict, and in
`added` name what it claims that the resume doesn't support ("" if nothing). Be
strict: if unsure, it adds information.
"""

REPAIR_INSTRUCTIONS = """\
These sentences of a cover letter were rejected for claiming things the person's
RESUME doesn't support (the reason is given; CONTEXT is the paragraph around each).
Rewrite each so it states only what the RESUME supports — usually by cutting the
claim and keeping the fact. Return {id, text} for each; text "" to drop it.
"""


class RepairedSentence(BaseModel):
    id: str
    text: str


class RepairedSentences(BaseModel):
    sentences: list[RepairedSentence]


def facts_text(resume: ResumeData) -> str:
    """Everything the letter may say about the person, as text."""
    b = resume.basics
    parts = [b.name, b.headline, b.location, resume.summary]
    for e in resume.experience:
        parts.append(f"{e.title} at {e.company} ({date_range(e.start, e.end, e.current)})")
        parts += [x.text for x in e.bullets]
    for p in resume.projects:
        parts += [p.name, *(x.text for x in p.bullets)]
    for ed in resume.education:
        parts.append(f"{ed.degree} {ed.field} {ed.institution} {format_date(ed.end)}")
    for c in resume.certifications:
        parts.append(f"{c.name} {c.issuer} {format_date(c.date)}")
    parts += resume.all_skills()
    return "\n".join(p for p in parts if p)


# What models reach for when they embellish. In a sentence about the person, each is a
# claim unless the resume itself uses the word. Deterministic, so it doesn't depend on
# the second check noticing.
EMBELLISHMENTS = [
    "track record", "proven", "strong experience", "extensive experience", "deep expertise",
    "expertise in", "demonstrat", "reflecting my", "reflects my", "commitment to", "passion",
    "ensuring", "ensure", "robust", "scalab", "reliabilit", "efficien", "seamless",
    "cutting-edge", "best practice", "high-quality", "world-class", "results-driven",
    "detail-oriented", "exposure to", "excellence",
]  # fmt: skip

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“'‘(])")


def sentences(paragraph: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(paragraph) if s.strip()]


def check_sentence(text: str, facts: str, posting: str, terms: list[str]) -> str | None:
    """Rule checks. A number or skill is fine if the resume has it, or if it's about
    the job and the posting says it ("5+ years", a skill the job lists, by name)."""
    if extra := new_numbers(text, facts + "\n" + posting):
        return f"used a number that isn't in your resume ({', '.join(sorted(extra))})"
    if claimed := new_terms(text, facts, terms):
        return f"mentioned {', '.join(claimed)}, which isn't in your resume"
    if found := embellishments(text, facts):
        return f"described your work in words your resume doesn't use (“{found[0]}…”)"
    return None


def embellishments(text: str, allowed_in: str) -> list[str]:
    """Words from EMBELLISHMENTS in `text` that `allowed_in` doesn't itself use."""
    lower, allowed = text.lower(), allowed_in.lower()
    return [w.strip() for w in EMBELLISHMENTS if w in lower and w not in allowed]


def _verify(
    items: dict[str, str], facts: str, posting: str, provider: AIProvider
) -> dict[str, str]:
    """Sentence id → what it adds, for each sentence the second check rejects."""
    if not items:
        return {}
    result = provider.extract(
        task="verify_tailoring",
        instructions=VERIFY_INSTRUCTIONS,
        text=json.dumps(
            {
                "resume": facts,
                "posting": posting[:6000],
                "sentences": [{"id": k, "text": v} for k, v in items.items()],
            },
            ensure_ascii=False,
        ),
        schema=LetterVerification,
    )
    answered = {v.id for v in result.verdicts}
    flagged = {v.id: v.added for v in result.verdicts if v.adds_information and v.id in items}
    # No verdict for a sentence means it wasn't checked, and unchecked isn't approved.
    for k in items:
        if k not in answered:
            flagged[k] = "it couldn't be checked"
    return flagged


def write_cover_letter(resume: ResumeData, job: dict, posting: str, provider: AIProvider) -> dict:
    """{"text": the letter body, "removed": [{"text", "reason"}]}."""
    facts = facts_text(resume)
    # Skills the letter may not claim unless the resume has them. Job keywords are
    # left to the verifier, as in tailoring.
    terms = skill_terms(resume, job)
    letter = provider.extract(
        task="tailor",
        instructions=WRITE_INSTRUCTIONS,
        text=json.dumps(
            {
                "job": {
                    "title": job.get("title", ""),
                    "company": job.get("company", ""),
                    "posting": posting[:6000],
                },
                "resume": resume.model_dump(
                    mode="json", exclude={"basics": {"email", "phone", "links"}}
                ),
            },
            ensure_ascii=False,
        ),
        schema=Letter,
    )
    # {"p1.s0": sentence}: paragraphs and sentence order are kept in the ids.
    body: dict[str, str] = {}
    for pi, paragraph in enumerate(p for p in letter.paragraphs[:6] if p.strip()):
        for si, sentence in enumerate(sentences(paragraph)):
            body[f"p{pi}.s{si}"] = sentence

    def problems(ids: list[str]) -> dict[str, str]:
        found = {k: r for k in ids if (r := check_sentence(body[k], facts, posting, terms))}
        rest = {k: body[k] for k in ids if k not in found}
        for k, added in _verify(rest, facts, posting, provider).items():
            found[k] = f"claimed something your resume doesn't say: {added}"
        return found

    issues = problems(list(body))
    still: dict[str, str] = {}
    if issues:
        paragraph_of = {
            k: " ".join(v for j, v in body.items() if j.split(".")[0] == k.split(".")[0])
            for k in issues
        }
        repaired = provider.extract(
            task="repair_tailoring",
            instructions=REPAIR_INSTRUCTIONS,
            text=json.dumps(
                {
                    "resume": facts,
                    "sentences": [
                        {"id": k, "text": body[k], "why": why, "context": paragraph_of[k]}
                        for k, why in issues.items()
                    ],
                },
                ensure_ascii=False,
            ),
            schema=RepairedSentences,
        )
        fixes = {r.id: r.text.strip() for r in repaired.sentences if r.id in issues}
        retry = []
        for k, why in issues.items():
            if fixes.get(k):
                body[k] = fixes[k]
                retry.append(k)
            else:
                still[k] = why  # dropped by the rewrite, or not returned: leave it out
        still |= problems(retry)

    removed = [{"text": body[k], "reason": why} for k, why in still.items()]
    for item in removed:
        log.info("cover letter sentence left out: %s", item["reason"])
    paragraphs: dict[str, list[str]] = {}
    seen: set[str] = set()
    for k, sentence in body.items():
        # A rewrite sometimes returns a copy of the sentence before it; say it once.
        if k in still or sentence.lower() in seen:
            continue
        seen.add(sentence.lower())
        paragraphs.setdefault(k.split(".")[0], []).append(sentence)
    texts = [" ".join(p) for p in paragraphs.values()]
    # The closing went (every sentence of it failed a check): end plainly rather than
    # stop on a list of facts.
    last = f"p{len({k.split('.')[0] for k in body}) - 1}"
    if body and last not in paragraphs:
        texts.append(_closing(job))
    return {"text": "\n\n".join(texts), "removed": removed}


def _closing(job: dict) -> str:
    role = " ".join(x for x in (job.get("title", ""), "role") if x).strip()
    at = f" at {job['company']}" if job.get("company") else ""
    return (
        f"I'd welcome the chance to talk about the {role}{at} and how my experience fits "
        "what you're looking for. Thank you for your time and consideration."
    )
