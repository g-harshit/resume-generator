"""Resume text → `ResumeData`, plus a list of things the user should check.

The model fills `ParsedResume`, a deliberately plain schema: no ids, no defaults,
every field required (what OpenAI's strict structured output wants). Everything
after that is ordinary code. Dates in particular: the model copies them exactly as
written and `read_date` interprets them, because a model asked for "YYYY-MM" will
confidently turn "Jul 2019 – 21" into 2021 and drop the month without saying so.
Every bullet is checked against the file. The model is asked to copy, not write; a
bullet we can't find in the file is flagged, because the profile is the only source
of facts for every resume made from it.
"""

import re
from typing import NamedTuple

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
    start: str  # as written: "Mar 2021", "03/2021", "2019"; "" if none
    end: str  # as written, including "Present"; "" if none
    bullets: list[str]


class PEducation(BaseModel):
    institution: str
    degree: str
    field: str
    location: str
    start: str
    end: str
    details: str


class PSkillGroup(BaseModel):
    group: str
    items: list[str]


class PProject(BaseModel):
    name: str
    url: str
    start: str
    end: str
    bullets: list[str]


class PCertification(BaseModel):
    name: str
    issuer: str
    date: str
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
  there, use an empty string or an empty list.
- Dates: copy each start and end date exactly as written ("Mar 2021", "03/2021",
  "2019", "Present", "21"). Do not reformat, complete or correct them. For a range
  like "Jul 2019 - 21", start is "Jul 2019" and end is "21". Empty string if none.
- Keep skills as the person grouped them; if they are not grouped, use one group
  with an empty name. One skill per item.
- `headline` is the job title under the name if there is one (e.g. "Backend
  Engineer"), without the location or contact details, which have their own fields.
- `summary` is an objective/summary/profile paragraph if there is one, verbatim.
- Put anything you could not place or read confidently in `unclear`, with the section
  it belongs to and a short description quoting the text.
"""


# --- after the model -------------------------------------------------------------

_MIN_CHECKED_CHARS = 12  # too short to meaningfully look up ("Go", "SQL")

_MONTHS = {
    name: i + 1
    for i, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ]
    )
    for name in names
}
_SEASONS = {"spring", "summer", "fall", "autumn", "winter"}
_PRESENT = {"present", "current", "currently", "now", "today", "ongoing", "till date", "to date"}


class DateReading(NamedTuple):
    value: str | None  # "YYYY" or "YYYY-MM"
    current: bool  # the text said "Present" or similar
    readable: bool  # False: there was text and we couldn't make a date of it


def read_date(text: str) -> DateReading:
    """Interpret a date exactly as a resume wrote it. Only unambiguous forms are
    accepted; anything else is reported unreadable rather than guessed."""
    t = re.sub(r"\s+", " ", text.strip().lower()).strip(" .,")
    if not t:
        return DateReading(None, False, True)
    if t in _PRESENT:
        return DateReading(None, True, True)

    def ym(year: int, month: int | None = None) -> DateReading:
        if not 1900 <= year <= 2100 or (month is not None and not 1 <= month <= 12):
            return DateReading(None, False, False)
        return DateReading(
            f"{year:04d}" if month is None else f"{year:04d}-{month:02d}", False, True
        )

    if m := re.fullmatch(r"(\d{4})", t):
        return ym(int(m[1]))
    if m := re.fullmatch(r"(\d{4})[-/.](\d{1,2})", t):
        return ym(int(m[1]), int(m[2]))
    if m := re.fullmatch(r"(\d{1,2})[-/.](\d{4})", t):
        return ym(int(m[2]), int(m[1]))
    # A month or season name and a year, in either order, separated by any of
    # space . , - / ("April-2022", "Mar/2021", "2022-Apr", "Jul '19").
    sep = r"[\s.,/-]*"
    year_pattern = r"(\d{4}|['’]\d{2})"
    if m := re.fullmatch(rf"([a-z]+){sep}{year_pattern}", t):
        word, year_text = m[1], m[2]
    elif m := re.fullmatch(rf"(\d{{4}}){sep}([a-z]+)", t):
        year_text, word = m[1], m[2]
    else:
        return DateReading(None, False, False)
    # '21 is an explicit abbreviation (apostrophe), unlike a bare "21".
    year = int(year_text) if year_text[0].isdigit() else 2000 + int(year_text[1:])
    if word in _MONTHS:
        return ym(year, _MONTHS[word])
    if word in _SEASONS:
        return ym(year)
    return DateReading(None, False, False)


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

    def date(self, text: str, path: str) -> DateReading:
        reading = read_date(text)
        if not reading.readable:
            self.warn(path, f"We couldn't read the date “{text.strip()}”. Please enter it.")
        return reading

    def span(
        self, start_text: str, end_text: str, path: str
    ) -> tuple[str | None, str | None, bool]:
        start = self.date(start_text, f"{path}.start").value
        end_reading = self.date(end_text, f"{path}.end")
        end, current = end_reading.value, end_reading.current
        if start and end and end[: len(start)] < start[: len(end)]:
            self.warn(f"{path}.end", "The end date is before the start date. Please check it.")
            end = None
        return start, end, current

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
        start, end, current = c.span(exp.start, exp.end, path)
        if not exp.start.strip():
            c.warn(f"{path}.start", "No start date found for this role.")
        if not exp.end.strip():
            c.warn(f"{path}.end", "No end date found. If you still work here, mark it current.")
        experience.append(
            {
                "company": exp.company[:200],
                "title": exp.title[:200],
                "location": exp.location[:200],
                "start": start,
                "end": end,
                "current": current,
                "bullets": c.bullets(exp.bullets, path),
            }
        )

    education = []
    for i, edu in enumerate(parsed.education[:15]):
        start, end, _ = c.span(edu.start, edu.end, f"education.{i}")
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
        start, end, _ = c.span(prj.start, prj.end, f"projects.{i}")
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
            "date": c.date(cert.date, f"certifications.{i}.date").value,
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
