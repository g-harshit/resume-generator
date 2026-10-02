"""The templates on offer.

Every template is the same HTML (`templates/resume.html.j2`) with its own stylesheet,
so the things an applicant tracking system depends on — one column, real text,
standard section headings, contact details in the body, reading order — are written
once and can't be broken by a new look. `tests/test_rendering.py` checks each
template's PDF for exactly those.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Template:
    slug: str
    name: str
    description: str


TEMPLATES: list[Template] = [
    Template("classic", "Classic", "Serif, centred header. Safe for any industry."),
    Template("modern", "Modern", "Clean sans-serif with one accent colour; dates on the right."),
    Template("compact", "Compact", "Tighter spacing, so eight-plus years still fit on one page."),
    Template("executive", "Executive", "Larger name and a summary-led layout for senior roles."),
]

BY_SLUG = {t.slug: t for t in TEMPLATES}
