from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlmodel import Session, select

from app.ai_providers import AIProviderError, get_ai_provider
from app.auth import CurrentUser
from app.config import get_settings
from app.database import SessionDep
from app.models import Profile, SourceDocument, User, utcnow
from app.schemas.resume import Bullet, ResumeData, SkillGroup
from app.services import rate_limit
from app.services.draft import DraftError, draft_lines
from app.services.fit import FitError, SummaryLength, write_summary
from app.services.match import normalise
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


class AddSkillIn(BaseModel):
    skill: str = Field(min_length=1, max_length=80)
    # Where it was used: an experience or project id. Then `line` — written by the
    # person, never generated — says how, and goes into that entry.
    entry_id: str | None = None
    line: str | None = Field(default=None, max_length=2000)


class AddSkillOut(BaseModel):
    profile: ProfileOut
    # The line added to the profile, with its id, so the resume can include the same one.
    bullet: Bullet | None


@router.post("/skills")
def add_skill(body: AddSkillIn, user: CurrentUser, session: SessionDep) -> AddSkillOut:
    """ "I have this" for a skill a job asks for. The person says so, and says where;
    nothing is inferred. Saved into the profile, so every later resume knows it."""
    profile = session.exec(
        select(Profile).where(Profile.user_id == user.id).with_for_update()
    ).first()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no profile yet.")
    data = ResumeData.model_validate(profile.data)
    skill = body.skill.strip()

    bullet = None
    if body.entry_id:
        line = (body.line or "").strip()
        if len(line) < 10:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Write a line about how you used it there.",
            )
        entry = next((e for e in [*data.experience, *data.projects] if e.id == body.entry_id), None)
        if entry is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "That role or project isn't in your profile."
            )
        bullet = Bullet(text=line)
        entry.bullets.append(bullet)

    if normalise(skill) not in {normalise(s) for s in data.all_skills()}:
        group = next((g for g in data.skills if not g.group), None) or next(
            (g for g in data.skills if g.group.lower() == "other"), None
        )
        if group is None:
            group = SkillGroup(group="Other" if data.skills else "", items=[])
            data.skills.append(group)
        group.items.append(skill)

    profile.data = ResumeData.model_validate(data.model_dump()).model_dump(mode="json")
    profile.version += 1
    profile.updated_at = utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return AddSkillOut(profile=_out(session, profile), bullet=bullet)


# --- writing help, for building a profile from scratch ------------------------------


def _profile_ai_start(session: Session, user: User) -> ResumeData:
    """The profile as saved (the client saves first), after the daily cap check."""
    rate_limit.check(
        session,
        "profile_ai",
        str(user.id),
        get_settings().resume_ai_edits_per_day,
        timedelta(days=1),
        "You've used a lot of AI writing help today. Please try again tomorrow.",
    )
    profile = _find(session, user)
    return ResumeData.model_validate(profile.data) if profile else ResumeData()


class LinesIn(BaseModel):
    kind: Literal["project", "experience"]
    # What the entry is: "Project: Campus Connect", "Intern at Acme".
    context: str = Field(default="", max_length=300)
    notes: str = Field(max_length=3000)
    count: int = Field(default=3, ge=1, le=6)


class LeftOut(BaseModel):
    text: str
    reason: str


class LinesOut(BaseModel):
    lines: list[str]
    # Lines the model wrote that said more than the notes, and why they were dropped.
    left_out: list[LeftOut]


@router.post("/lines")
def write_lines(body: LinesIn, user: CurrentUser, session: SessionDep) -> LinesOut:
    """Resume lines from the person's own notes about a project or job. Not saved:
    the person reads them and adds the ones they want."""
    data = _profile_ai_start(session, user)
    try:
        lines, left_out = draft_lines(
            body.kind, body.context, body.notes, data, get_ai_provider(), body.count
        )
    except DraftError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None
    rate_limit.record(session, "profile_ai", str(user.id))
    return LinesOut(lines=lines, left_out=[LeftOut(**x) for x in left_out])


class ProfileSummaryIn(BaseModel):
    length: SummaryLength = "same"


class SummaryOut(BaseModel):
    text: str


@router.post("/summary")
def write_profile_summary(
    body: ProfileSummaryIn, user: CurrentUser, session: SessionDep
) -> SummaryOut:
    """A summary from the saved profile's own facts (not aimed at any one job). Not
    saved: the editor puts it in the summary field, where the person can change it."""
    data = _profile_ai_start(session, user)
    if not (data.experience or data.projects or data.education):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Add your education, projects or experience first — the summary is written from them.",
        )
    try:
        text = write_summary(data, {}, get_ai_provider(), body.length)
    except FitError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None
    rate_limit.record(session, "profile_ai", str(user.id))
    return SummaryOut(text=text)
