"""The free ATS checker: public, no account. Upload a resume (and, if you like, paste a
job), see what an ATS reads from it. The file is kept 24 hours so that signing up can
turn it into the person's profile ("claim"), then deleted."""

import logging
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.ai_providers import AIProviderError, get_ai_provider
from app.auth import CurrentUser
from app.config import get_settings
from app.database import SessionDep
from app.models import AtsCheck, JobDescription, JobSource, SourceDocument, utcnow
from app.routers.uploads import MAX_BYTES
from app.services import rate_limit
from app.services.ats_check import analyse, keyword_coverage
from app.services.extract import DOCX, PDF, ExtractionError, sniff_type
from app.services.jobs import JobTextError, check_text, content_hash, find_existing, parse_job
from app.services.resume_import import run_parse
from app.services.storage import get_storage

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ats-check", tags=["ats-check"])

KEEP = timedelta(hours=24)
_SUFFIX = {PDF: ".pdf", DOCX: ".docx"}
_GONE = "This check has expired (we keep them 24 hours). Run it again."


class AtsOut(BaseModel):
    token: str
    report: dict


def purge_expired(session: Session) -> int:
    """Delete checks older than 24 hours, and their files. Returns how many."""
    old = session.exec(select(AtsCheck).where(AtsCheck.created_at < utcnow() - KEEP)).all()
    storage = get_storage()
    for check in old:
        try:
            storage.delete(check.storage_key)
        except Exception:
            log.exception("couldn't delete an expired ATS check's file")
        session.delete(check)
    if old:
        session.commit()
    return len(old)


@router.post("", status_code=status.HTTP_201_CREATED)
def run_check(
    request: Request,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
    job_text: Annotated[str, Form(max_length=40_000)] = "",
) -> AtsOut:
    """Check a resume file, and against a job if one is pasted. No account needed."""
    ip = rate_limit.client_ip(request)
    rate_limit.check(
        session,
        "ats_check",
        ip,
        get_settings().ats_checks_per_day,
        timedelta(days=1),
        "You've run a lot of checks today. Please try again tomorrow — or sign up free to "
        "keep working on your resume.",
    )
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "That file is over 5 MB.")
    mime = sniff_type(data)
    if mime is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Upload a PDF or a Word (.docx) file. Older .doc files: save as .docx first.",
        )
    filename = (file.filename or "resume")[:255]
    try:
        report = analyse(data, mime, filename)
    except ExtractionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None

    text, parsed = None, None
    if job_text.strip():
        try:
            text = check_text(job_text)
            parsed = parse_job(text, get_ai_provider())
        except JobTextError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
        except AIProviderError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None
        report["keywords"] = keyword_coverage(report["ats_text"], parsed)

    purge_expired(session)
    check = AtsCheck(
        id=secrets.token_urlsafe(24),
        filename=filename,
        mime=mime,
        storage_key=get_storage().put(data, suffix=_SUFFIX[mime]),
        report=report,
        job_text=text,
        parsed_job=parsed,
    )
    session.add(check)
    session.commit()
    rate_limit.record(session, "ats_check", ip)
    return AtsOut(token=check.id, report=report)


def _live(session: Session, token: str) -> AtsCheck:
    check = session.get(AtsCheck, token[:64])
    if check is None or check.created_at < utcnow() - KEEP:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _GONE)
    return check


@router.get("/{token}")
def get_check(token: str, session: SessionDep) -> AtsOut:
    """A check's report again (the result page, reloaded), while it's kept."""
    return AtsOut(token=token, report=_live(session, token).report)


class ClaimOut(BaseModel):
    upload_id: int
    job_id: int | None


@router.post("/{token}/claim")
def claim(
    token: str, user: CurrentUser, session: SessionDep, background: BackgroundTasks
) -> ClaimOut:
    """After signing up: the checked file becomes the person's upload (read into their
    profile as any upload is), and the pasted job one of their jobs. The check, and its
    copy of the file, are deleted."""
    check = _live(session, token)
    storage = get_storage()
    data = storage.get(check.storage_key)
    doc = SourceDocument(
        user_id=user.id,
        filename=check.filename,
        mime=check.mime,
        size_bytes=len(data),
        storage_key=storage.put(data, suffix=_SUFFIX[check.mime]),
    )
    session.add(doc)

    job_id = None
    if check.job_text and check.parsed_job:
        job = find_existing(session, user.id, check.job_text)
        if job is None:
            job = JobDescription(
                user_id=user.id,
                source=JobSource.PASTE,
                title=check.parsed_job["title"],
                company=check.parsed_job["company"],
                raw_text=check.job_text,
                content_hash=content_hash(check.job_text),
                parsed=check.parsed_job,
            )
            session.add(job)
    else:
        job = None

    old_key = check.storage_key
    session.delete(check)
    try:
        session.commit()
    except IntegrityError:  # claimed twice at once
        session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, _GONE) from None
    storage.delete(old_key)
    session.refresh(doc)
    if job is not None:
        session.refresh(job)
        job_id = job.id
    background.add_task(run_parse, doc.id)
    return ClaimOut(upload_id=doc.id, job_id=job_id)
