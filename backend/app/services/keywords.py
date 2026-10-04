"""Rewrite one line to include keywords the person chose for it.

Unlike a bridge (services/bridge.py), the evidence here is the person: they picked
"Kafka" and "microservices" for this line, saying that's what the work involved. So
the line may name them even though its words don't prove them. Everything else is
held as tightly as any rewording: the new line names every chosen keyword and adds
nothing else — no number, no other skill or job term, no padding, not much longer —
and a second call confirms it. A line that can't pass in two tries stays as it was.
"""

import json
import logging

from pydantic import BaseModel

from app.ai_providers import AIProvider
from app.services.bridge import _key, names
from app.services.cover_letter import embellishments
from app.services.tailor import new_numbers, new_terms

log = logging.getLogger(__name__)

TRIES = 2


class KeywordError(Exception):
    """The line couldn't take these keywords without adding something else."""


class KeywordLine(BaseModel):
    text: str


INSTRUCTIONS = """\
Rewrite one resume LINE so that it names every keyword in KEYWORDS. The person has
confirmed each keyword describes this work. Make it read like a strong resume line,
with the keywords worked into what the line already says, not listed at the end:
- "Built an event-driven service in Go" + Kafka, microservices → "Built an
  event-driven Go microservice on Kafka"
- "Designed and built a scalable end-to-end event-driven service in Go" + distributed
  systems, queues, high-throughput systems, low-latency systems → "Designed and built
  a scalable end-to-end event-driven Go service on distributed queues, built for high
  throughput and low latency"

Keep every fact and descriptive word the line has ("scalable", "end-to-end" stay).
Add only the keywords and the few plain words needed to place them ("with", "using",
"on", "for", "built for"). No new numbers, tools, outcomes, scale, team or qualities
("seamless", "ensuring", "high-impact", "leveraging"). If AVOID is given, those
wordings were rejected or disliked: write a clearly different one.
"""


class KeywordVerdict(BaseModel):
    reasoning: str
    adds_anything_else: bool
    added: str  # what else it adds, in a few words; "" if nothing


CHECK_INSTRUCTIONS = """\
A resume line (ORIGINAL) was rewritten (REWRITTEN) to include KEYWORDS. The person
has confirmed every keyword is true of this work, so each keyword, in any natural
form ("microservice" for "Microservices", "high-throughput, low-latency" for
"High-throughput systems, Low-latency systems", "queues" for "Message queues"), and
the plain words that place them ("with", "using", "on", "for", "across", "via"),
count as already known. Do not report them.

Is there anything ELSE in REWRITTEN that is in neither ORIGINAL nor KEYWORDS: a new
action, tool, number, scale, result, responsibility or quality ("millions of
events", "led", "improving reliability", "cloud-native")? Give one or two sentences
of reasoning, then the answer, and in `added` only those other things ("" if
nothing). If unsure whether something is a keyword's natural form, it is.
"""


def check(new: str, line: str, keywords: list[str], terms: list[str]) -> str | None:
    """Why `new` can't replace `line` as the line naming `keywords`, or None."""
    if left := [k for k in keywords if not names(k, new)]:
        return f"left out {', '.join(left)}"
    if extra := new_numbers(new, line):
        return f"added a number ({', '.join(sorted(extra))})"
    chosen = {_key(k) for k in keywords}
    allowed = " ".join([line, *keywords])
    if extra := [t for t in new_terms(new, allowed, terms) if _key(t) not in chosen]:
        return f"also mentioned {', '.join(extra)}"
    if extra := embellishments(new, line):
        return f"added “{extra[0]}”"
    if len(new) > len(line) + sum(len(k) + 10 for k in keywords) + 25:
        return "made the line much longer"
    return None


def add_keywords(
    line: str,
    keywords: list[str],
    context: str,
    terms: list[str],
    provider: AIProvider,
    avoid: list[str] | None = None,
) -> str:
    """`line`, rewritten to name every one of `keywords`. Raises KeywordError."""
    avoid = [a for a in avoid or [] if a.strip()]
    reason = ""
    for _ in range(TRIES):
        out = provider.extract(
            task="keyword_rewrite",
            instructions=INSTRUCTIONS,
            text=json.dumps(
                {"context": context, "line": line, "keywords": keywords, "avoid": avoid},
                ensure_ascii=False,
            ),
            schema=KeywordLine,
        )
        new = out.text.strip()
        reason = check(new, line, keywords, terms) or ""
        if not reason:
            verdict = provider.extract(
                task="verify_keyword_rewrite",
                instructions=CHECK_INSTRUCTIONS,
                text=json.dumps(
                    {"original": line, "rewritten": new, "keywords": keywords},
                    ensure_ascii=False,
                ),
                schema=KeywordVerdict,
            )
            if not verdict.adds_anything_else:
                return new
            reason = f"added something your line doesn't say: {verdict.added or 'a new claim'}"
        log.info("keyword rewrite refused: %s", reason)
        avoid.append(new)
    raise KeywordError(reason)
