from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import update
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
from app.rendering.render import render_html, render_letter_html, render_pdf
from app.routers.templates import PreviewOut, pdf_filename
from app.schemas.resume import ResumeData
from app.services import rate_limit
from app.services.cover_letter import write_cover_letter
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
    version: int
    job_id: int | None
    # About the job it was made for; empty / null if the job is gone.
    company: str
    job_title: str
    source: str | None  # "paste" | "extension"
    created_at: datetime
    updated_at: datetime
    # How many of the job's skills this resume shows; null if the job is gone.
    covered: int | None
    total: int | None


class ResumeOut(ResumeSummary):
    content: ResumeData
    provenance: dict
    match: dict | None
    cover_letter: dict | None


def _own(session: Session, user: User, resume_id: int) -> Resume:
    resume = session.get(Resume, resume_id)
    if resume is None or resume.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")
    return resume


def _job(session: Session, resume: Resume) -> JobDescription | None:
    if resume.job_description_id is None:
        return None
    return session.get(JobDescription, resume.job_description_id)


def _match(session: Session, resume: Resume) -> dict | None:
    job = _job(session, resume)
    return match_job(ResumeData.model_validate(resume.content), job.parsed) if job else None


def _summary(session: Session, resume: Resume, match: dict | None) -> dict:
    job = _job(session, resume)
    return {
        "id": resume.id,
        "title": resume.title,
        "template": resume.template,
        "version": resume.version,
        "job_id": resume.job_description_id,
        "company": job.company if job else "",
        "job_title": job.title if job else "",
        "source": job.source if job else None,
        "created_at": resume.created_at,
        "updated_at": resume.updated_at,
        "covered": match["covered"] if match else None,
        "total": match["total"] if match else None,
    }


def _out(session: Session, resume: Resume) -> ResumeOut:
    match = _match(session, resume)
    return ResumeOut(
        **_summary(session, resume, match),
        content=ResumeData.model_validate(resume.content),
        provenance=resume.provenance,
        match=match,
        cover_letter=resume.cover_letter,
    )


def _title(job: JobDescription) -> str:
    return " — ".join(x for x in (job.title, job.company) if x) or "Untitled job"


def _reviewed_profile(session: Session, user: User) -> Profile:
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if profile is None or profile.reviewed_at is None:
        # Everything in a resume comes from the profile, so it has to have been checked.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Review and confirm your profile first: every resume is built from it.",
        )
    return profile


def _check_daily_cap(session: Session, user: User) -> None:
    """Tailoring runs (new resumes and re-tailors) per day: each is several model calls."""
    since = utcnow() - timedelta(days=1)
    runs = session.exec(
        select(func.count())
        .select_from(ResumeRevision)
        .join(Resume, Resume.id == ResumeRevision.resume_id)
        .where(
            Resume.user_id == user.id,
            ResumeRevision.created_at > since,
            ResumeRevision.reason.in_([RevisionReason.TAILOR, RevisionReason.RETAILOR]),
        )
    ).one()
    if runs >= get_settings().resumes_per_day:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "You've tailored a lot of resumes today. Please try again tomorrow.",
        )


def _tailor(profile: Profile, job: JobDescription) -> tuple[ResumeData, dict]:
    try:
        return tailor(
            ResumeData.model_validate(profile.data), job.parsed, job.raw_text, get_ai_provider()
        )
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None


@router.post("", status_code=status.HTTP_201_CREATED)
def create_resume(body: TailorIn, user: CurrentUser, session: SessionDep) -> ResumeOut:
    """Tailor the profile to a job. Waits for the model (usually 10-30 s)."""
    if body.template not in BY_SLUG:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No such template")
    job = session.get(JobDescription, body.job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    profile = _reviewed_profile(session, user)
    _check_daily_cap(session, user)
    content, provenance = _tailor(profile, job)

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
    return [ResumeSummary(**_summary(session, r, _match(session, r))) for r in resumes]


@router.get("/{resume_id}")
def get_resume(resume_id: int, user: CurrentUser, session: SessionDep) -> ResumeOut:
    return _out(session, _own(session, user, resume_id))


class SaveIn(BaseModel):
    # The version the editor last loaded; a stale one gets 409, as for profiles.
    version: int
    content: ResumeData
    template: str = Field(max_length=40)


# Autosave fires every few seconds while someone types. Saves within this long of the
# last "edit" revision update it rather than adding one, so the history stays useful.
EDIT_REVISION_WINDOW = timedelta(minutes=10)


def _conflict() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        "This resume was changed somewhere else (another tab?). Reload to see the latest.",
    )


