"""ResumeData + a template → HTML (the in-app preview) or PDF (the download).

Both come from the same HTML, so the preview can't drift from the file.
"""

import os
import re
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import jinja2
from markupsafe import Markup

from app.rendering.catalog import BY_SLUG
from app.schemas.resume import ResumeData

_DIR = Path(__file__).parent / "templates"
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class UnknownTemplate(Exception):
    pass


def format_date(value: str | None) -> str:
    """'2021-03' → 'Mar 2021', '2019' → '2019'."""
    if not value:
        return ""
    year, _, month = value.partition("-")
    return f"{_MONTHS[int(month) - 1]} {year}" if month else year


def date_range(start: str | None, end: str | None, current: bool) -> str:
    a = format_date(start)
    b = "Present" if current else format_date(end)
    if a and b:
        return a if a == b else f"{a} – {b}"
    return a or b


@dataclass
class Link:
    text: str
    href: str | None  # only http(s); anything else is shown as text, never linked


def link_for(url: str) -> Link | None:
    url = url.strip()
    if not url:
        return None
    text = re.sub(r"^https?://(www\.)?", "", url).rstrip("/")
    if re.match(r"^https?://", url, re.I):
        return Link(text, url)
    if re.match(r"^[\w-]+(\.[\w-]+)+(/\S*)?$", url):  # "linkedin.com/in/asha"
        return Link(text, f"https://{url}")
    return Link(text, None)  # "javascript:…" and friends stay inert text


def _contact(data: ResumeData) -> list[Link]:
    b = data.basics
    items = []
    if b.location:
        items.append(Link(b.location, None))
    if b.email:
        items.append(Link(b.email, f"mailto:{b.email}"))
    if b.phone:
        items.append(Link(b.phone, None))
    items += [link for link in (link_for(x.url) for x in b.links) if link]
    return items


@cache
def _env() -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(_DIR),
        autoescape=True,  # everything in the resume is user text
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


@cache
def _css(name: str) -> Markup:
    # Our own stylesheet, so marked safe. Autoescaping it turned the quotes in
    # `font-family: "Helvetica Neue"` into &#34;, and browsers and WeasyPrint both
    # dropped the rule: every template silently fell back to Times.
    return Markup((_DIR / name).read_text())


def render_html(data: ResumeData, slug: str) -> str:
    if slug not in BY_SLUG:
        raise UnknownTemplate(slug)
    return (
        _env()
        .get_template("resume.html.j2")
        .render(
            data=data,
            b=data.basics,
            slug=slug,
            contact=_contact(data),
            base_css=_css("base.css"),
            template_css=_css(f"{slug}.css"),
            date_range=date_range,
            format_date=format_date,
            link_for=link_for,
        )
    )


# --- PDF ---------------------------------------------------------------------------

# WeasyPrint loads Pango & co. from the system. Homebrew on Apple silicon installs them
# where macOS doesn't look by default; point it there before the import. (On Linux
# they're ordinary system packages and this does nothing.)
if sys.platform == "darwin" and Path("/opt/homebrew/lib").is_dir():
    os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib")

import weasyprint  # noqa: E402


def _no_fetching(url: str, *args, **kwargs):
    """Rendering never fetches anything: the HTML carries its CSS, and the resume has
    no images. Refusing every URL means user-supplied text can never make the server
    request an address."""
    raise ValueError(f"Rendering does not fetch resources ({url[:60]})")


@dataclass
class Pdf:
    content: bytes
    pages: int


def render_pdf(html: str) -> Pdf:
    document = weasyprint.HTML(string=html, url_fetcher=_no_fetching).render()
    return Pdf(document.write_pdf(), len(document.pages))
