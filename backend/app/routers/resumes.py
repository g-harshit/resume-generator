from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlmodel import Session, func, select

from app.ai_providers import AIProviderError, get_ai_provider
from app.auth import CurrentUser
from app.config import get_settings
from app.database import SessionDep
from app.models import (
    JobDescription,
    Profile,
    Resume,
    ResumeRevision,
    RevisionReason,
    User,
    utcnow,
)
from app.rendering.catalog import BY_SLUG
from app.rendering.render import render_html, render_pdf
from app.routers.templates import PreviewOut, pdf_filename
from app.schemas.resume import ResumeData
from app.services.match import match_job
from app.services.tailor import tailor

router = APIRouter(prefix="/resumes", tags=["resumes"])


class TailorIn(BaseModel):
    job_id: int
    template: str = Field(max_length=40)


class ResumeSummary(BaseModel):
    id: int
    title: str
    template: str
    job_id: int | None
    created_at: datetime
    updated_at: datetime
    # How many of the job's skills this resume shows; null if the job is gone.
    covered: int | None
    total: int | None


class ResumeOut(ResumeSummary):
    content: ResumeData
    provenance: dict
    match: dict | None


def _own(session: Session, user: User, resume_id: int) -> Resume:
    resume = session.get(Resume, resume_id)
    if resume is None or resume.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")
    return resume


def _match(session: Session, resume: Resume) -> dict | None:
    job = (
        session.get(JobDescription, resume.job_description_id)
        if resume.job_description_id
        else None
    )
    return match_job(ResumeData.model_validate(resume.content), job.parsed) if job else None


def _summary(resume: Resume, match: dict | None) -> dict:
    return {
        "id": resume.id,
        "title": resume.title,
        "template": resume.template,
        "job_id": resume.job_description_id,
        "created_at": resume.created_at,
        "updated_at": resume.updated_at,
        "covered": match["covered"] if match else None,
        "total": match["total"] if match else None,
    }


def _out(session: Session, resume: Resume) -> ResumeOut:
    match = _match(session, resume)
    return ResumeOut(
        **_summary(resume, match),
        content=ResumeData.model_validate(resume.content),
        provenance=resume.provenance,
        match=match,
    )


def _title(job: JobDescription) -> str:
    return " — ".join(x for x in (job.title, job.company) if x) or "Untitled job"


@router.post("", status_code=status.HTTP_201_CREATED)
def create_resume(body: TailorIn, user: CurrentUser, session: SessionDep) -> ResumeOut:
    """Tailor the profile to a job. Waits for the model (usually 10-30 s)."""
    if body.template not in BY_SLUG:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No such template")
    job = session.get(JobDescription, body.job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if profile is None or profile.reviewed_at is None:
        # Everything in a resume comes from the profile, so it has to have been checked.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Review and confirm your profile first: every resume is built from it.",
        )

    since = utcnow() - timedelta(days=1)
    recent = session.exec(
        select(func.count())
        .select_from(Resume)
        .where(Resume.user_id == user.id, Resume.created_at > since)
    ).one()
    if recent >= get_settings().resumes_per_day:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "You've made a lot of resumes today. Please try again tomorrow.",
        )

    try:
        content, provenance = tailor(
            ResumeData.model_validate(profile.data), job.parsed, job.raw_text, get_ai_provider()
        )
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None

    data = content.model_dump(mode="json")
    resume = Resume(
        user_id=user.id,
        job_description_id=job.id,
        template=body.template,
        title=_title(job)[:300],
        content=data,
        provenance=provenance,
        profile_version=profile.version,
    )
    session.add(resume)
    session.flush()
    session.add(ResumeRevision(resume_id=resume.id, content=data, reason=RevisionReason.TAILOR))
    session.commit()
    session.refresh(resume)
    return _out(session, resume)


@router.get("")
def list_resumes(user: CurrentUser, session: SessionDep) -> list[ResumeSummary]:
    resumes = session.exec(
        select(Resume).where(Resume.user_id == user.id).order_by(Resume.updated_at.desc())
    ).all()
    return [ResumeSummary(**_summary(r, _match(session, r))) for r in resumes]


@router.get("/{resume_id}")
def get_resume(resume_id: int, user: CurrentUser, session: SessionDep) -> ResumeOut:
    return _out(session, _own(session, user, resume_id))


def _template(resume: Resume, override: str | None) -> str:
    slug = override or resume.template
    if slug not in BY_SLUG:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such template")
    return slug


@router.get("/{resume_id}/preview")
def preview(
    resume_id: int, user: CurrentUser, session: SessionDep, template: str | None = None
) -> PreviewOut:
    resume = _own(session, user, resume_id)
    html = render_html(ResumeData.model_validate(resume.content), _template(resume, template))
    return PreviewOut(html=html, pages=render_pdf(html).pages)


@router.get("/{resume_id}/pdf")
def pdf(
    resume_id: int, user: CurrentUser, session: SessionDep, template: str | None = None
) -> Response:
    resume = _own(session, user, resume_id)
    data = ResumeData.model_validate(resume.content)
    rendered = render_pdf(render_html(data, _template(resume, template)))
    return Response(
        rendered.content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{pdf_filename(data)}"',
            "X-Page-Count": str(rendered.pages),
            "Cache-Control": "private, no-store",
        },
    )
