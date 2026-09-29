from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import select

from app.auth import CurrentUser
from app.database import SessionDep
from app.models import Profile
from app.schemas.resume import ResumeData

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileOut(BaseModel):
    data: ResumeData
    version: int
    reviewed_at: datetime | None
    source_document_id: int | None
    updated_at: datetime


@router.get("")
def get_profile(user: CurrentUser, session: SessionDep) -> ProfileOut | None:
    """The user's profile, or null before their first upload has been read."""
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if profile is None:
        return None
    return ProfileOut(
        data=ResumeData.model_validate(profile.data),
        version=profile.version,
        reviewed_at=profile.reviewed_at,
        source_document_id=profile.source_document_id,
        updated_at=profile.updated_at,
    )
