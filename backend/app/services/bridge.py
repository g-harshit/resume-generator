"""Name the job's skills in the lines that already show them.

A job asks for Python; no line says "Python", but one says "Built REST APIs in
Django". The person did use Python: Django is Python. So the line may say so: "Built
REST APIs in Python (Django)". That's a bridge. One line can carry several: "Designed
and built an end-to-end event-driven service in Go" shows backend work and system
design as well as event-driven systems.

A bridge is the one place tailoring adds words the line doesn't have, so it is held to
more than a rewording is. In four steps:

1. Claims. The model names, per missing skill, a line that proves it and quotes the
   exact words that do. Code checks the quote really is in the person's line.
2. Judging the claims. A separate, strict call decides, claim by claim, whether those
   words *mean* the person used the skill. "Django" → Python, "ECS" → AWS, "GitHub
   Actions" → CI/CD: yes. "Docker" → Kubernetes, "REST APIs" → GraphQL, "scalable" →
   high-throughput: no. Related, likely or usual isn't the same as stated.
3. Rewriting. Each line is rewritten to name only its approved skills. Code checks it
   names at least one and adds nothing else: no number, no other skill or job term,
   no padding ("robust", "seamless"), not much longer.
4. Checking the rewrite. Another call confirms the line says nothing new apart from
   naming those skills.

Whatever fails a step leaves the line as it was. Bridging is optional polish: if the
model is unavailable, the resume is returned unchanged.
"""

import json
import logging
import re

from pydantic import BaseModel

from app.ai_providers import AIProvider, AIProviderError
from app.schemas.resume import ResumeData
from app.services.cover_letter import embellishments
from app.services.match import alternatives, names, normalise
from app.services.tailor import _line_context, new_numbers, new_terms, skill_terms

log = logging.getLogger(__name__)

MAX_SKILLS = 25  # the job's missing skills sent to the model, most important first


# --- 1. claims ---------------------------------------------------------------------------


class Claim(BaseModel):
    skill: str  # one of the missing skills, exactly as given
    line_id: str
    evidence: str  # the exact words of the line that show the skill
    reasoning: str  # why those words mean the skill was used


class Claims(BaseModel):
    claims: list[Claim]


CLAIM_INSTRUCTIONS = """\
A resume has been tailored to a job, but its lines never name some of the skills the
job asks for (MISSING). Some may already be shown by what a line describes:
- "Built REST APIs in Django" shows Python (Django is Python) and backend development
- "Deployed services to ECS" shows AWS
- "Set up GitHub Actions pipelines" shows CI/CD
- "Designed and built an end-to-end service" shows system design and backend work
- "Kafka consumers" shows message queues and event-driven systems

For each missing skill, find the line whose own words prove the person used it, and
return a claim: `skill` (exactly as given), `line_id`, `evidence` (the fewest exact words
copied from that line that prove it: "Django", "on ECS", "Designed and built"),
`reasoning` (one sentence). A line may prove
several skills; each skill needs only its best line.

Only when the words make the skill certain, not when it is related, likely or usual:
- Docker does not show Kubernetes; REST does not show GraphQL; SQL does not show
  PostgreSQL; AWS does not show Terraform; leading a team does not show Agile.
- "scalable" or "robust" do not show high-throughput, low-latency or distributed
  systems; "a service" does not show microservices; "event-driven" does not show
  queues or Kafka. Those need the line to say so.
Most missing skills will have no line. An empty list is a fine answer.
"""


# --- 2. judging the claims -----------------------------------------------------------------


class ClaimVerdict(BaseModel):
    id: str
    reasoning: str  # first, so the answer follows from it
    proves_skill: bool


class ClaimVerification(BaseModel):
    verdicts: list[ClaimVerdict]


JUDGE_INSTRUCTIONS = """\
Each item claims that the words EVIDENCE, in a resume LINE, prove the person used
SKILL. Decide each claim strictly.

proves_skill is true only when doing what EVIDENCE says necessarily means using
SKILL: a framework of that language (Django → Python, Spring Boot → Java), a service
of that platform (ECS, S3, Lambda → AWS), a tool of that practice (GitHub Actions,
Jenkins pipelines → CI/CD), the work itself (building an API or a service in Go →
backend development; designing and building a service end to end → system design;
an event-driven service → event-driven systems; Kafka or RabbitMQ consumers →
message queues).

It is false when they are only related, often found together, or one could be the
other: Docker → Kubernetes, REST → GraphQL, SQL → PostgreSQL, AWS → Terraform,
"cloud" → AWS, Python → Django, "scalable" → high-throughput, "fast" → low-latency,
"a service" → microservices, "event-driven" → message queues, "scalable" →
distributed systems.

For each id, give one or two sentences of reasoning, then the answer. If unsure,
false.
"""


