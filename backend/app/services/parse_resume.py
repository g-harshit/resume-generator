"""Resume text → `ResumeData`, plus a list of things the user should check.

The model fills `ParsedResume`, a deliberately plain schema: no ids, no defaults,
every field required (what OpenAI's strict structured output wants). Everything
after that is ordinary code: dates are validated, conflicts resolved, and every
bullet is checked against the file. The model is asked to copy, not write; a
bullet we can't find in the file is flagged, because the profile is the only source
of facts for every resume made from it.
"""

import re

from pydantic import BaseModel

from app.ai_providers import AIProvider
from app.schemas.resume import ResumeData

# A resume is a few thousand characters. Past this it's not a resume (or it's a
# portfolio with one attached) and we'd be paying to read a book.
MAX_TEXT_CHARS = 40_000


class TooLongError(Exception):
    pass


# --- what the model fills ------------------------------------------------------


class PLink(BaseModel):
    label: str
    url: str


class PBasics(BaseModel):
    name: str
    headline: str
    email: str
    phone: str
    location: str
    links: list[PLink]


class PExperience(BaseModel):
    company: str
    title: str
    location: str
    start: str | None
    end: str | None
    current: bool
    bullets: list[str]


class PEducation(BaseModel):
    institution: str
    degree: str
    field: str
    location: str
    start: str | None
    end: str | None
    details: str


class PSkillGroup(BaseModel):
    group: str
    items: list[str]


class PProject(BaseModel):
    name: str
    url: str
    start: str | None
    end: str | None
    bullets: list[str]


class PCertification(BaseModel):
    name: str
    issuer: str
    date: str | None
    url: str


class PUnclear(BaseModel):
    section: str
    detail: str


class ParsedResume(BaseModel):
    basics: PBasics
    summary: str
    experience: list[PExperience]
    education: list[PEducation]
    skills: list[PSkillGroup]
    projects: list[PProject]
    certifications: list[PCertification]
    unclear: list[PUnclear]


INSTRUCTIONS = """\
You convert the text of a person's resume into structured data. The text was
extracted from a PDF or Word file, so line breaks and column order may be imperfect.

Rules:
- Copy the person's words exactly. Do not rewrite, summarise, correct, translate or
  improve anything. Each bullet is one achievement or responsibility, copied verbatim
  (drop only the bullet symbol). Join a bullet that was broken across lines.
- Never invent or infer information that is not in the text. If something is not
  there, use an empty string, an empty list, or null.
- Dates: "YYYY-MM" when month and year are given, "YYYY" when only the year is.
  If a date is ambiguous, abbreviated beyond recognition, or missing, use null and add
  an entry to `unclear` quoting what the text says. Never guess a month.
- `current` is true only when the text says the role is ongoing ("Present", "Now",
  "Current"); then `end` is null.
- Keep skills as the person grouped them; if they are not grouped, use one group
  with an empty name. One skill per item.
- `headline` is a title line under the name if there is one (e.g. "Backend Engineer").
- `summary` is an objective/summary/profile paragraph if there is one, verbatim.
- Put anything you could not place or read confidently in `unclear`, with the section
  it belongs to and a short description quoting the text.
"""


# --- after the model -------------------------------------------------------------

_YEAR_MONTH = re.compile(r"^\d{4}(-(0[1-9]|1[0-2]))?$")
_MIN_CHECKED_CHARS = 12  # too short to meaningfully look up ("Go", "SQL")


