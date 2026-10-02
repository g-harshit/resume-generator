from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app.ai_providers import AIProviderError, get_ai_provider
from app.auth import CurrentUser
from app.config import get_settings
from app.database import SessionDep
from app.models import JobDescription, JobSource, Profile, User, utcnow
from app.schemas.resume import ResumeData
from app.services.jobs import JobTextError, check_text, content_hash, find_existing, parse_job
from app.services.match import match_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobIn(BaseModel):
    text: str = Field(max_length=60_000)
    url: str = Field(default="", max_length=2000)
    source: str = Field(default=JobSource.PASTE, pattern="^(paste|extension)$")


class JobOut(BaseModel):
    id: int
    source: str
    url: str
    title: str
    company: str
    location: str
    seniority: str
    created_at: datetime
    # What the job asks for vs the profile *now*: recomputed on every read, so it
    # moves as soon as the user adds a skill. Null before they have a profile.
    match: dict | None


def _match(session: Session, user: User, job: JobDescription) -> dict | None:
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if profile is None:
        return None
    return match_job(ResumeData.model_validate(profile.data), job.parsed)


def _out(session: Session, user: User, job: JobDescription) -> JobOut:
    p = job.parsed
    return JobOut(
        id=job.id,
        source=job.source,
        url=job.url,
        title=job.title,
        company=job.company,
        location=p.get("location", ""),
        seniority=p.get("seniority", ""),
        created_at=job.created_at,
        match=_match(session, user, job),
    )


@router.post("")
def add_job(body: JobIn, user: CurrentUser, session: SessionDep) -> JobOut:
    """Read a job description. Waits for the model (a few seconds) rather than running
    in the background: the page and the extension both want the answer at once.
    The same posting twice returns the first reading, without another model call."""
    try:
        text = check_text(body.text)
    except JobTextError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None

    existing = find_existing(session, user.id, text)
    if existing:
        return _out(session, user, existing)

    since = utcnow() - timedelta(days=1)
    recent = session.exec(
        select(func.count())
        .select_from(JobDescription)
        .where(JobDescription.user_id == user.id, JobDescription.created_at > since)
    ).one()
    if recent >= get_settings().jobs_per_day:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "You've added a lot of job descriptions today. Please try again tomorrow.",
        )

    try:
        parsed = parse_job(text, get_ai_provider())
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None

    job = JobDescription(
        user_id=user.id,
        source=body.source,
        url=body.url.strip(),
        title=parsed["title"],
        company=parsed["company"],
        raw_text=text,
        content_hash=content_hash(text),
        parsed=parsed,
    )
    session.add(job)
    try:
        session.commit()
    except IntegrityError:  # the same posting, sent twice at once
        session.rollback()
        return _out(session, user, find_existing(session, user.id, text))
    session.refresh(job)
    return _out(session, user, job)


@router.get("/{job_id}")
def get_job(job_id: int, user: CurrentUser, session: SessionDep) -> JobOut:
    job = session.get(JobDescription, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return _out(session, user, job)