# --- 3. rewriting ----------------------------------------------------------------------------


class Rewrite(BaseModel):
    id: str
    text: str


class Rewrites(BaseModel):
    lines: list[Rewrite]


REWRITE_INSTRUCTIONS = """\
Rewrite each resume LINE so that it names every skill in SKILLS. The line already
proves each one: EVIDENCE gives the words that do. Put each skill's name right where
its evidence is, as the line's own words, changing as little as possible:
- "Built REST APIs in Django" + Python, backend development → "Built backend REST
  APIs in Python (Django)"
- "Kafka consumers on ECS" + AWS, message queues → "Kafka (message queue) consumers
  on AWS ECS"
- "Designed and built an event-driven service in Go" + system design → "Owned the
  system design and build of an event-driven service in Go" is WRONG ("owned" is new);
  "System design and build of an event-driven service in Go" is right
A skill describes the work, so attach it to the work, not to a team or a person.
Never tack a clause on the end ("…, utilizing AWS", "…, applying Python",
"demonstrating…", "leveraging…"). Keep everything else the line says, in its order.
No new tools, numbers, outcomes, scale or qualities. A natural form of a skill's name
is fine ("backend" for "Backend development", "queues" for "Message queues").
"""


# --- 4. checking the rewrite -----------------------------------------------------------------


class RewriteVerdict(BaseModel):
    id: str
    reasoning: str
    adds_anything_else: bool


class RewriteVerification(BaseModel):
    verdicts: list[RewriteVerdict]


CHECK_INSTRUCTIONS = """\
Each item is a resume line (ORIGINAL) rewritten (REWRITTEN) to name some skills
(SKILLS) that ORIGINAL already proves. Naming those skills is allowed. Does REWRITTEN
state anything else that ORIGINAL doesn't: a new action, tool, number, scope, result
or quality? For each id, one or two sentences of reasoning, then the answer. If
unsure, true.
"""


# --- the steps -------------------------------------------------------------------------------


def _key(term: str) -> str:
    return normalise(alternatives(term)[0])


def job_terms(job: dict) -> list[str]:
    """The job's skills and keywords, once each, in the job's order: must-haves first."""
    seen: set[str] = set()
    out = []
    for term in [
        *job.get("must_have", []),
        *job.get("nice_to_have", []),
        *job.get("keywords", []),
    ]:
        key = _key(term)
        if key and key not in seen:
            seen.add(key)
            out.append(term.strip())
    return out


def missing_skills(resume: ResumeData, job: dict) -> list[str]:
    """The job's skills and keywords that none of the resume's lines name. The Skills
    list and the summary don't count: the point is to show the skill in the work."""
    lines = " \n ".join(b.text for e in [*resume.experience, *resume.projects] for b in e.bullets)
    return [t for t in job_terms(job) if not names(t, lines)][:MAX_SKILLS]


def missing_by_line(resume: ResumeData, job: dict) -> dict[str, list[str]]:
    """Per line: the job's terms that line doesn't name (it may still be elsewhere), so
    a keyword used on one line can be added to others too."""
    terms = job_terms(job)
    return {
        b.id: [t for t in terms if not names(t, b.text)]
        for e in [*resume.experience, *resume.projects]
        for b in e.bullets
    }


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _quote(evidence: str) -> str:
    return evidence.strip().strip("\"'“”‘’ ")


def quoted_from(evidence: str, *texts: str) -> bool:
    quote = _quote(evidence)
    return len(quote) >= 2 and all(_squash(quote) in _squash(t) for t in texts)


def check_rewrite(new: str, current: str, skills: list[str], terms: list[str]) -> str | None:
    """Why `new` can't replace `current` as a line naming `skills`, or None."""
    if not any(names(s, new) for s in skills):
        return f"didn't name {', '.join(skills)}"
    if extra := new_numbers(new, current):
        return f"added a number ({', '.join(sorted(extra))})"
    allowed = " ".join([current, *skills])
    if extra := [t for t in new_terms(new, allowed, terms) if _key(t) not in map(_key, skills)]:
        return f"also mentioned {', '.join(extra)}"
    if extra := embellishments(new, current):
        return f"added “{extra[0]}”"
    room = sum(len(s) + 12 for s in skills) + 20
    if len(new) > len(current) + room:
        return "made the line much longer"
    return None


def _ask(provider: AIProvider, task: str, instructions: str, items, schema):
    try:
        return provider.extract(
            task=task,
            instructions=instructions,
            text=json.dumps(items, ensure_ascii=False),
            schema=schema,
        )
    except AIProviderError as exc:
        log.warning("skill bridging stopped at %s: %s", task, exc)
        return None