def _squash(s: str) -> str:
    """Lower-case letters and digits only, so a line broken across columns, re-spaced,
    or with different dashes or bullets still matches."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


class _Converter:
    def __init__(self, source_text: str):
        self.source = _squash(source_text)
        self.warnings: list[dict] = []

    def warn(self, path: str, message: str) -> None:
        self.warnings.append({"path": path, "message": message})

    def date(self, value: str | None, path: str) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        if _YEAR_MONTH.match(value):
            return value
        self.warn(path, f"We couldn't read the date “{value}”. Please enter it.")
        return None

    def span(self, start, end, path: str) -> tuple[str | None, str | None]:
        start = self.date(start, f"{path}.start")
        end = self.date(end, f"{path}.end")
        if start and end and end[: len(start)] < start[: len(end)]:
            self.warn(f"{path}.end", "The end date is before the start date. Please check it.")
            end = None
        return start, end

    def verbatim(self, text: str, path: str) -> str:
        text = text.strip()
        if len(text) >= _MIN_CHECKED_CHARS and _squash(text) not in self.source:
            self.warn(
                path,
                "We couldn't find this exact line in your file. Check it says what you meant.",
            )
        return text

    def bullets(self, items: list[str], path: str) -> list[dict]:
        return [
            {"text": self.verbatim(t, f"{path}.bullets.{i}")[:2000]}
            for i, t in enumerate(t for t in items if t.strip())
        ][:30]


def to_resume_data(parsed: ParsedResume, source_text: str) -> tuple[ResumeData, list[dict]]:
    c = _Converter(source_text)
    b = parsed.basics

    experience = []
    for i, exp in enumerate(parsed.experience[:30]):
        path = f"experience.{i}"
        start, end = c.span(exp.start, exp.end, path)
        if exp.current and end:
            end = None
        if not start:
            c.warn(f"{path}.start", "No start date found for this role.")
        if not exp.current and not end and exp.end is None:
            c.warn(f"{path}.end", "No end date found. If you still work here, mark it current.")
        experience.append(
            {
                "company": exp.company[:200],
                "title": exp.title[:200],
                "location": exp.location[:200],
                "start": start,
                "end": end,
                "current": exp.current,
                "bullets": c.bullets(exp.bullets, path),
            }
        )

    education = []
    for i, edu in enumerate(parsed.education[:15]):
        start, end = c.span(edu.start, edu.end, f"education.{i}")
        education.append(
            {
                "institution": edu.institution[:200],
                "degree": edu.degree[:200],
                "field": edu.field[:200],
                "location": edu.location[:200],
                "start": start,
                "end": end,
                "details": edu.details[:2000],
            }
        )

    skills = []
    for group in parsed.skills[:20]:
        seen: set[str] = set()
        items = []
        for item in group.items:
            item = item.strip()[:80]
            if item and item.lower() not in seen:
                seen.add(item.lower())
                items.append(item)
        if items:
            skills.append({"group": group.group[:200], "items": items[:60]})

    projects = []
    for i, prj in enumerate(parsed.projects[:20]):
        start, end = c.span(prj.start, prj.end, f"projects.{i}")
        projects.append(
            {
                "name": prj.name[:200],
                "url": prj.url[:500],
                "start": start,
                "end": end,
                "bullets": c.bullets(prj.bullets, f"projects.{i}")[:20],
            }
        )

    certifications = [
        {
            "name": cert.name[:200],
            "issuer": cert.issuer[:200],
            "date": c.date(cert.date, f"certifications.{i}.date"),
            "url": cert.url[:500],
        }
        for i, cert in enumerate(parsed.certifications[:30])
        if cert.name.strip()
    ]

    data = ResumeData.model_validate(
        {
            "basics": {
                "name": b.name[:200],
                "headline": b.headline[:200],
                "email": b.email[:200],
                "phone": b.phone[:200],
                "location": b.location[:200],
                "links": [
                    {"label": link.label[:200], "url": link.url[:500]}
                    for link in b.links[:10]
                    if link.url.strip()
                ],
            },
            "summary": c.verbatim(parsed.summary, "summary")[:2000],
            "experience": experience,
            "education": education,
            "skills": skills,
            "projects": projects,
            "certifications": certifications,
        }
    )

    if not data.basics.name:
        c.warn("basics.name", "We couldn't find your name.")
    if not data.basics.email:
        c.warn("basics.email", "No email address found. Recruiters will need one.")
    if not data.basics.phone:
        c.warn("basics.phone", "No phone number found.")
    for item in parsed.unclear:
        c.warn(item.section, item.detail)

    return data, c.warnings


def parse_resume(text: str, provider: AIProvider) -> tuple[ResumeData, list[dict]]:
    if len(text) > MAX_TEXT_CHARS:
        raise TooLongError(
            "This file is much longer than a resume. Upload just your resume "
            "(two or three pages at most)."
        )
    parsed = provider.extract(
        task="parse_resume", instructions=INSTRUCTIONS, text=text, schema=ParsedResume
    )
    return to_resume_data(parsed, text)
