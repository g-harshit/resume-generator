"""Rewrite one line to include keywords the person chose for it.

The person is the authority on their own work: they picked these keywords for this
line, so the line names every one of them. Nothing second-guesses that choice. The
only check is that the model actually did it: a line that leaves a keyword out gets
one more try with the omission pointed out.
"""

import json
import logging

from pydantic import BaseModel

from app.ai_providers import AIProvider
from app.services.bridge import names

log = logging.getLogger(__name__)

TRIES = 2


class KeywordError(Exception):
    """The model didn't return a line."""


class KeywordLine(BaseModel):
    text: str


INSTRUCTIONS = """\
Rewrite one resume LINE so that it includes every keyword in KEYWORDS. The person has
chosen these keywords for this line: include all of them, spelled as given (a natural
form is fine: "microservice" for "microservices").

Make it read like a strong, specific resume line, with the keywords worked into what
the line says rather than listed at the end. Keep every fact the line has: tools,
numbers, scope, results. Don't invent numbers. Keep it to one sentence, about the
same length or a little longer.

If AVOID is given, the person didn't like those wordings: write a clearly different
one. If MISSING is given, your last attempt left those keywords out: include them.
"""


def add_keywords(
    line: str,
    keywords: list[str],
    context: str,
    provider: AIProvider,
    avoid: list[str] | None = None,
) -> str:
    """`line`, rewritten to include every one of `keywords`."""
    avoid = [a for a in avoid or [] if a.strip()]
    best, missing = "", list(keywords)
    for _ in range(TRIES):
        out = provider.extract(
            task="keyword_rewrite",
            instructions=INSTRUCTIONS,
            text=json.dumps(
                {
                    "context": context,
                    "line": line,
                    "keywords": keywords,
                    "avoid": avoid,
                    **({"missing": missing} if best else {}),
                },
                ensure_ascii=False,
            ),
            schema=KeywordLine,
        )
        new = out.text.strip()
        if not new:
            continue
        left = [k for k in keywords if not names(k, new)]
        if not best or len(left) < len(missing):
            best, missing = new, left
        if not left:
            break
        log.info("keyword rewrite left out %s", left)
    if not best:
        raise KeywordError("the AI didn't return a line")
    return best
