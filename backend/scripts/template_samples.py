"""Render one invented sample resume in every template, as the images the template
picker shows: apps/web/public/templates/<slug>.jpg (page one, 144 dpi).

The picker shows the same sample every time instead of laying out each user's own
profile four times on every visit. Run again after changing a template:

    cd backend && uv run python -m scripts.template_samples
"""

# ruff: noqa: E501 — the sample's lines read better unwrapped.
import base64
from pathlib import Path

from app.ai_providers.stub import StubProvider
from app.rendering.catalog import TEMPLATES
from app.rendering.render import page_images, render_html, render_pdf
from app.schemas.layout import Layout
from app.schemas.resume import ResumeData
from app.services.fit import fill_page

OUT = Path(__file__).resolve().parents[2] / "apps" / "web" / "public" / "templates"

# Everyone and everything here is invented.
SAMPLE = ResumeData.model_validate(
    {
        "basics": {
            "name": "Maya Kapoor",
            "headline": "Senior Software Engineer",
            "email": "maya.kapoor@example.com",
            "phone": "+91 98765 00000",
            "location": "Bengaluru, India",
            "links": [{"id": "l1", "label": "GitHub", "url": "https://github.com/example"}],
        },
        "summary": (
            "Backend engineer with seven years building payment and logistics systems in Go "
            "and Python. Led the move of a settlement platform to event-driven services on "
            "AWS, cut API latency by 85%, and mentors a team of five. Comfortable owning "
            "systems end to end, from design reviews to on-call."
        ),
        "experience": [
            {
                "id": "e1",
                "company": "Northwind Payments",
                "title": "Senior Software Engineer",
                "location": "Bengaluru",
                "start": "2022-04",
                "current": True,
                "bullets": [
                    {"id": "e1b1", "text": "Led the design of an event-driven settlement platform in Go on Kafka, processing 4M transactions a day."},
                    {"id": "e1b2", "text": "Cut p99 latency of the payouts API from 900 ms to 140 ms with PostgreSQL index and query tuning."},
                    {"id": "e1b3", "text": "Introduced OpenTelemetry tracing across 14 services, halving time to find incidents."},
                    {"id": "e1b4", "text": "Designed idempotent payout retries that removed duplicate transfers."},
                    {"id": "e1b5", "text": "Mentored five engineers and ran the team's on-call rotation."},
                ],
            },
            {
                "id": "e2",
                "company": "Cartwheel Logistics",
                "title": "Software Engineer",
                "location": "Pune",
                "start": "2019-06",
                "end": "2022-03",
                "bullets": [
                    {"id": "e2b1", "text": "Built the order-routing service in Python and FastAPI serving 40 warehouses."},
                    {"id": "e2b2", "text": "Moved nightly batch jobs to Airflow, cutting failed runs by 70%."},
                    {"id": "e2b3", "text": "Containerised 12 services with Docker and deployed them on AWS ECS."},
                    {"id": "e2b4", "text": "Built a Redis-backed rate limiter shared by all public APIs."},
                ],
            },
            {
                "id": "e3",
                "company": "Brightlane Software",
                "title": "Associate Engineer",
                "location": "Pune",
                "start": "2017-07",
                "end": "2019-05",
                "bullets": [
                    {"id": "e3b1", "text": "Maintained Java services for a retail banking client."},
                    {"id": "e3b2", "text": "Wrote integration tests that cut release bugs by half."},
                    {"id": "e3b3", "text": "Automated monthly releases with Jenkins pipelines."},
                ],
            },
        ],
        "education": [
            {
                "id": "ed1",
                "institution": "College of Engineering, Pune",
                "degree": "B.Tech",
                "field": "Computer Engineering",
                "start": "2013",
                "end": "2017",
            }
        ],
        "skills": [
            {"id": "s1", "group": "Languages", "items": ["Go", "Python", "Java", "SQL"]},
            {"id": "s2", "group": "Data & messaging", "items": ["PostgreSQL", "Kafka", "Redis"]},
            {"id": "s3", "group": "Cloud & tools", "items": ["AWS", "Docker", "Airflow", "OpenTelemetry"]},
        ],
        "projects": [
            {
                "id": "p1",
                "name": "ledgerkit",
                "bullets": [
                    {"id": "p1b1", "text": "Open-source double-entry ledger library in Go, used by three startups."},
                    {"id": "p1b2", "text": "Property-based tests that check every posting balances."},
                ],
            },
            {
                "id": "p2",
                "name": "queue-watch",
                "bullets": [{"id": "p2b1", "text": "A small CLI that shows Kafka consumer lag per partition."}],
            }
        ],
        "certifications": [
            {"id": "c1", "name": "AWS Certified Developer – Associate", "issuer": "Amazon Web Services", "date": "2023-05"}
        ],
    }
)  # fmt: skip


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for t in TEMPLATES:
        # Spaced to use the whole page, as "fill the page" would.
        filled = fill_page(SAMPLE, Layout(), t.slug, SAMPLE, {}, StubProvider(), add_content=False)
        pdf = render_pdf(render_html(SAMPLE, t.slug, filled.layout))
        first = page_images(pdf.content)[0].image
        (OUT / f"{t.slug}.jpg").write_bytes(base64.b64decode(first.split(",", 1)[1]))
        print(f"{t.slug}: {pdf.pages} page(s) → {OUT / f'{t.slug}.jpg'}")


if __name__ == "__main__":
    main()
