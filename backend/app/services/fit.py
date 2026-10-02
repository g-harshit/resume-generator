"""Making a resume fit the page count the person wants.

Three tools, all under the same rule as tailoring — nothing that isn't in the
person's own lines:

- `condense`: rewrite one role's (or project's) lines into fewer. Each new line names
  the lines it came from; it may not carry a number, skill or embellishment its
  sources don't, and the second check reads it against them. If any line fails, that
  role keeps its top original lines instead: shorter, never invented.
- `write_summary`: a summary from the resume's own facts, checked like tailoring's.
- `fit_to_pages`: narrow margins first (no content lost); then, round by round, fewer
  lines for older roles — the latest keeps the most — until the PDF fits.
"""

import json
import logging
from dataclasses import dataclass, field

from pydantic import BaseModel

from app.ai_providers import AIProvider
from app.rendering.render import render_html, render_pdf
from app.schemas.layout import Layout
from app.schemas.resume import Bullet, ResumeData, new_id
from app.services.cover_letter import embellishments, facts_text
from app.services.tailor import (
    check_pairs,
    check_summary,
    new_numbers,
    new_terms,
    skill_terms,
)

log = logging.getLogger(__name__)


class FitError(Exception):
    """Shown to the user."""


# --- condensing ---------------------------------------------------------------------------


class CondensedLine(BaseModel):
    text: str
    source_ids: list[str]


class CondensedEntry(BaseModel):
    id: str
    bullets: list[CondensedLine]


class Condensed(BaseModel):
    entries: list[CondensedEntry]


CONDENSE_INSTRUCTIONS = """\
You shorten the lines of a resume. For each entry, rewrite its bullets into at most
`target` bullets: merge related ones, keep the facts and numbers that matter most for
the JOB, drop the rest. Every bullet you return lists `source_ids`: the ids of that
entry's bullets it draws from.

Never add anything that isn't in its source bullets: no new numbers, tools,
responsibilities, outcomes, scale or qualities ("robust", "improved efficiency").
Shorter is good; more is never allowed. Keep each bullet to one line or two.
"""


def _entries(resume: ResumeData) -> dict[str, tuple[str, list[Bullet]]]:
    """id → (context, bullets) for every role and project."""
    out = {}
    for e in resume.experience:
        out[e.id] = (f"Role: {' at '.join(x for x in (e.title, e.company) if x)}", e.bullets)
    for p in resume.projects:
        out[p.id] = (f"Project: {p.name}", p.bullets)
    return out


def condense(
    resume: ResumeData,
    targets: dict[str, int],
    job: dict,
    provider: AIProvider,
) -> tuple[ResumeData, dict[str, dict], list[str]]:
    """Shorten the entries in `targets` (id → at most this many lines). Returns the new
    resume, provenance for the new lines, and notes on any entry that fell back to its
    own top lines."""
    resume = resume.model_copy(deep=True)
    entries = _entries(resume)
    todo = {i: n for i, n in targets.items() if i in entries and len(entries[i][1]) > n >= 1}
    if not todo:
        return resume, {}, []

    result = provider.extract(
        task="tailor",
        instructions=CONDENSE_INSTRUCTIONS,
        text=json.dumps(
            {
                "job": {
                    k: job.get(k, "") for k in ("title", "company", "must_have", "nice_to_have")
                },
                "entries": [
                    {
                        "id": i,
                        "context": entries[i][0],
                        "target": n,
                        "bullets": [{"id": b.id, "text": b.text} for b in entries[i][1]],
                    }
                    for i, n in todo.items()
                ],
            },
            ensure_ascii=False,
        ),
        schema=Condensed,
    )
    terms = skill_terms(resume, job)
    proposed: dict[str, list[tuple[str, list[str], str]]] = {}  # entry → [(new id, sources, text)]
    failed: dict[str, str] = {}
    for entry in result.entries:
        if entry.id not in todo or entry.id in proposed:
            continue
        own = {b.id: b.text for b in entries[entry.id][1]}
        lines = []
        for line in entry.bullets[: todo[entry.id]]:
            sources = [s for s in dict.fromkeys(line.source_ids) if s in own]
            text = line.text.strip()
            source_text = " ".join(own[s] for s in sources)
            if not text or not sources:
                failed[entry.id] = "a line didn't say which of your lines it came from"
            elif extra := new_numbers(text, source_text):
                failed[entry.id] = f"a line added a number ({', '.join(sorted(extra))})"
            elif extra := new_terms(text, source_text, terms):
                failed[entry.id] = f"a line added {', '.join(extra)}"
            elif extra := embellishments(text, source_text):
                failed[entry.id] = f"a line added “{extra[0]}”"
            lines.append((new_id("b"), sources, text))
        if lines and entry.id not in failed:
            proposed[entry.id] = lines

    # The second check, on every line that passed the rules.
    pairs = [
        {
            "id": line_id,
            "context": entries[eid][0],
            "original": " ".join(b.text for b in entries[eid][1] if b.id in sources),
            "rewritten": text,
        }
        for eid, lines in proposed.items()
        for line_id, sources, text in lines
    ]
    flagged = check_pairs(pairs, provider)
    for eid, lines in list(proposed.items()):
        bad = [flagged[line_id] for line_id, _, _ in lines if line_id in flagged]
        if bad:
            failed[eid] = f"a line added something your original doesn't say: {bad[0]}"
            del proposed[eid]

    provenance: dict[str, dict] = {}
    notes: list[str] = []
    for eid, n in todo.items():
        context, bullets = entries[eid]
        if eid in proposed:
            own = {b.id: b.text for b in bullets}
            new = []
            for line_id, sources, text in proposed[eid]:
                new.append(Bullet(id=line_id, text=text))
                provenance[line_id] = {
                    "original": " ".join(own[s] for s in sources),
                    "status": "condensed",
                    "sources": sources,
                    "attempted": None,
                    "reason": None,
                }
        else:
            # Fall back to the person's own most relevant lines (tailoring already put
            # them first): shorter, and nothing new.
            new = bullets[:n]
            reason = failed.get(eid, "it couldn't be shortened")
            notes.append(
                f"{context.split(': ', 1)[1]}: kept your top {n} lines as written ({reason})."
            )
            log.info("condense fell back for %s: %s", eid, reason)
        bullets[:] = new
    return resume, provenance, notes