def bridge(
    resume: ResumeData, provenance: dict, profile: ResumeData, job: dict, provider: AIProvider
) -> list[str]:
    """Rewrite, in place, lines whose own words show skills the job wants and no line
    names, so they name them. Each is recorded as "bridged", with the skills and the
    words that prove each. Returns the skills added."""
    missing = missing_skills(resume, job)
    lines = {b.id: b for e in [*resume.experience, *resume.projects] for b in e.bullets}
    if not missing or not lines:
        return []
    context = _line_context(profile)

    def original(line_id: str) -> str:
        return provenance.get(line_id, {}).get("original") or lines[line_id].text

    # 1. claims
    proposed = _ask(
        provider,
        "bridge_claims",
        CLAIM_INSTRUCTIONS,
        {
            "missing": missing,
            "lines": [
                {"id": i, "where": context.get(i, ""), "text": b.text} for i, b in lines.items()
            ],
        },
        Claims,
    )
    if proposed is None:
        return []
    wanted = {_key(s): s for s in missing}
    claims: dict[str, Claim] = {}  # claim id → claim, with the skill as the job spells it
    taken: set[str] = set()
    for c in proposed.claims:
        key = _key(c.skill)
        if key not in wanted or key in taken or c.line_id not in lines:
            continue
        if not quoted_from(c.evidence, original(c.line_id), lines[c.line_id].text):
            log.info("bridge claim refused, quote not in line: %s → %s", c.line_id, c.skill)
            continue
        taken.add(key)
        claims[f"c{len(claims) + 1}"] = c.model_copy(
            update={"skill": wanted[key], "evidence": _quote(c.evidence)}
        )
    if not claims:
        return []

    # 2. judging the claims
    judged = _ask(
        provider,
        "judge_bridge_claims",
        JUDGE_INSTRUCTIONS,
        [
            {"id": i, "skill": c.skill, "evidence": c.evidence, "line": lines[c.line_id].text}
            for i, c in claims.items()
        ],
        ClaimVerification,
    )
    if judged is None:
        return []
    proven = {v.id for v in judged.verdicts if v.proves_skill}  # unanswered isn't proven
    by_line: dict[str, list[Claim]] = {}
    for i, c in claims.items():
        ok = i in proven
        log.info(
            "bridge claim %s: %s → %s (%s)",
            "proven" if ok else "rejected",
            c.line_id,
            c.skill,
            c.evidence,
        )
        if ok:
            by_line.setdefault(c.line_id, []).append(c)
    if not by_line:
        return []

    # 3. rewriting
    rewritten = _ask(
        provider,
        "bridge_rewrite",
        REWRITE_INSTRUCTIONS,
        [
            {
                "id": line_id,
                "line": lines[line_id].text,
                "skills": [c.skill for c in cs],
                "evidence": {c.skill: c.evidence for c in cs},
            }
            for line_id, cs in by_line.items()
        ],
        Rewrites,
    )
    if rewritten is None:
        return []
    terms = skill_terms(profile, job)
    candidates: dict[str, tuple[str, list[Claim]]] = {}
    for r in rewritten.lines:
        cs = by_line.get(r.id)
        if cs is None or r.id in candidates:
            continue
        text = r.text.strip()
        if reason := check_rewrite(text, lines[r.id].text, [c.skill for c in cs], terms):
            log.info("bridge rewrite refused %s: %s", r.id, reason)
            continue
        named = [c for c in cs if names(c.skill, text)]
        candidates[r.id] = (text, named)
    if not candidates:
        return []

    # 4. checking the rewrite
    checked = _ask(
        provider,
        "verify_bridge_rewrite",
        CHECK_INSTRUCTIONS,
        [
            {
                "id": line_id,
                "original": lines[line_id].text,
                "rewritten": text,
                "skills": [c.skill for c in cs],
            }
            for line_id, (text, cs) in candidates.items()
        ],
        RewriteVerification,
    )
    if checked is None:
        return []
    clean = {v.id for v in checked.verdicts if not v.adds_anything_else}

    added: list[str] = []
    for line_id, (text, cs) in candidates.items():
        if line_id not in clean:
            log.info("bridge rewrite rejected by verifier: %s", line_id)
            continue
        before = provenance.get(line_id, {})
        earlier = before.get("skills", []) if before.get("status") == "bridged" else []
        provenance[line_id] = {
            "original": original(line_id),
            "status": "bridged",
            "skills": [*earlier, *({"skill": c.skill, "evidence": c.evidence} for c in cs)],
            # The line before any skills were named: where removing them goes back to.
            "base": before.get("base") if earlier else lines[line_id].text,
            "attempted": None,
            "reason": None,
        }
        lines[line_id].text = text
        added += [c.skill for c in cs]
    return added
