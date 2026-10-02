import re

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import CurrentUser
from app.database import SessionDep
from app.models import Profile, User
from app.rendering.catalog import BY_SLUG, TEMPLATES
from app.rendering.render import page_images, render_html, render_pdf
from app.schemas.resume import ResumeData

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplateOut(BaseModel):
    slug: str
    name: str
    description: str


class PageLink(BaseModel):
    x: float
    y: float
    w: float
    h: float
    url: str


class PreviewOut(BaseModel):
    html: str
    # From the real PDF layout, so "2 pages" in the picker is what the download will be.
    pages: int
    # Every page of that PDF as an image, so the preview shows page 2 where it starts,
    # with each page's links (positions as fractions of the page) to click on it.
    images: list[str]
    links: list[list[PageLink]]


def preview_of(html: str) -> PreviewOut:
    rendered = render_pdf(html)
    views = page_images(rendered.content)
    return PreviewOut(
        html=html,
        pages=rendered.pages,
        images=[v.image for v in views],
        links=[[PageLink(**link) for link in v.links] for v in views],
    )


@router.get("")
def list_templates() -> list[TemplateOut]:
    return [TemplateOut(slug=t.slug, name=t.name, description=t.description) for t in TEMPLATES]


def _profile_data(session: Session, user: User) -> ResumeData:
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if profile is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Upload your resume first, so there's something to show."
        )
    return ResumeData.model_validate(profile.data)


def _known(slug: str) -> str:
    if slug not in BY_SLUG:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such template")
    return slug


def pdf_filename(data: ResumeData) -> str:
    name = re.sub(r"[^A-Za-z0-9]+", "-", data.basics.name).strip("-") or "Resume"
    return f"{name}-Resume.pdf"


@router.get("/{slug}/preview")
def preview(slug: str, user: CurrentUser, session: SessionDep) -> PreviewOut:
    """The user's profile in this template, as HTML for the picker's live preview."""
    return preview_of(render_html(_profile_data(session, user), _known(slug)))


@router.get("/{slug}/pdf")
def pdf(slug: str, user: CurrentUser, session: SessionDep) -> Response:
    """The user's profile in this template, as a PDF to download."""
    data = _profile_data(session, user)
    rendered = render_pdf(render_html(data, _known(slug)))
    return Response(
        rendered.content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{pdf_filename(data)}"',
            "X-Page-Count": str(rendered.pages),
            "Cache-Control": "private, no-store",
        },
    )
