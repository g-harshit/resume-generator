from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app.auth import CurrentUser
from app.config import get_settings
from app.database import SessionDep
from app.models import ParseStatus, Profile, SourceDocument, User, utcnow
from app.services.extract import DOCX, PDF, sniff_type
from app.services.resume_import import is_stale, notes_of, replace_profile, run_parse
from app.services.storage import get_storage

router = APIRouter(prefix="/uploads", tags=["uploads"])

MAX_BYTES = 5 * 1024 * 1024
_SUFFIX = {PDF: ".pdf", DOCX: ".docx"}
_TOOK_TOO_LONG = "Reading your resume took too long. Please upload it again."


class UploadOut(BaseModel):
    id: int
    filename: str
    status: str
    error: str | None
    # Notes from reading the file (see parse_resume.to_resume_data).
    notes: list[dict]
    # True when this upload is what the user's profile currently holds.
    applied: bool
    created_at: datetime


def _out(session: Session, doc: SourceDocument) -> UploadOut:
    profile = session.exec(select(Profile).where(Profile.user_id == doc.user_id)).first()
    stale = is_stale(doc)
    return UploadOut(
        id=doc.id,
        filename=doc.filename,
        status=ParseStatus.FAILED if stale else doc.parse_status,
        error=_TOOK_TOO_LONG if stale else doc.parse_error,
        notes=notes_of(doc),
        applied=profile is not None and profile.source_document_id == doc.id,
        created_at=doc.created_at,
    )


def _own(session: Session, user: User, document_id: int) -> SourceDocument:
    doc = session.get(SourceDocument, document_id)
    if doc is None or doc.user_id != user.id:  # someone else's is "not found", not "forbidden"
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload not found")
    return doc


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def upload(
    user: CurrentUser,
    session: SessionDep,
    background: BackgroundTasks,
    file: Annotated[UploadFile, File()],
) -> UploadOut:
    # A plain `def` (run in a thread): the DB calls below block, so no `async`.
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "That file is over 5 MB.")
    mime = sniff_type(data)
    if mime is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Upload a PDF or a Word (.docx) file. Older .doc files: save as .docx first.",
        )

    since = utcnow() - timedelta(days=1)
    recent = session.exec(
        select(func.count())
        .select_from(SourceDocument)
        .where(SourceDocument.user_id == user.id, SourceDocument.created_at > since)
    ).one()
    if recent >= get_settings().uploads_per_day:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "You've uploaded a lot of files today. Please try again tomorrow.",
        )

    doc = SourceDocument(
        user_id=user.id,
        filename=(file.filename or "resume")[:255],
        mime=mime,
        size_bytes=len(data),
        storage_key=get_storage().put(data, suffix=_SUFFIX[mime]),
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    background.add_task(run_parse, doc.id)
    return _out(session, doc)


@router.get("/{document_id}")
def get_upload(document_id: int, user: CurrentUser, session: SessionDep) -> UploadOut:
    return _out(session, _own(session, user, document_id))


@router.get("/{document_id}/file")
def get_file(document_id: int, user: CurrentUser, session: SessionDep) -> Response:
    """The original file, for showing beside the parsed profile."""
    doc = _own(session, user, document_id)
    return Response(
        get_storage().get(doc.storage_key),
        media_type=doc.mime,
        headers={"Content-Disposition": "inline", "Cache-Control": "private, no-store"},
    )


class TextOut(BaseModel):
    text: str


@router.get("/{document_id}/text")
def get_text(document_id: int, user: CurrentUser, session: SessionDep) -> TextOut:
    """The text we read from the file: what a Word upload is shown as (browsers can't
    display .docx), and useful beside any parse."""
    doc = _own(session, user, document_id)
    return TextOut(text=doc.extracted_text or "")


@router.post("/{document_id}/apply")
def apply(document_id: int, user: CurrentUser, session: SessionDep) -> UploadOut:
    """Replace the profile with this upload, even a reviewed one: the user asked."""
    doc = _own(session, user, document_id)
    if doc.parse_status != ParseStatus.DONE:
        raise HTTPException(status.HTTP_409_CONFLICT, "This upload hasn't been read yet.")
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    replace_profile(session, doc, profile)
    session.commit()
    return _out(session, doc)
