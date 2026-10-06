"""The free ATS checker: what an applicant tracking system reads from a resume file,
and checks we can explain. Plain code, no model (the only model call is reading a
pasted job description, in the router).

No score. Real ATSs (Workday, Greenhouse, Lever, Naukri RMS) don't give resumes a
number; they read the file into text and fields, and recruiters search that. So the
checker shows the text a simple ATS gets — the file's text in the order it's stored,
columns not untangled, Word headers, footers and text boxes left out, as many do —
and checks each thing that commonly goes wrong in that reading.
"""

import io
import re
from dataclasses import asdict, dataclass

import docx
import pymupdf

from app.services.bridge import job_terms
from app.services.extract import DOCX, PDF, ExtractionError, page_has_columns
from app.services.match import names

MAX_TEXT = 20_000  # characters of the ATS's text sent back


@dataclass
class Check:
    id: str
    title: str
    status: str  # "pass" | "warn" | "fail"
    detail: str


@dataclass
class _Facts:
    """What a file's analysis found, before it's turned into checks."""

    text: str
    pages: int
    columns: bool = False
    tables: int = 0
    images: int = 0
    text_boxes: int = 0
    header_footer_text: str = ""


# --- reading the file as a simple ATS would ------------------------------------------


def _pdf_facts(data: bytes) -> _Facts:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ExtractionError("This PDF looks damaged. Try exporting it again.") from exc
    if doc.needs_pass:
        raise ExtractionError("This PDF is password-protected. Upload a copy without a password.")
    with doc:
        # Blocks sorted top to bottom, then left to right: across columns, line by line,
        # which is how a simple parser reads a two-column page.
        text = "\n".join(page.get_text("text", sort=True) for page in doc)
        columns = any(page_has_columns(page) for page in doc)
        tables = 0
        for page in doc:
            try:
                found = page.find_tables()
                tables += sum(1 for t in found.tables if t.row_count >= 2 and t.col_count >= 2)
            except Exception:  # table finding is best effort
                pass
        images = sum(len(page.get_images(full=True)) for page in doc)
        pages = doc.page_count
    return _Facts(text=text, pages=pages, columns=columns, tables=tables, images=images)


def _docx_facts(data: bytes) -> _Facts:
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ExtractionError("This Word file looks damaged. Try saving it again.") from exc
    # The body's own paragraphs only: many ATSs skip headers, footers and text boxes.
    text = "\n".join(p.text for p in document.paragraphs)
    header_footer = "\n".join(
        p.text
        for section in document.sections
        for part in (section.header, section.footer)
        for p in part.paragraphs
        if p.text.strip()
    )
    body = document.element.body
    text_boxes = sum(1 for el in body.iter() if el.tag.endswith("}txbxContent"))
    images = len(document.inline_shapes) + sum(
        1 for el in body.iter() if el.tag.endswith("}anchor")
    )
    # A Word file's pages aren't stored; estimate from its length.
    words = len(text.split()) + sum(len(c.text.split()) for t in document.tables for c in _cells(t))
    return _Facts(
        text=text,
        pages=max(1, round(words / 450)),
        tables=len(document.tables),
        images=images,
        text_boxes=text_boxes,
        header_footer_text=header_footer,
    )


def _cells(table):
    for row in table.rows:
        yield from row.cells


# --- checks ------------------------------------------------------------------------------

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?:\+?\d[\d\s().-]{8,}\d)")
_LINKEDIN = re.compile(r"linkedin\.com/in/", re.IGNORECASE)
_GARBLE = re.compile(r"\(cid:\d+\)|�")
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DATE = re.compile(
    rf"\b{_MONTH}\s*'?\d{{2,4}}\b|\b(?:0?[1-9]|1[0-2])[/.-](?:19|20)\d{{2}}\b"
    r"|\b(?:19|20)\d{2}\s*[-–—]\s*(?:(?:19|20)\d{2}|present|current|now)\b",
    re.IGNORECASE,
)
_HEADINGS = {
    "experience": r"(work |professional )?experience|employment( history)?"
    r"|work history|career history",
    "education": r"education|academic (background|qualifications?)|qualifications?",
    "skills": r"(technical |key |core )?skills|technologies|tech stack|competencies",
    "summary": r"(professional )?summary|profile|about me|objective",
    "projects": r"(personal |academic |key )?projects",
}


def _headings(text: str) -> set[str]:
    found = set()
    for line in text.splitlines():
        line = line.strip().strip(":").strip()
        if not line or len(line) > 40:
            continue
        for name, pattern in _HEADINGS.items():
            if re.fullmatch(pattern, line, re.IGNORECASE):
                found.add(name)
    return found


