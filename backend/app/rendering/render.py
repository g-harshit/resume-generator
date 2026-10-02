"""ResumeData + a template → HTML (the in-app preview) or PDF (the download).

Both come from the same HTML, so the preview can't drift from the file.
"""

import base64
import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

import jinja2
from markupsafe import Markup

from app.rendering.catalog import BY_SLUG
from app.schemas.layout import Layout
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


_MAX_LINK_TEXT = 45


def _short(text: str) -> str:
    """ "credly.com/badges/3f1c…/public_url" → "credly.com/…": a credential link is long
    and means nothing to read; the full address stays in the link."""
    if len(text) <= _MAX_LINK_TEXT or "/" not in text:
        return text
    return text.split("/", 1)[0] + "/…"


def link_for(url: str) -> Link | None:
    url = url.strip()
    if not url:
        return None
    text = _short(re.sub(r"^https?://(www\.)?", "", url).rstrip("/"))
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
        digits = re.sub(r"[^\d+]", "", b.phone)
        items.append(Link(b.phone, f"tel:{digits}" if len(digits) >= 6 else None))
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


# "Narrow" margins: the same on all four sides, and a little less space between
# sections. Comes after the template's own CSS, so it wins.
NARROW_MM = 10
# Fitting more on a page: tighter spacing between sections and entries too.
_TIGHT_CSS = (
    ".section { margin-top: 0.6em; } .entry { margin-top: 0.4em; } .head { margin-bottom: 0.6em; }"
)


def _margin_css(mm: int) -> str:
    """The same margin on all four sides, in the PDF and the on-screen preview."""
    return f"@page {{ margin: {mm}mm; }}\n@media screen {{ .page {{ padding: {mm}mm; }} }}\n"


def _layout_css(layout: Layout) -> Markup:
    if layout.margins == "narrow":
        return Markup(_margin_css(NARROW_MM) + _TIGHT_CSS)
    if layout.margins == "custom" and layout.margin_mm is not None:
        css = _margin_css(layout.margin_mm)
        return Markup(css + (_TIGHT_CSS if layout.margin_mm <= NARROW_MM else ""))
    return Markup("")


def render_html(data: ResumeData, slug: str, layout: Layout | None = None) -> str:
    if slug not in BY_SLUG:
        raise UnknownTemplate(slug)
    layout = layout or Layout()
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
            hidden=set(layout.hidden),
            order=layout.sections(),
            layout_css=_layout_css(layout),
        )
    )


def render_letter_html(data: ResumeData, body: str, company: str, slug: str) -> str:
    if slug not in BY_SLUG:
        raise UnknownTemplate(slug)
    today = date.today()
    return (
        _env()
        .get_template("letter.html.j2")
        .render(
            b=data.basics,
            slug=slug,
            contact=_contact(data),
            base_css=_css("base.css"),
            template_css=_css(f"{slug}.css"),
            paragraphs=[p.strip() for p in body.split("\n\n") if p.strip()],
            company=company,
            today=f"{today.day} {today.strftime('%B %Y')}",
        )
    )


# --- PDF ---------------------------------------------------------------------------

# WeasyPrint loads Pango & co. from the system. Homebrew on Apple silicon installs them
# where macOS doesn't look by default; point it there before the import. (On Linux
# they're ordinary system packages and this does nothing.)
if sys.platform == "darwin" and Path("/opt/homebrew/lib").is_dir():
    os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib")

import pymupdf  # noqa: E402
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


@dataclass
class PageView:
    image: str  # a data: URL
    # Where the PDF's links are on this page, as fractions of its width and height, so
    # the preview can make them clickable over the image.
    links: list[dict]


_SAFE_LINK = re.compile(r"^(https?:|mailto:|tel:)", re.IGNORECASE)


def page_images(pdf: bytes, dpi: int = 144) -> list[PageView]:
    """Each page of the PDF as an image, with its links, for the preview: the page
    breaks the browser can't know, exactly where the download has them. 144 dpi is
    sharp on high-density screens at preview size; JPEG keeps it to ~100 KB a page."""
    out = []
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        for page in doc:
            w, h = page.rect.width, page.rect.height
            pix = page.get_pixmap(dpi=dpi).tobytes("jpeg", jpg_quality=85)
            links = [
                {
                    "x": link["from"].x0 / w,
                    "y": link["from"].y0 / h,
                    "w": link["from"].width / w,
                    "h": link["from"].height / h,
                    "url": link["uri"],
                }
                for link in page.get_links()
                if _SAFE_LINK.match(link.get("uri") or "")
            ]
            out.append(PageView("data:image/jpeg;base64," + base64.b64encode(pix).decode(), links))
    return out
