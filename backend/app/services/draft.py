"""Resume lines from the person's own notes, for building a profile from scratch.

Someone without a resume (a student, say) knows what they did but not how resumes
say it. They describe a project or job in plain words; the model turns that into
resume lines. Same rule as tailoring: a line may say nothing the notes don't —
no number, tool, outcome or quality the person didn't write. Each line is checked
in code (numbers, known skills, embellishing words), then read against the notes by
the second check. Lines that fail are left out, and the person is told why.
"""

import json
import logging
from typing import Literal

from pydantic import BaseModel

from app.ai_providers import AIProvider
from app.schemas.resume import ResumeData
from app.services.cover_letter import embellishments
from app.services.match import KNOWN_SKILLS, mentioned_casually
from app.services.tailor import check_pairs, new_numbers, new_terms

log = logging.getLogger(__name__)


class DraftError(Exception):
    """Shown to the user."""


class DraftedLines(BaseModel):
    lines: list[str]


INSTRUCTIONS = """\
You help someone write their resume. They describe a {kind} in their own words
(NOTES); you turn that into {count} resume bullet lines for it.

- Start each line with a strong past-tense verb ("Built", "Designed", "Led"); present
  tense for something ongoing. No "I", no full stop needed.
- One idea per line, one or two lines of text each. Put what they built or did first,
  then how (tools), then what came of it — only the parts the NOTES say.
- Use ONLY what the NOTES say. No number, tool, technology, team size, user count,
  result or quality they didn't write ("scalable", "robust", "efficient", "improved
  performance" are claims). If the notes are thin, write fewer, shorter lines —
  never pad. If the notes give one fact, one line is right.
- Keep their numbers and names exactly as written.
"""


def draft_lines(
    kind: Literal["project", "experience"],
    context: str,
    notes: str,
    profile: ResumeData,
    provider: AIProvider,
    count: int = 3,
) -> tuple[list[str], list[dict]]:
    """Resume lines from `notes`. Returns (lines, left_out) where each left-out line
    says why: {"text", "reason"}. Raises DraftError when nothing usable came back."""
    notes = notes.strip()
    if len(notes) < 15:
        raise DraftError("Write a little more about it first — what you did, and how.")
    result = provider.extract(
        task="tailor",
        instructions=INSTRUCTIONS.format(
            kind="job or internship" if kind == "experience" else "project",
            count=f"up to {count}",
        ),
        text=json.dumps({"about": context, "notes": notes}, ensure_ascii=False),
        schema=DraftedLines,
    )
    # The notes plus the entry's own heading (a project's name, a role's title).
    source = f"{context}\n{notes}"
    terms = [*KNOWN_SKILLS, *profile.all_skills()]

    kept: dict[str, str] = {}
    left_out: list[dict] = []
    for i, text in enumerate(dict.fromkeys(t.strip() for t in result.lines[:count])):
        if not text:
            continue
        reason = None
        if extra := new_numbers(text, source):
            reason = f"it added a number you didn't write ({', '.join(sorted(extra))})"
        elif extra := [
            t for t in new_terms(text, source, terms) if not mentioned_casually(t, source)
        ]:
            reason = f"it mentioned {', '.join(extra)}, which your notes don't"
        elif extra := embellishments(text, source):
            reason = f"it added “{extra[0]}”"
        if reason:
            left_out.append({"text": text, "reason": reason})
        else:
            kept[f"l{i}"] = text

    flagged = check_pairs(
        [
            {
                "id": key,
                "context": f"A resume line written from the person's notes about: {context}",
                "original": notes,
                "rewritten": text,
            }
            for key, text in kept.items()
        ],
        provider,
    )
    for key, why in flagged.items():
        left_out.append(
            {"text": kept.pop(key), "reason": f"it says something your notes don't: {why}"}
        )

    if left_out:
        log.info("draft lines left out: %s", [x["reason"] for x in left_out])
    if not kept:
        raise DraftError(
            "We couldn't write lines that stick to what you wrote this time. Try again, or "
            "add a little more detail to your notes."
        )
    return list(kept.values()), left_out
