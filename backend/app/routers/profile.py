from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import update
from sqlmodel import Session, select

from app.auth import CurrentUser
from app.database import SessionDep
from app.models import Profile, SourceDocument, User, utcnow
from app.schemas.resume import ResumeData
from app.services.profile_checks import blocking, profile_checks
from app.services.resume_import import notes_of

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileOut(BaseModel):
    data: ResumeData
    version: int
    reviewed_at: datetime | None
    source_document_id: int | None
    # "application/pdf" can be shown as-is; a Word file is shown as the text we read.
    source_mime: str | None
    updated_at: datetime
    # What's missing now; recomputed on every read and save.
    checks: list[dict]
    # What we noticed reading the file. Only until the profile is confirmed.
    notes: list[dict]


class SaveIn(BaseModel):
    # The version the client last loaded; 0 to create a profile from scratch.
    version: int
    data: ResumeData


class ConfirmIn(BaseModel):
    version: int


def _find(session: Session, user: User) -> Profile | None:
    return session.exec(select(Profile).where(Profile.user_id == user.id)).first()


def _out(session: Session, profile: Profile) -> ProfileOut:
    data = ResumeData.model_validate(profile.data)
    doc = (
        session.get(SourceDocument, profile.source_document_id)
        if profile.source_document_id
        else None
    )
    return ProfileOut(
        data=data,
        version=profile.version,
        reviewed_at=profile.reviewed_at,
        source_document_id=profile.source_document_id,
        source_mime=doc.mime if doc else None,
        updated_at=profile.updated_at,
        checks=profile_checks(data),
        notes=notes_of(doc) if profile.reviewed_at is None else [],
    )


def _conflict() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        "Your profile was changed somewhere else (another tab?). Reload to see the latest.",
    )


@router.get("")
def get_profile(user: CurrentUser, session: SessionDep) -> ProfileOut | None:
    """The user's profile, or null before they have one."""
    profile = _find(session, user)
    return _out(session, profile) if profile else None


@router.put("")
def save_profile(body: SaveIn, user: CurrentUser, session: SessionDep) -> ProfileOut:
    data = body.data.model_dump(mode="json")
    profile = _find(session, user)

    if profile is None:
        if body.version != 0:
            raise _conflict()
        profile = Profile(user_id=user.id, data=data)
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return _out(session, profile)

    # Compare-and-set in one statement: two tabs saving at once can't both win and
    # silently drop the other's edits.
    result = session.exec(
        update(Profile)
        .where(Profile.id == profile.id, Profile.version == body.version)
        .values(data=data, version=Profile.version + 1, updated_at=utcnow())
    )
    if result.rowcount != 1:
        session.rollback()
        raise _conflict()
    session.commit()
    session.refresh(profile)
    return _out(session, profile)


@router.post("/confirm")
def confirm_profile(body: ConfirmIn, user: CurrentUser, session: SessionDep) -> ProfileOut:
    """The user has checked what we read. Resumes are only tailored from a confirmed
    profile, and a later upload won't silently replace it."""
    profile = _find(session, user)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no profile to confirm yet.")
    if profile.version != body.version:
        raise _conflict()
    problems = blocking(profile_checks(ResumeData.model_validate(profile.data)))
    if problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problems[0]["message"])
    profile.reviewed_at = utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return _out(session, profile)
