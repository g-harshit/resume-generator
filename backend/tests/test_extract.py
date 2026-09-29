import pytest

from app.services.extract import (
    DOCX,
    PDF,
    ExtractionError,
    extract_text,
    sniff_type,
)
from tests import fixtures


def test_file_type_comes_from_the_bytes():
    assert sniff_type(fixtures.two_column_pdf()) == PDF
    assert sniff_type(fixtures.resume_docx()) == DOCX
    assert sniff_type(b"GIF89a....") is None
    assert sniff_type(b"PK\x03\x04 not really a zip") is None


def test_two_column_pdf_reads_each_column_top_to_bottom():
    text = extract_text(fixtures.two_column_pdf(), PDF)
    lines = [line for line in text.splitlines() if line.strip()]
    assert lines[0].startswith("Asha Rao - Backend Engineer")  # full-width header first

    # The sidebar is read as one run, then the main column as one run: no interleaving.
    # (Long lines wrap inside their box, so find each by its opening words.)
    def pos(s):
        return next(i for i, line in enumerate(lines) if line.startswith(s[:20]))

    sidebar = [pos(s) for s in fixtures.SIDEBAR]
    main = [pos(m) for m in fixtures.MAIN]
    assert sidebar == sorted(sidebar)
    assert main == sorted(main)
    assert max(sidebar) < min(main)


def test_right_aligned_dates_stay_with_their_role():
    lines = extract_text(fixtures.dated_single_column_pdf(), PDF).splitlines()
    role = lines.index("Backend Engineer, Finlytics")
    assert lines[role + 1] == "Mar 2021 - Present"
    role = lines.index("Software Engineer, Cartwheel")
    assert lines[role + 1] == "Jul 2019 - Feb 2021"


def test_docx_includes_the_header_and_tables_in_order():
    lines = extract_text(fixtures.resume_docx(), DOCX).splitlines()
    assert lines[0] == "Asha Rao · asha.rao@example.com"
    assert lines.index("Skills") < lines.index("Go, PostgreSQL, Kafka, gRPC")
    assert (
        lines.index("Experience")
        < lines.index("Skills")
        < lines.index("Education: B.Tech Computer Science, 2019")
    )


def test_a_pdf_with_no_text_is_explained():
    with pytest.raises(ExtractionError, match="scan or a photo"):
        extract_text(fixtures.blank_pdf(), PDF)


def test_a_damaged_pdf_is_explained():
    with pytest.raises(ExtractionError, match="damaged"):
        extract_text(b"%PDF-1.7 garbage", PDF)
