"""Name a job's skill in a line that already shows it.

A job asks for Python; the resume never says "Python", but a line says "Built REST
APIs in Django". The person did use Python: Django is Python. So the line may say so:
"Built REST APIs in Python (Django)". That's a bridge.

A bridge is the one place tailoring adds a word the line doesn't have, so it is held
to more than a rewording is:

- the model must quote the exact words of the person's line that prove the skill
  ("Django"), and the quote must really be in that line
- the new line may add the skill and nothing else: no number, no other skill or job
  term, no padding ("robust", "scalable"), not much longer
- a second, strict call is shown the quote and the skill and answers one question:
  does that evidence mean the person used the skill? "Django" → Python, "ECS" → AWS,
  "GitHub Actions" → CI/CD: yes. "Docker" → Kubernetes, "REST APIs" → GraphQL,
  "SQL" → PostgreSQL: no. Related isn't the same as used.

Whatever fails any of that leaves the line as it was. A bridge is optional polish, so
if the model is unavailable the resume is simply returned without bridges.
"""

import json
import logging
import re

from pydantic import BaseModel

from app.ai_providers import AIProvider, AIProviderError
from app.schemas.resume import ResumeData
from app.services.cover_letter import embellishments
from app.services.jobs import is_written
from app.services.match import alternatives, match, normalise
from app.services.tailor import _line_context, _too_long, new_numbers, new_terms, skill_terms

log = logging.getLogger(__name__)

MAX_SKILLS = 15  # the job's missing skills sent to the model, most important first


class Bridge(BaseModel):
    skill: str  # one of the missing skills, as given
    line_id: str
    evidence: str  # the exact words of the line that show the skill
    reasoning: str  # why those words mean the person used the skill
    text: str  # the line, now naming the skill


class Bridges(BaseModel):
    bridges: list[Bridge]


INSTRUCTIONS = """\
A resume has been tailored to a job, but it never names some of the skills the job
asks for (MISSING). Some of them may already be shown by what a line describes: a
line about Django shows Python; "deployed on ECS" shows AWS; "set up GitHub Actions
pipelines" shows CI/CD; "wrote React components in TSX" shows TypeScript.

For each missing skill, look through LINES for one whose own words prove the person
used that skill. If you find one, return:
- `skill`: the missing skill, exactly as given
- `line_id`: that line's id
- `evidence`: the exact words copied from that line that prove it ("Django")
- `reasoning`: one sentence on why those words mean the skill was used
- `text`: the line rewritten to name the skill, changing as little as possible
  ("Built REST APIs in Python (Django) for the billing team.")

Rules:
- Only when the line's words make the skill certain, not when it is related, likely
  or common alongside it. Docker does not show Kubernetes. REST APIs do not show
  GraphQL. SQL does not show PostgreSQL. AWS does not show Terraform. Leading a
  team does not show Agile. If in doubt, leave the skill out.
- The new line adds the skill's name and nothing else: no new tools, numbers,
  outcomes, scale or qualities. Keep everything else the line says.
- One skill per line, and at most one line per skill.
- Most missing skills will have no line. Return only the ones you are sure of; an
  empty list is a fine answer.
"""


class BridgeVerdict(BaseModel):
    id: str
    reasoning: str  # first, so the answers follow from it
    evidence_proves_skill: bool
    adds_anything_else: bool


class BridgeVerification(BaseModel):
    verdicts: list[BridgeVerdict]


VERIFY_INSTRUCTIONS = """\
Each item says a resume line proves a skill, quoting the words that prove it, and
rewrites the line to name the skill. Check two things, strictly.

1. evidence_proves_skill: do the EVIDENCE words, in ORIGINAL, mean the person
   certainly used SKILL? True only when using the thing in EVIDENCE means using
   SKILL: a framework of that language (Django → Python, Spring Boot → Java), a
   service of that platform (ECS, S3, Lambda → AWS), a tool of that practice
   (GitHub Actions, Jenkins pipelines → CI/CD). False when they are only related,
   often used together, or one is a kind the other could be: Docker → Kubernetes,
   REST → GraphQL, SQL → PostgreSQL, "databases" → MongoDB, AWS → Terraform,
   "cloud" → AWS, Python → Django.
2. adds_anything_else: does REWRITTEN state anything ORIGINAL doesn't, apart from
   naming SKILL? Any new action, tool, number, scope, result or quality counts.

For each id, give one or two sentences of reasoning, then both answers. If unsure,
evidence_proves_skill is false.
"""


