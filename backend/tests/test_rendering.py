"""Every template, checked the way an applicant tracking system reads a resume: by
pulling the text out of the PDF. If a template change breaks reading order, puts
contact details in a page header, or turns text into something unextractable, these
fail."""

import pymupdf
import pytest

from app.rendering.catalog import TEMPLATES
from app.rendering.render import date_range, format_date, link_for, render_html, render_pdf
from app.schemas.resume import ResumeData

PROFILE = ResumeData.model_validate(
    {
        "basics": {
            "name": "Meera Iyer",
            "headline": "Senior Backend Engineer",
            "email": "meera.iyer@example.com",
            "phone": "+91 98000 12345",
            "location": "Pune, India",
            "links": [
                {"label": "LinkedIn", "url": "linkedin.com/in/meera-iyer"},
                {"label": "Evil", "url": "javascript:alert(1)"},
            ],
        },
        "summary": "Backend engineer with 7 years of experience building payment systems in Go.",
        "experience": [
            {
                "company": "Paylane",
                "title": "Senior Backend Engineer",
                "location": "Pune",
                "start": "2021-03",
                "current": True,
                "bullets": [
                    {
                        "text": "Designed the reconciliation service that matches 3M bank "
                        "transactions a day, cutting manual review by 60%."
                    },
                    {"text": "Migrated settlement jobs from cron scripts to Kafka consumers."},
                    {"text": "Escaped, not run: <script>alert(1)</script> & <b>bold</b>"},
                ],
            },
            {
                "company": "Tradewise",
                "title": "Software Engineer",
                "start": "2019-07",
                "end": "2021-02",
                "bullets": [
                    {"text": "Built the order-matching API in Go serving 1,200 requests a second."}
                ],
            },
        ],
        "education": [
            {
                "institution": "College of Engineering Pune",
                "degree": "B.E.",
                "field": "Computer Engineering",
                "start": "2013",
                "end": "2017",
            }
        ],
        "skills": [
            {"group": "Languages", "items": ["Go", "Python", "SQL"]},
            {"group": "", "items": ["PostgreSQL", "Kafka"]},
        ],
        "projects": [
            {
                "name": "ledgerkit",
                "url": "https://github.com/example/ledgerkit",
                "bullets": [{"text": "A double-entry accounting library for Go."}],
            }
        ],
        "certifications": [
            {"name": "AWS Certified Developer", "issuer": "Amazon Web Services", "date": "2022"}
        ],
    }
)

HEADINGS = ["Summary", "Experience", "Education", "Skills", "Projects", "Certifications"]
MM = 72 / 25.4  # points per millimetre


def flat(text: str) -> str:
    return " ".join(text.split())


@pytest.fixture(scope="module", params=[t.slug for t in TEMPLATES])
def rendered(request):
    html = render_html(PROFILE, request.param)
    pdf = render_pdf(html)
    doc = pymupdf.open(stream=pdf.content, filetype="pdf")
    text = flat(" ".join(page.get_text("text") for page in doc))
    return {"slug": request.param, "html": html, "pdf": pdf, "doc": doc, "text": text}


def test_fits_on_one_page(rendered):
    assert rendered["pdf"].pages == 1


def test_contact_details_are_in_the_text_and_come_first(rendered):
    text = rendered["text"]
    for value in [
        "meera.iyer@example.com",
        "+91 98000 12345",
        "Pune, India",
        "linkedin.com/in/meera-iyer",
    ]:
        assert value in text, value
    assert (
        text.lower().index("meera iyer")
        < text.index("meera.iyer@example.com")
        < text.lower().index("summary")  # some templates uppercase headings in CSS
    )


def test_standard_headings_in_order(rendered):
    text = rendered["text"]
    positions = [text.lower().index(h.lower()) for h in HEADINGS]
    assert positions == sorted(positions)


def test_every_line_reads_as_one_unbroken_string(rendered):
    text = rendered["text"]
    for exp in PROFILE.experience:
        for bullet in exp.bullets:
            assert flat(bullet.text) in text, bullet.text
    assert flat(PROFILE.summary) in text


def test_roles_read_in_order_with_their_dates(rendered):
    text = rendered["text"]
    paylane, tradewise = text.index("Paylane"), text.index("Tradewise")
    assert (
        paylane < text.index("Mar 2021 – Present") < tradewise < text.index("Jul 2019 – Feb 2021")
    )
    assert text.index("Senior Backend Engineer, Paylane") < text.index(
        "Designed the reconciliation"
    )


