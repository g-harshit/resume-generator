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
from typing import Literal

from pydantic import BaseModel

from app.ai_providers import AIProvider, AIProviderError
from app.rendering.render import measure, render_html, render_pdf
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
Write a summary for the top of this person's resume, as long as LENGTH says, aimed
at the JOB, using only facts from their RESUME. Lead with who they are and what they've done that
the job cares about. Write it the way resumes are written: no name and no pronouns
("he", "she", "I") — start with the role or degree ("Computer Science student at…",
"Backend engineer who…"). No skill, number, title, scale or quality the resume doesn't
state — and don't mention a skill the job asks for unless the resume lists it. No
clichés ("results-driven", "passionate", "proven track record"). Don't tie a skill,
task or number to a role or a time ("previously", "at X") unless the resume puts it
there. If PREVIOUS is given, write something different from it.
"""


SummaryLength = Literal["shorter", "same", "longer"]

# How long to make it, relative to PREVIOUS when there is one.
_LENGTH_ASK: dict[str, tuple[str, str]] = {
    # length: (with a previous summary, without one)
    "shorter": ("Make it clearly shorter than PREVIOUS: one or two sentences.", "One sentence."),
    "same": ("Keep it about as long as PREVIOUS.", "Two or three sentences."),
    "longer": (
        "Make it longer than PREVIOUS: three or four sentences, under 120 words, using more "
        "of the resume's facts (still only its facts).",
        "Three or four sentences, under 120 words.",
    ),
}


def write_summary(
    resume: ResumeData, job: dict, provider: AIProvider, length: SummaryLength = "same"
) -> str:
    """A summary only the resume's facts support. Two tries, then FitError. A draft that's
    honest but misses the length asked for gets the second try, and is used if that one
    does no better."""
    terms = skill_terms(resume, job)
    # Everything about the person, employers and education included: a checker shown
    # only skills and lines rejected naming their own employers as "new information".
    # Not the old summary: it isn't a source of facts for its replacement.
    facts = facts_text(resume.model_copy(update={"summary": ""}))
    previous = resume.summary.strip()
    why, rejected, honest = "", "", ""
    for _ in range(2):
        draft = provider.extract(
            task="write_summary",
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
                    "length": _LENGTH_ASK[length][0 if resume.summary.strip() else 1],
                    **({"rejected_draft": rejected, "rejected_because": why} if why else {}),
                },
                ensure_ascii=False,
            ),
            schema=Summary,
        ).text.strip()
        why = check_summary(draft, resume, terms, 900 if length == "longer" else 600) or (
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
                why = _wrong_length(draft, previous, length)
                if not why:
                    return draft
                honest = draft
        rejected = draft
        log.info("summary draft rejected: %s", why)
    if honest:
        return honest
    raise FitError(
        "We couldn't write a summary using only what's in your resume this time. Try again, "
        "or write one yourself."
    )


def _wrong_length(draft: str, previous: str, length: SummaryLength) -> str:
    """Why the draft isn't the length asked for, or ''. Measured against the summary it
    replaces; with none there, any length passes."""
    if not previous or length == "same":
        return ""
    words, before = len(draft.split()), len(previous.split())
    if length == "shorter" and words > 0.8 * before:
        return f"it has {words} words; it should be clearly shorter than {before}"
    if length == "longer" and words < 1.2 * before:
        return f"it has {words} words; it should be clearly longer than {before}"
    return ""


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
    profile: ResumeData | None = None,
    provenance: dict | None = None,
) -> FitResult:
    """Make the resume `target` pages: shorter if it runs over, and using the whole
    last page if it has room (adding back the person's own lines from `profile`)."""
    before = count_pages(resume, slug, layout)
    layout = layout.model_copy(update={"pages": target})
    if before <= target:
        return fill_page(resume, layout, slug, profile or resume, job, provider, provenance, target)

    def respaced(result: FitResult) -> FitResult:
        """`result`, spread again over its last page (layout only, nothing added)."""
        spaced = fill_page(
            result.resume,
            result.layout,
            slug,
            result.resume,
            job,
            provider,
            target=target,
            add_content=False,
        )
        if spaced.layout != result.layout:
            result.layout = spaced.layout
            result.pages_after = spaced.pages_after
            result.steps += [s for s in spaced.steps if "as far as" not in s]
        return result

    steps: list[str] = []
    # A page stretched to fill it (larger text, more spacing) is the first thing to
    # give back: it was only ever filling room, which this content no longer leaves.
    if layout.spacing or layout.font_scale:
        layout = layout.model_copy(update={"spacing": None, "font_scale": None})
        steps.append("Took out the extra spacing and text size used to fill the page.")
        pages = count_pages(resume, slug, layout)
        if pages <= target:
            return respaced(FitResult(resume, layout, {}, before, pages, steps))

    narrow = layout.model_copy(update={"margins": "narrow"})
    if layout.margins != "narrow":
        steps.append("Narrowed the margins on all four sides.")
        pages = count_pages(resume, slug, narrow)
        if pages <= target:
            return respaced(FitResult(resume, narrow, {}, before, pages, steps))

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
            # Shortening overshoots a little: spread what's left over the last page.
            return respaced(result)
    result.steps.append(
        f"Still {result.pages_after} pages. Try hiding a section, or shortening a role further."
    )
    return result


# --- filling the page ---------------------------------------------------------------------
#
# The other way round: a resume with room to spare on its last page uses it. Every step
# is kept only if the resume still has its pages, and none adds anything that isn't the
# person's: their own lines and projects left out of this resume come back, the summary
# is written longer from the resume's facts, and the gaps between sections, entries and
# lines grow until the last page is full. Margins are the person's choice: left alone.

FULL = 0.93  # a last page this full is done
MAX_FONT_SCALE = 1.2
MAX_SPACING = 5.0


def _largest(resume, layout: Layout, field: str, low: float, high: float, fits, rounds: int = 6):
    """The largest `field` in (low, high] that keeps the pages, by halving: (layout,
    pages, fill), or None if even a little more doesn't fit."""
    best = None
    ok, p, f = fits(resume, layout.model_copy(update={field: high}))
    if ok:
        return layout.model_copy(update={field: high}), p, f
    for _ in range(rounds):
        mid = round((low + high) / 2, 3)
        trial = layout.model_copy(update={field: mid})
        ok, p, f = fits(resume, trial)
        if ok:
            best, low = (trial, p, f), mid
        else:
            high = mid
    return best


def _fill(resume: ResumeData, slug: str, layout: Layout) -> tuple[int, float]:
    return measure(render_html(resume, slug, layout))


def _left_out(resume: ResumeData, profile: ResumeData, provenance: dict) -> dict[str, list[Bullet]]:
    """Per role and project in the resume: the profile's lines it doesn't have (nor
    merged into one of its lines), in the profile's order."""
    out: dict[str, list[Bullet]] = {}
    # Merged into a line that's still here; a merge since undone doesn't count.
    current = {b.id for e in [*resume.experience, *resume.projects] for b in e.bullets}
    sources = {s for k, p in provenance.items() if k in current for s in p.get("sources", [])}
    for mine, theirs in (
        (resume.experience, profile.experience),
        (resume.projects, profile.projects),
    ):
        own = {e.id: e for e in theirs}
        for entry in mine:
            if entry.id not in own:
                continue
            have = {b.id for b in entry.bullets} | sources
            if missing := [b for b in own[entry.id].bullets if b.id not in have]:
                out[entry.id] = missing
    return out


def fill_page(
    resume: ResumeData,
    layout: Layout,
    slug: str,
    profile: ResumeData,
    job: dict,
    provider: AIProvider,
    provenance: dict | None = None,
    target: int | None = None,
    add_content: bool = True,
    longer_summary: bool = True,
) -> FitResult:
    """Use the room left on the last page, without going past `target` pages (default:
    as many as it has now). `add_content=False` only adjusts the layout;
    `longer_summary=False` skips the one step that needs the model."""
    provenance = dict(provenance or {})
    pages, fill = _fill(resume, slug, layout)
    target = target or pages
    before = pages
    steps: list[str] = []

    def fits(r: ResumeData, lay: Layout) -> tuple[bool, int, float]:
        p, f = _fill(r, slug, lay)
        return p <= target, p, f

    if pages > target:
        return FitResult(resume, layout, provenance, before, pages, steps)

    # 1. The person's own lines and projects left out of this resume, newest role first.
    if add_content and fill < FULL:
        resume = resume.model_copy(deep=True)
        order = {eid: i for i, eid in enumerate(_by_recency(resume))}
        waiting = _left_out(resume, profile, provenance)
        entries = {e.id: e for e in [*resume.experience, *resume.projects]}
        queue = sorted(waiting, key=lambda eid: order.get(eid, len(order)))
        added = 0
        while queue and fill < FULL:
            for eid in list(queue):
                line = waiting[eid].pop(0)
                entries[eid].bullets.append(Bullet(id=line.id, text=line.text))
                ok, p, f = fits(resume, layout)
                if ok:
                    pages, fill, added = p, f, added + 1
                else:
                    entries[eid].bullets.pop()
                    waiting[eid] = []
                if not waiting[eid]:
                    queue.remove(eid)
                if fill >= FULL:
                    break
        if added:
            steps.append(
                f"Added back {added} of your own line{'s' if added > 1 else ''} "
                "left out of this resume."
            )
        have = {p.id for p in resume.projects}
        for project in profile.projects:
            if fill >= FULL or project.id in have:
                continue
            trial = resume.model_copy(update={"projects": [*resume.projects, project]})
            ok, p, f = fits(trial, layout)
            if ok:
                resume, pages, fill = trial, p, f
                steps.append(f"Added back your project {project.name}.")

    # 2. A longer summary, from the resume's own facts.
    if add_content and longer_summary and fill < FULL - 0.04 and resume.summary.strip():
        try:
            longer = write_summary(resume, job, provider, "longer")
        except (FitError, AIProviderError) as exc:
            log.info("fill: no longer summary: %s", exc)
        else:
            trial = resume.model_copy(update={"summary": longer})
            ok, p, f = fits(trial, layout)
            if ok:
                provenance["summary"] = {
                    "original": provenance.get("summary", {}).get("original") or resume.summary,
                    "status": "written",
                    "attempted": None,
                    "reason": None,
                }
                resume, pages, fill = trial, p, f
                steps.append("Wrote a longer summary from what's in your resume.")

    # 3. Slightly larger text, then more room between sections, entries and lines: each
    # the most that keeps the pages, so the last line sits on the bottom margin.
    if fill < FULL:
        for field, top, step in (
            ("font_scale", MAX_FONT_SCALE, "Made the text a little larger."),
            ("spacing", MAX_SPACING, "Spaced sections and lines out to use the whole page."),
        ):
            if fill >= FULL:
                break
            low = getattr(layout, field) or 1.0
            if low >= top:
                continue
            found = _largest(resume, layout, field, low, top, fits)
            if found:
                layout, pages, fill = found
                steps.append(step)

    if fill < FULL:
        steps.append(
            f"The last page is {fill:.0%} full: that's as far as the layout can stretch. "
            "Add lines (yours left out, or new ones in your profile) to fill the rest."
        )
    elif not steps:
        steps.append("The page is already full.")
    return FitResult(resume, layout, provenance, before, pages, steps)