@router.put("/{resume_id}")
def save_resume(resume_id: int, body: SaveIn, user: CurrentUser, session: SessionDep) -> ResumeOut:
    """The person's own edits. Unlike tailoring, nothing here is checked against the
    profile: it's their resume and their words."""
    resume = _own(session, user, resume_id)
    if body.template not in BY_SLUG:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No such template")
    data = body.content.model_dump(mode="json")
    now = utcnow()
    result = session.exec(
        update(Resume)
        .where(Resume.id == resume.id, Resume.version == body.version)
        .values(content=data, template=body.template, version=Resume.version + 1, updated_at=now)
    )
    if result.rowcount != 1:
        session.rollback()
        raise _conflict()

    latest = session.exec(
        select(ResumeRevision)
        .where(ResumeRevision.resume_id == resume.id)
        .order_by(ResumeRevision.created_at.desc())
    ).first()
    if (
        latest is not None
        and latest.reason == RevisionReason.EDIT
        and now - latest.created_at < EDIT_REVISION_WINDOW
    ):
        latest.content = data
        session.add(latest)
    else:
        session.add(ResumeRevision(resume_id=resume.id, content=data, reason=RevisionReason.EDIT))
    session.commit()
    session.refresh(resume)
    return _out(session, resume)


@router.post("/{resume_id}/retailor")
def retailor(resume_id: int, user: CurrentUser, session: SessionDep) -> ResumeOut:
    """Tailor again from the profile as it is now (say, after adding a skill). The
    edits made to this resume are replaced; the previous version stays in its history."""
    resume = _own(session, user, resume_id)
    job = _job(session, resume)
    if job is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "The job this resume was made for is gone.")
    profile = _reviewed_profile(session, user)
    _check_daily_cap(session, user)
    started_at_version = resume.version
    content, provenance = _tailor(profile, job)  # 20-40 s; the editor may save meanwhile

    data = content.model_dump(mode="json")
    result = session.exec(
        update(Resume)
        .where(Resume.id == resume.id, Resume.version == started_at_version)
        .values(
            content=data,
            provenance=provenance,
            profile_version=profile.version,
            version=Resume.version + 1,
            updated_at=utcnow(),
        )
    )
    if result.rowcount != 1:  # edited while tailoring: don't throw those edits away
        session.rollback()
        raise _conflict()
    session.add(ResumeRevision(resume_id=resume.id, content=data, reason=RevisionReason.RETAILOR))
    session.commit()
    session.refresh(resume)
    return _out(session, resume)


@router.post("/{resume_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate(resume_id: int, user: CurrentUser, session: SessionDep) -> ResumeOut:
    """A copy to try something different on. No model call, so not part of the cap."""
    source = _own(session, user, resume_id)
    copy = Resume(
        user_id=user.id,
        job_description_id=source.job_description_id,
        template=source.template,
        title=f"{source.title} (copy)"[:300],
        content=source.content,
        provenance=source.provenance,
        profile_version=source.profile_version,
    )
    session.add(copy)
    session.flush()
    session.add(ResumeRevision(resume_id=copy.id, content=copy.content, reason=RevisionReason.COPY))
    session.commit()
    session.refresh(copy)
    return _out(session, copy)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: int, user: CurrentUser, session: SessionDep) -> Response:
    """Deletes the resume and its history. The job it was made for stays."""
    session.delete(_own(session, user, resume_id))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- cover letter ------------------------------------------------------------------


@router.post("/{resume_id}/cover-letter")
def write_letter(resume_id: int, user: CurrentUser, session: SessionDep) -> ResumeOut:
    """Write (or rewrite) the cover letter for this resume's job, from this resume.
    Waits for the model, usually 15-30 s."""
    resume = _own(session, user, resume_id)
    job = _job(session, resume)
    if job is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "The job this resume was made for is gone.")
    rate_limit.check(
        session,
        "cover_letter",
        str(user.id),
        get_settings().cover_letters_per_day,
        timedelta(days=1),
        "You've written a lot of cover letters today. Please try again tomorrow.",
    )
    try:
        letter = write_cover_letter(
            ResumeData.model_validate(resume.content), job.parsed, job.raw_text, get_ai_provider()
        )
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None
    rate_limit.record(session, "cover_letter", str(user.id))
    resume.cover_letter = {**letter, "generated_at": utcnow().isoformat()}
    resume.updated_at = utcnow()
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return _out(session, resume)


class LetterIn(BaseModel):
    text: str = Field(max_length=10_000)


@router.put("/{resume_id}/cover-letter")
def save_letter(
    resume_id: int, body: LetterIn, user: CurrentUser, session: SessionDep
) -> ResumeOut:
    """The person's own edits to the letter: theirs, so not checked."""
    resume = _own(session, user, resume_id)
    if resume.cover_letter is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no cover letter yet.")
    resume.cover_letter = {**resume.cover_letter, "text": body.text}
    resume.updated_at = utcnow()
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return _out(session, resume)


@router.get("/{resume_id}/cover-letter/pdf")
def letter_pdf(
    resume_id: int, user: CurrentUser, session: SessionDep, template: str | None = None
) -> Response:
    resume = _own(session, user, resume_id)
    if not resume.cover_letter:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no cover letter yet.")
    data = ResumeData.model_validate(resume.content)
    job = _job(session, resume)
    html = render_letter_html(
        data, resume.cover_letter["text"], job.company if job else "", _template(resume, template)
    )
    rendered = render_pdf(html)
    filename = pdf_filename(data).replace("-Resume.pdf", "-Cover-Letter.pdf")
    return Response(
        rendered.content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


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