def test_nothing_in_the_page_margins(rendered):
    """No running header or footer: ATS parsers often skip those, taking contact
    details with them. Every template's margins are at least 11 mm."""
    for page in rendered["doc"]:
        for _x0, y0, _x1, y1, *_ in page.get_text("blocks"):
            assert y0 >= 10 * MM and y1 <= page.rect.height - 10 * MM, (rendered["slug"], y0, y1)


def test_text_is_real_text_with_embedded_fonts(rendered):
    for page in rendered["doc"]:
        fonts = page.get_fonts()
        assert fonts
        assert all(ext != "n/a" for _, ext, *_ in fonts)  # "n/a" = not embedded


EXPECTED_FONT = {
    "classic": "Georgia",
    "modern": "Helvetica",
    "compact": "Arial",
    "executive": "Georgia",
}


def test_the_template_font_is_the_one_used(rendered):
    """Catches a stylesheet that silently doesn't apply (it happened: autoescaped CSS
    quotes made every template fall back to Times)."""
    fonts = {f[3] for page in rendered["doc"] for f in page.get_fonts()}
    assert any(EXPECTED_FONT[rendered["slug"]] in f for f in fonts), fonts
    assert "&#34;" not in rendered["html"]


def test_user_text_is_escaped_not_run(rendered):
    assert "<script>" not in rendered["html"]
    assert "&lt;script&gt;" in rendered["html"]
    assert "<script>alert(1)</script> & <b>bold</b>" in rendered["text"]


def test_only_http_links_are_clickable(rendered):
    assert 'href="javascript:' not in rendered["html"]
    uris = {link.get("uri") for page in rendered["doc"] for link in page.get_links()}
    assert "https://linkedin.com/in/meera-iyer" in uris
    assert "https://github.com/example/ledgerkit" in uris
    assert "mailto:meera.iyer@example.com" in uris
    assert not any(u and u.startswith("javascript:") for u in uris)


def test_a_long_profile_runs_to_more_pages():
    long = PROFILE.model_copy(deep=True)
    for exp in long.experience:
        exp.bullets = exp.bullets * 10
    assert render_pdf(render_html(long, "classic")).pages >= 2


@pytest.mark.parametrize(
    ("start", "end", "current", "expected"),
    [
        ("2021-03", None, True, "Mar 2021 – Present"),
        ("2019-07", "2021-02", False, "Jul 2019 – Feb 2021"),
        ("2013", "2017", False, "2013 – 2017"),
        ("2020", "2020", False, "2020"),
        (None, "2017", False, "2017"),
        (None, None, False, ""),
    ],
)
def test_date_range(start, end, current, expected):
    assert date_range(start, end, current) == expected


def test_format_date():
    assert format_date("2022-12") == "Dec 2022"
    assert format_date(None) == ""


@pytest.mark.parametrize(
    ("url", "text", "href"),
    [
        ("https://www.example.com/me/", "example.com/me", "https://www.example.com/me/"),
        ("linkedin.com/in/x", "linkedin.com/in/x", "https://linkedin.com/in/x"),
        ("javascript:alert(1)", "javascript:alert(1)", None),
        ("mailto:x@example.com", "mailto:x@example.com", None),
    ],
)
def test_link_for(url, text, href):
    link = link_for(url)
    assert (link.text, link.href) == (text, href)


# --- endpoints -----------------------------------------------------------------


def test_templates_are_listed(client):
    slugs = [t["slug"] for t in client.get("/templates").json()]
    assert slugs == ["classic", "modern", "compact", "executive"]


def test_preview_and_pdf_need_a_profile(client, auth):
    r = client.get("/templates/classic/preview", headers=auth)
    assert r.status_code == 404
    assert "Upload your resume first" in r.json()["detail"]


def test_preview_and_pdf_render_the_profile(client, auth):
    data = PROFILE.model_dump(mode="json")
    client.put("/profile", headers=auth, json={"version": 0, "data": data})

    preview = client.get("/templates/modern/preview", headers=auth).json()
    assert "Meera Iyer" in preview["html"] and preview["pages"] == 1

    r = client.get("/templates/modern/pdf", headers=auth)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"] == 'attachment; filename="Meera-Iyer-Resume.pdf"'
    assert r.headers["x-page-count"] == "1"
    assert r.content.startswith(b"%PDF-")


def test_unknown_template_is_not_found(client, auth):
    client.put(
        "/profile", headers=auth, json={"version": 0, "data": PROFILE.model_dump(mode="json")}
    )
    assert client.get("/templates/fancy/pdf", headers=auth).status_code == 404
