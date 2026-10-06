"""Reword the lines a person picks, for the job their resume is for.

Making a resume copies the profile as it is; nothing is reworded until the person asks,
line by line (or a whole role at once: one call). The rewording is held to tailoring's
invention guard: no number, skill or job term the line doesn't have, not much longer
(`check_rewording`), and a second call that compares each new line with the old one
(`check_pairs`). A line that fails keeps its words, and the person is told why.
"""

import json

from pydantic import BaseModel

from app.ai_providers import AIProvider
from app.schemas.resume import ResumeData
from app.services.tailor import (
    _line_context,
    check_pairs,
    check_rewording,
    new_numbers,
    skill_terms,
)


class Reworded(BaseModel):
    id: str
    text: str


class RewordPlan(BaseModel):
    lines: list[Reworded]


INSTRUCTIONS = """\
Reword each resume line in LINES for the job in JOB. Use the job's name for something
the line already describes (it says "Postgres", the job says "PostgreSQL"), lead with
the part the job cares about, and tighten it. Stay close to the original: the facts
must not change, and none may be dropped — keep every number, metric ("from 800ms to
120ms"), tool and result the line has, and its verb's meaning ("designed" stays
designed, not "implemented").

Never add anything the line doesn't say: no new numbers, tools, technologies,
responsibilities, team sizes, outcomes, scope ("backend", "production") or qualities
("optimizing", "significantly", "robust", "ensuring reliability"). If a line can't be
improved for this job without adding something, return it unchanged. If AVOID gives
a line's previous wording, write a clearly different one. Return every id.
"""


def reword_lines(
    resume: ResumeData,
    line_ids: list[str],
    job: dict,
    job_text: str,
    provider: AIProvider,
    avoid: dict[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    """New wording for each of `line_ids` that passed the guard, and, for the ones that
    didn't, why: ({id: new text}, {id: reason})."""
    lines = {b.id: b.text for e in [*resume.experience, *resume.projects] for b in e.bullets}
    wanted = [i for i in dict.fromkeys(line_ids) if i in lines]
    if not wanted:
        return {}, {}
    context = _line_context(resume)
    plan = provider.extract(
        task="reword_lines",
        instructions=INSTRUCTIONS,
        text=json.dumps(
            {
                "job": {
                    "title": job.get("title", ""),
                    "must_have": job.get("must_have", []),
                    "nice_to_have": job.get("nice_to_have", []),
                    "keywords": job.get("keywords", []),
                    "posting": job_text[:6000],
                },
                "lines": [
                    {
                        "id": i,
                        "where": context.get(i, ""),
                        "text": lines[i],
                        **({"avoid": avoid[i]} if avoid and avoid.get(i) else {}),
                    }
                    for i in wanted
                ],
            },
            ensure_ascii=False,
        ),
        schema=RewordPlan,
    )
    terms = skill_terms(resume, job)
    proposed: dict[str, str] = {}
    refused: dict[str, str] = {}
    for line in plan.lines:
        if line.id not in wanted or line.id in proposed:
            continue
        text = line.text.strip()
        if text == lines[line.id]:
            refused[line.id] = (
                "it's already as good for this job as it can be without adding anything"
            )
        elif reason := check_rewording(text, lines[line.id], terms):
            refused[line.id] = reason
        elif dropped := new_numbers(lines[line.id], text):
            # A rewording that loses a metric makes the line weaker, not more relevant.
            refused[line.id] = f"it dropped {', '.join(sorted(dropped))} from your line"
        else:
            proposed[line.id] = text
    for i in wanted:
        if i not in proposed and i not in refused:
            refused[i] = "the AI didn't return it"
    flagged = check_pairs(
        [
            {"id": i, "context": context.get(i, ""), "original": lines[i], "rewritten": t}
            for i, t in proposed.items()
        ],
        provider,
    )
    for i, added in flagged.items():
        refused[i] = f"it added something your line doesn't say: {added}"
        del proposed[i]
    return proposed, refused
