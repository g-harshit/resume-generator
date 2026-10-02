"""A pasted (or clipped) job description → what the job asks for.

The model reads the posting into `ParsedJob`; code then drops any skill or keyword
that isn't actually written in it. Models like to "helpfully" add AWS to a job that
says "cloud": that would send a user off to add a skill the employer never asked for.
"""

import hashlib
import re

from pydantic import BaseModel
from sqlmodel import Session, select

from app.ai_providers import AIProvider
from app.models import JobDescription
from app.services.match import appears_in

MIN_TEXT_CHARS = 200
MAX_TEXT_CHARS = 30_000


class JobTextError(Exception):
    """The text can't be a job description. `str()` is shown to the user."""


class ParsedJob(BaseModel):
    title: str
    company: str
    location: str
    # As written: "Senior", "5+ years", "Mid-level". "" if the posting doesn't say.
    seniority: str
    must_have: list[str]
    nice_to_have: list[str]
    # Other terms the posting leans on that an ATS may scan for: domains ("payments"),
    # practices ("on-call", "code review"), certifications.
    keywords: list[str]


INSTRUCTIONS = """\
You read a job posting and list what it asks for. The text may include page clutter
(navigation, "apply now", similar jobs); ignore it.

- title, company, location: as the posting states them; empty string if not stated.
- seniority: the level or experience asked for, as written ("Senior", "5+ years");
  empty string if not stated.
- must_have: skills, technologies, tools and qualifications the posting requires.
  Short names, one per item ("PostgreSQL", "Kubernetes", "Product analytics").
- nice_to_have: the ones it lists as preferred, a plus, bonus, or nice to have.
- keywords: other specific terms the posting emphasises that a resume screener would
  look for (a domain like "payments", a practice like "on-call"), up to 10.
- Use only words that appear in the posting. Never add a skill it doesn't mention,
  even one that usually goes with the job. Soft skills ("team player") are not
  skills: leave them out.
"""


def normalise_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalise_text(text).lower().encode()).hexdigest()


def check_text(text: str) -> str:
    text = text.strip()
    if len(text) < MIN_TEXT_CHARS:
        raise JobTextError(
            "That's too short to be a job description. Paste the whole posting, "
            "including the requirements."
        )
    if len(text) > MAX_TEXT_CHARS:
        raise JobTextError("That's much longer than a job description. Paste just the one posting.")
    return text


def is_written(term: str, text: str) -> bool:
    """Does the posting actually say `term`? Generous about how the model phrased it
    ("Kubernetes (K8s)" when the posting says "K8s"; "AWS ECS" for "AWS (ECS, EKS)"),
    strict about whether the thing is there at all."""
    if appears_in(term, text):
        return True
    alternatives = [a.strip() for a in re.split(r"[()/,]", term) if a.strip()]
    if any(appears_in(a, text) for a in alternatives):
        return True
    words = re.findall(r"[\w+#.]+", term)
    return bool(words) and all(appears_in(w, text) for w in words)


def _keep_written(terms: list[str], text: str, limit: int) -> list[str]:
    seen: set[str] = set()
    out = []
    for term in terms:
        term = term.strip()[:80]
        if term and term.lower() not in seen and is_written(term, text):
            seen.add(term.lower())
            out.append(term)
    return out[:limit]


def parse_job(text: str, provider: AIProvider) -> dict:
    parsed = provider.extract(
        task="parse_jd", instructions=INSTRUCTIONS, text=text, schema=ParsedJob
    )
    return {
        "title": parsed.title.strip()[:200],
        "company": parsed.company.strip()[:200],
        "location": parsed.location.strip()[:200],
        "seniority": parsed.seniority.strip()[:200],
        "must_have": _keep_written(parsed.must_have, text, 30),
        "nice_to_have": _keep_written(parsed.nice_to_have, text, 20),
        "keywords": _keep_written(parsed.keywords, text, 10),
    }


def find_existing(session: Session, user_id: int, text: str) -> JobDescription | None:
    return session.exec(
        select(JobDescription).where(
            JobDescription.user_id == user_id,
            JobDescription.content_hash == content_hash(text),
        )
    ).first()