def _checks(f: _Facts, mime: str, size: int) -> list[Check]:
    text = f.text
    words = len(text.split())
    out: list[Check] = []

    readable = len(text.strip()) >= 200
    out.append(
        Check(
            "text",
            "Text an ATS can read",
            "pass" if readable else "fail",
            f"We read {words} words from the file."
            if readable
            else "Almost no text came out. A scanned or image-only resume is blank to an ATS: "
            "export a PDF from Word or Google Docs instead.",
        )
    )
    garbled = len(_GARBLE.findall(text))
    out.append(
        Check(
            "garbled",
            "Characters come out as written",
            "fail" if garbled > 5 else "warn" if garbled else "pass",
            "Some characters come out as junk (an unusual font or a PDF without its fonts). "
            "Re-export the PDF, or use a standard font."
            if garbled
            else "No garbled characters.",
        )
    )
    out.append(
        Check(
            "columns",
            "One column",
            "warn" if f.columns else "pass",
            "Your layout has two columns. Many ATSs read straight across the page, mixing the "
            "columns' lines together — see the text below. A single column is safest."
            if f.columns
            else "Single column: read top to bottom, in order.",
        )
    )
    out.append(
        Check(
            "tables",
            "No tables",
            "warn" if f.tables else "pass",
            f"Found {f.tables} table{'s' if f.tables > 1 else ''}. Some ATSs scramble or skip "
            "text in tables; plain lines are safer."
            if f.tables
            else "No tables.",
        )
    )
    if mime == DOCX:
        out.append(
            Check(
                "text_boxes",
                "No text boxes",
                "warn" if f.text_boxes else "pass",
                f"Found {f.text_boxes} text box{'es' if f.text_boxes > 1 else ''}. Many ATSs "
                "skip text in text boxes entirely."
                if f.text_boxes
                else "No text boxes.",
            )
        )
        contact_hidden = bool(
            _EMAIL.search(f.header_footer_text) or _PHONE.search(f.header_footer_text)
        )
        out.append(
            Check(
                "header_footer",
                "Contact details in the page, not the header",
                "fail" if contact_hidden else "pass",
                "Your email or phone is in the Word header or footer, which many ATSs never "
                "read. Move them into the page."
                if contact_hidden
                else "Nothing important is in the header or footer.",
            )
        )
    out.append(
        Check(
            "images",
            "No images or icons",
            "warn" if f.images else "pass",
            f"Found {f.images} image{'s' if f.images > 1 else ''}. An ATS can't read text in "
            "images: if a photo, logo or icons carry anything (a phone icon, skill bars), "
            "write it as text."
            if f.images
            else "No images.",
        )
    )

    email = _EMAIL.search(text)
    phone = _PHONE.search(text)
    out.append(
        Check(
            "email",
            "Email address",
            "pass" if email else "fail",
            f"Found {email.group(0)}." if email else "No email address in the text an ATS reads.",
        )
    )
    out.append(
        Check(
            "phone",
            "Phone number",
            "pass" if phone else "warn",
            f"Found {' '.join(phone.group(0).split())}."
            if phone
            else "No phone number in the text an ATS reads.",
        )
    )
    out.append(
        Check(
            "linkedin",
            "LinkedIn profile",
            "pass" if _LINKEDIN.search(text) else "warn",
            "Found your LinkedIn address."
            if _LINKEDIN.search(text)
            else "No linkedin.com/in/… address. Recruiters look for it; write it out in full.",
        )
    )

    headings = _headings(text)
    needed = ["experience", "education", "skills"]
    if "experience" not in headings and "projects" in headings:
        needed = ["projects", "education", "skills"]  # a student's resume
    missing = [h for h in needed if h not in headings]
    out.append(
        Check(
            "headings",
            "Standard section headings",
            "pass" if not missing else "warn",
            f"Found: {', '.join(sorted(headings))}."
            if not missing
            else f"Couldn't find a {', '.join(missing)} heading. ATSs sort your resume by "
            "standard headings — use “Experience”, “Education”, “Skills” rather than creative "
            "ones, each on its own line."
            + (
                " Here the two columns mix headings into other lines — see the text below."
                if f.columns
                else ""
            ),
        )
    )
    dates = len(_DATE.findall(text))
    out.append(
        Check(
            "dates",
            "Dates an ATS can read",
            "pass" if dates >= 2 else "warn",
            f"Found {dates} dates."
            if dates >= 2
            else "Few or no dates found. Write them like “Jan 2022 – Present” or "
            "“2019 – 2021” so an ATS can work out your experience.",
        )
    )
    long = f.pages > 2
    thin = words < 250
    out.append(
        Check(
            "length",
            "Length",
            "warn" if long or thin else "pass",
            f"{f.pages} page{'s' if f.pages > 1 else ''}"
            f"{' (estimated)' if mime == DOCX else ''}, {words} words. "
            + (
                "Over two pages: recruiters rarely read that far."
                if long
                else "Quite short: add what you did and its results."
                if thin
                else "A good length."
            ),
        )
    )
    out.append(
        Check(
            "file",
            "File type",
            "pass",
            f"{'PDF' if mime == PDF else 'Word (.docx)'}, {size // 1024} KB: every ATS takes it.",
        )
    )
    return out


def analyse(data: bytes, mime: str, filename: str) -> dict:
    """The checker's report on one file: the text an ATS reads, and the checks."""
    facts = _pdf_facts(data) if mime == PDF else _docx_facts(data)
    text = re.sub(r"\n{3,}", "\n\n", facts.text).strip()
    facts.text = text
    checks = _checks(facts, mime, len(data))
    return {
        "filename": filename[:255],
        "file_type": "pdf" if mime == PDF else "docx",
        "pages": facts.pages,
        "words": len(text.split()),
        "ats_text": text[:MAX_TEXT],
        "checks": [asdict(c) for c in checks],
        "keywords": None,
    }


def keyword_coverage(text: str, parsed_job: dict) -> dict:
    """Which of the job's skills and keywords the resume's text names."""
    terms = job_terms(parsed_job)
    covered = [t for t in terms if names(t, text)]
    return {
        "job_title": " — ".join(
            x for x in (parsed_job.get("title"), parsed_job.get("company")) if x
        ),
        "covered": covered,
        "missing": [t for t in terms if t not in covered],
    }