# --- summary -------------------------------------------------------------------------------


class Summary(BaseModel):
    text: str


SUMMARY_INSTRUCTIONS = """\
Write a 2-3 sentence summary for the top of this person's resume, aimed at the JOB,
using only facts from their RESUME. Lead with who they are and what they've done that
the job cares about. No skill, number, title, scale or quality the resume doesn't
state — and don't mention a skill the job asks for unless the resume lists it. No
clichés ("results-driven", "passionate", "proven track record"). Don't tie a skill,
task or number to a role or a time ("previously", "at X") unless the resume puts it
there. If PREVIOUS is given, write something different from it.
"""


def write_summary(resume: ResumeData, job: dict, provider: AIProvider) -> str:
    """A summary only the resume's facts support. Two tries, then FitError."""
    terms = skill_terms(resume, job)
    # Everything about the person, employers and education included: a checker shown
    # only skills and lines rejected naming their own employers as "new information".
    # Not the old summary: it isn't a source of facts for its replacement.
    facts = facts_text(resume.model_copy(update={"summary": ""}))
    previous, why = resume.summary, ""
    for _ in range(2):
        draft = provider.extract(
            task="tailor",
            instructions=SUMMARY_INSTRUCTIONS,
            text=json.dumps(
                {
                    "job": {
                        k: job.get(k, "") for k in ("title", "company", "must_have", "nice_to_have")
                    },
                    "resume": resume.model_dump(
                        mode="json",
                        exclude={"basics": {"email", "phone", "links"}, "summary": True},
                    ),
                    "previous": previous,
                    **({"rejected_because": why} if why else {}),
                },
                ensure_ascii=False,
            ),
            schema=Summary,
        ).text.strip()
        why = check_summary(draft, resume, terms) or (
            f"used “{found[0]}”" if (found := embellishments(draft, facts)) else ""
        )
        if not why:
            flagged = check_pairs(
                [
                    {
                        "id": "summary",
                        "context": (
                            "A resume summary. ORIGINAL is everything in the resume. "
                            "Also flag a skill, task or number tied to a role or time "
                            "the resume doesn't put it in."
                        ),
                        "original": facts,
                        "rewritten": draft,
                    }
                ],
                provider,
            )
            why = flagged.get("summary", "")
            if not why:
                return draft
        previous = draft
        log.info("summary draft rejected: %s", why)
    raise FitError(
        "We couldn't write a summary using only what's in your resume this time. Try again, "
        "or write one yourself."
    )


# --- fitting to N pages -------------------------------------------------------------------

# Lines per role by recency (newest first; the last number repeats for older roles),
# for each round of shortening. The newest role keeps the most.
_ROUNDS = [[5, 3, 2], [4, 2, 1], [3, 2, 1]]
_PROJECT_LINES = [2, 1, 1]


@dataclass
class FitResult:
    resume: ResumeData
    layout: Layout
    provenance: dict[str, dict]
    pages_before: int
    pages_after: int
    steps: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def count_pages(resume: ResumeData, slug: str, layout: Layout) -> int:
    return render_pdf(render_html(resume, slug, layout)).pages


def _by_recency(resume: ResumeData) -> list[str]:
    def key(e):
        return (e.current, e.end or e.start or "", e.start or "")

    return [e.id for e in sorted(resume.experience, key=key, reverse=True)]


def fit_to_pages(
    resume: ResumeData,
    layout: Layout,
    slug: str,
    target: int,
    job: dict,
    provider: AIProvider,
) -> FitResult:
    before = count_pages(resume, slug, layout)
    layout = layout.model_copy(update={"pages": target})
    if before <= target:
        return FitResult(resume, layout, {}, before, before, ["It already fits."])

    steps: list[str] = []
    narrow = layout.model_copy(update={"margins": "narrow"})
    if layout.margins != "narrow":
        steps.append("Narrowed the margins on all four sides.")
        pages = count_pages(resume, slug, narrow)
        if pages <= target:
            return FitResult(resume, narrow, {}, before, pages, steps)

    order = _by_recency(resume)
    result = FitResult(resume, narrow, {}, before, before, steps)
    for round_no, caps in enumerate(_ROUNDS):
        targets = {eid: caps[min(rank, len(caps) - 1)] for rank, eid in enumerate(order)}
        targets |= {p.id: _PROJECT_LINES[round_no] for p in resume.projects}
        shorter, provenance, notes = condense(resume, targets, job, provider)
        pages = count_pages(shorter, slug, narrow)
        result = FitResult(
            shorter,
            narrow,
            provenance,
            before,
            pages,
            [
                *steps,
                "Kept the most lines for your latest role and fewer for older ones "
                f"(at most {', '.join(str(c) for c in caps)}…).",
            ],
            notes,
        )
        if pages <= target:
            return result
    result.steps.append(
        f"Still {result.pages_after} pages. Try hiding a section, or shortening a role further."
    )
    return result