def missing_skills(resume: ResumeData, job: dict) -> list[str]:
    """The job's skills and keywords this resume never names, in the job's order:
    must-haves first."""
    result = match(
        resume, job.get("must_have", []), job.get("nice_to_have", []), job.get("keywords", [])
    )
    return [
        m.term
        for key in ("must_have", "nice_to_have", "keywords")
        for m in result[key]
        if not m.covered
    ][:MAX_SKILLS]


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _key(term: str) -> str:
    return normalise(alternatives(term)[0])


def check_bridge(
    skill: str, evidence: str, new: str, current: str, original: str, terms: list[str]
) -> str | None:
    """Why `new` can't replace `current` as a line that names `skill`, or None.
    `original` is the person's own wording of the line: the evidence must be there,
    and still in the line as tailored."""
    quote = evidence.strip().strip("\"'“”‘’ ")
    if len(quote) < 2 or not all(_squash(quote) in _squash(t) for t in (original, current)):
        return "quoted words that aren't in your line"
    if not is_written(skill, new):
        return f"didn't name {skill}"
    if extra := new_numbers(new, current):
        return f"added a number ({', '.join(sorted(extra))})"
    allowed = f"{current} {skill}"
    if extra := new_terms(new, allowed, terms):
        return f"also mentioned {', '.join(extra)}"
    if extra := embellishments(new, current):
        return f"added “{extra[0]}”"
    if _too_long(new, current) or len(new) > len(current) + len(skill) + 40:
        return "made the line much longer"
    return None


def bridge(
    resume: ResumeData, provenance: dict, profile: ResumeData, job: dict, provider: AIProvider
) -> None:
    """Rewrite, in place, lines whose own words show a skill the job wants and the
    resume doesn't name, so they name it. Each one is recorded as "bridged"."""
    missing = missing_skills(resume, job)
    lines = {b.id: b for e in [*resume.experience, *resume.projects] for b in e.bullets}
    if not missing or not lines:
        return
    context = _line_context(profile)
    try:
        proposed = provider.extract(
            task="bridge_skills",
            instructions=INSTRUCTIONS,
            text=json.dumps(
                {
                    "missing": missing,
                    "lines": [
                        {"id": i, "where": context.get(i, ""), "text": b.text}
                        for i, b in lines.items()
                    ],
                },
                ensure_ascii=False,
            ),
            schema=Bridges,
        )
    except AIProviderError as exc:
        log.warning("skill bridging skipped: %s", exc)
        return

    wanted = {_key(s): s for s in missing}
    terms = skill_terms(profile, job)
    candidates: dict[str, Bridge] = {}  # line id → bridge
    done: set[str] = set()  # skills already bridged
    for b in proposed.bridges:
        key = _key(b.skill)
        line = lines.get(b.line_id)
        if key not in wanted or key in done or line is None or b.line_id in candidates:
            continue
        skill = wanted[key]
        original = provenance.get(b.line_id, {}).get("original") or line.text
        text = b.text.strip()
        if reason := check_bridge(skill, b.evidence, text, line.text, original, terms):
            log.info("bridge refused %s → %s: %s", b.line_id, skill, reason)
            continue
        candidates[b.line_id] = b.model_copy(update={"skill": skill, "text": text})
        done.add(key)
    if not candidates:
        return

    try:
        checked = provider.extract(
            task="verify_bridge",
            instructions=VERIFY_INSTRUCTIONS,
            text=json.dumps(
                [
                    {
                        "id": i,
                        "skill": b.skill,
                        "evidence": b.evidence,
                        "original": lines[i].text,
                        "rewritten": b.text,
                    }
                    for i, b in candidates.items()
                ],
                ensure_ascii=False,
            ),
            schema=BridgeVerification,
        )
    except AIProviderError as exc:
        log.warning("skill bridging skipped: %s", exc)
        return

    # Unchecked isn't approved: only an item with a passing verdict is applied.
    passed = {
        v.id for v in checked.verdicts if v.evidence_proves_skill and not v.adds_anything_else
    }
    for line_id, b in candidates.items():
        if line_id not in passed:
            log.info("bridge rejected by verifier %s → %s", line_id, b.skill)
            continue
        line = lines[line_id]
        before = provenance.get(line_id, {})
        provenance[line_id] = {
            "original": before.get("original") or line.text,
            "status": "bridged",
            "skill": b.skill,
            "evidence": b.evidence.strip().strip("\"'“”‘’ "),
            "attempted": None,
            "reason": None,
        }
        line.text = b.text
