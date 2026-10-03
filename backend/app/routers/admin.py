"""The admin panel: who's using the app, how much, and account actions.

Admins are the `ADMIN_EMAILS` whose address is verified (see `app.auth.is_admin`).
Everyone else gets 404 from every route here. Admins see accounts and activity,
not the text of anyone's resume. Every action is written to `admin_actions`.
"""

import csv
import io
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import Date, cast, func, or_
from sqlmodel import Session, select

from app.auth import AdminUser
from app.database import SessionDep
from app.models import (
    AdminAction,
    JobDescription,
    ParseStatus,
    Profile,
    Resume,
    SourceDocument,
    User,
    utcnow,
)
from app.services.storage import get_storage

log = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _log(session: Session, admin: User, action: str, target: User | None, **detail) -> None:
    session.add(
        AdminAction(
            admin_email=admin.email,
            action=action,
            target_user_id=target.id if target else None,
            target_email=target.email if target else "",
            detail=detail or None,
        )
    )


def _count(session: Session, statement) -> int:
    return session.exec(statement).one()


# --- overview --------------------------------------------------------------------------


class DayCount(BaseModel):
    day: str
    count: int


class StatsOut(BaseModel):
    users: int
    users_today: int
    users_7d: int
    users_30d: int
    active_7d: int
    google_users: int
    password_users: int
    disabled_users: int
    profiles: int
    profiles_confirmed: int
    resumes: int
    resumes_7d: int
    cover_letters: int
    jobs: int
    jobs_from_extension: int
    uploads: int
    uploads_failed: int
    signups_by_day: list[DayCount]


@router.get("/stats")
def stats(admin: AdminUser, session: SessionDep) -> StatsOut:
    now = utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    users = select(func.count()).select_from(User)
    since = now - timedelta(days=30)
    by_day = session.exec(
        select(cast(User.created_at, Date), func.count())
        .where(User.created_at >= since)
        .group_by(cast(User.created_at, Date))
        .order_by(cast(User.created_at, Date))
    ).all()
    counts = {d.isoformat(): n for d, n in by_day}
    days = [(since + timedelta(days=i + 1)).date().isoformat() for i in range(30)]
    resumes = select(func.count()).select_from(Resume)
    uploads = select(func.count()).select_from(SourceDocument)
    jobs = select(func.count()).select_from(JobDescription)
    return StatsOut(
        users=_count(session, users),
        users_today=_count(session, users.where(User.created_at >= today)),
        users_7d=_count(session, users.where(User.created_at >= now - timedelta(days=7))),
        users_30d=_count(session, users.where(User.created_at >= since)),
        active_7d=_count(session, users.where(User.last_seen_at >= now - timedelta(days=7))),
        google_users=_count(session, users.where(User.google_sub.is_not(None))),
        password_users=_count(session, users.where(User.password_hash.is_not(None))),
        disabled_users=_count(session, users.where(User.disabled_at.is_not(None))),
        profiles=_count(session, select(func.count()).select_from(Profile)),
        profiles_confirmed=_count(
            session,
            select(func.count()).select_from(Profile).where(Profile.reviewed_at.is_not(None)),
        ),
        resumes=_count(session, resumes),
        resumes_7d=_count(session, resumes.where(Resume.created_at >= now - timedelta(days=7))),
        cover_letters=_count(session, resumes.where(Resume.cover_letter.is_not(None))),
        jobs=_count(session, jobs),
        jobs_from_extension=_count(session, jobs.where(JobDescription.source == "extension")),
        uploads=_count(session, uploads),
        uploads_failed=_count(
            session, uploads.where(SourceDocument.parse_status == ParseStatus.FAILED)
        ),
        signups_by_day=[DayCount(day=d, count=counts.get(d, 0)) for d in days],
    )


# --- users -----------------------------------------------------------------------------


class UserRow(BaseModel):
    id: int
    email: str
    name: str
    sign_in: list[str]  # "google", "password"
    email_verified: bool
    created_at: datetime
    last_seen_at: datetime | None
    disabled: bool
    profile: str  # "none", "draft", "confirmed"
    resumes: int
    jobs: int
    uploads: int


class UsersPage(BaseModel):
    total: int
    users: list[UserRow]


def _counts(model, user_ids: list[int], session: Session) -> dict[int, int]:
    if not user_ids:
        return {}
    rows = session.exec(
        select(model.user_id, func.count())
        .where(model.user_id.in_(user_ids))
        .group_by(model.user_id)
    ).all()
    return dict(rows)


def _rows(users: list[User], session: Session) -> list[UserRow]:
    ids = [u.id for u in users]
    resumes = _counts(Resume, ids, session)
    jobs = _counts(JobDescription, ids, session)
    uploads = _counts(SourceDocument, ids, session)
    profiles = (
        dict(
            session.exec(
                select(Profile.user_id, Profile.reviewed_at).where(Profile.user_id.in_(ids))
            ).all()
        )
        if ids
        else {}
    )
    return [
        UserRow(
            id=u.id,
            email=u.email,
            name=u.name,
            sign_in=[
                m for m, on in (("google", u.google_sub), ("password", u.password_hash)) if on
            ],
            email_verified=u.email_verified_at is not None,
            created_at=u.created_at,
            last_seen_at=u.last_seen_at,
            disabled=u.disabled_at is not None,
            profile=(
                "none"
                if u.id not in profiles
                else "confirmed"
                if profiles[u.id] is not None
                else "draft"
            ),
            resumes=resumes.get(u.id, 0),
            jobs=jobs.get(u.id, 0),
            uploads=uploads.get(u.id, 0),
        )
        for u in users
    ]


def _search(q: str):
    query = select(User)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.where(
            or_(func.lower(User.email).like(like), func.lower(User.name).like(like))
        )
    return query


@router.get("/users")
def list_users(
    admin: AdminUser, session: SessionDep, q: str = "", offset: int = 0, limit: int = 50
) -> UsersPage:
    limit = max(1, min(limit, 200))
    query = _search(q)
    total = _count(session, select(func.count()).select_from(query.subquery()))
    users = session.exec(
        query.order_by(User.created_at.desc()).offset(max(0, offset)).limit(limit)
    ).all()
    return UsersPage(total=total, users=_rows(list(users), session))


@router.get("/users.csv")
def export_users(admin: AdminUser, session: SessionDep, q: str = "") -> Response:
    users = session.exec(_search(q).order_by(User.created_at.desc())).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "id",
            "email",
            "name",
            "sign_in",
            "email_verified",
            "joined",
            "last_seen",
            "disabled",
            "profile",
            "resumes",
            "jobs",
            "uploads",
        ]
    )
    for r in _rows(list(users), session):
        writer.writerow(
            [
                r.id,
                r.email,
                r.name,
                "+".join(r.sign_in),
                r.email_verified,
                r.created_at.isoformat(),
                r.last_seen_at.isoformat() if r.last_seen_at else "",
                r.disabled,
                r.profile,
                r.resumes,
                r.jobs,
                r.uploads,
            ]
        )
    _log(session, admin, "export_users", None, count=len(users), query=q)
    session.commit()
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="users.csv"',
            "Cache-Control": "private, no-store",
        },
    )


class ResumeItem(BaseModel):
    id: int
    title: str
    template: str
    has_cover_letter: bool
    created_at: datetime
    updated_at: datetime


class JobItem(BaseModel):
    id: int
    title: str
    company: str
    source: str
    created_at: datetime


class UploadItem(BaseModel):
    id: int
    filename: str
    size_bytes: int
    status: str
    error: str | None
    created_at: datetime


class ActionItem(BaseModel):
    admin_email: str
    action: str
    target_email: str
    detail: dict | None
    created_at: datetime


class UserDetail(BaseModel):
    user: UserRow
    is_admin: bool
    profile_updated_at: datetime | None
    profile_sections: dict[str, int]  # how many roles, projects…; not their content
    resumes: list[ResumeItem]
    jobs: list[JobItem]
    uploads: list[UploadItem]
    actions: list[ActionItem]


def _target(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such user")
    return user


@router.get("/users/{user_id}")
def user_detail(user_id: int, admin: AdminUser, session: SessionDep) -> UserDetail:
    from app.auth import is_admin

    user = _target(session, user_id)
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    data = profile.data if profile else {}
    sections = {
        k: len(data.get(k) or [])
        for k in ("experience", "education", "projects", "certifications", "skills")
    }
    resumes = session.exec(
        select(Resume).where(Resume.user_id == user.id).order_by(Resume.created_at.desc())
    ).all()
    jobs = session.exec(
        select(JobDescription)
        .where(JobDescription.user_id == user.id)
        .order_by(JobDescription.created_at.desc())
    ).all()
    uploads = session.exec(
        select(SourceDocument)
        .where(SourceDocument.user_id == user.id)
        .order_by(SourceDocument.created_at.desc())
    ).all()
    actions = session.exec(
        select(AdminAction)
        .where(AdminAction.target_user_id == user.id)
        .order_by(AdminAction.created_at.desc())
        .limit(50)
    ).all()
    return UserDetail(
        user=_rows([user], session)[0],
        is_admin=is_admin(user),
        profile_updated_at=profile.updated_at if profile else None,
        profile_sections=sections,
        resumes=[
            ResumeItem(
                id=r.id,
                title=r.title,
                template=r.template,
                has_cover_letter=r.cover_letter is not None,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in resumes
        ],
        jobs=[
            JobItem(
                id=j.id, title=j.title, company=j.company, source=j.source, created_at=j.created_at
            )
            for j in jobs
        ],
        uploads=[
            UploadItem(
                id=d.id,
                filename=d.filename,
                size_bytes=d.size_bytes,
                status=d.parse_status,
                error=d.parse_error,
                created_at=d.created_at,
            )
            for d in uploads
        ],
        actions=[ActionItem(**a.model_dump(include=set(ActionItem.model_fields))) for a in actions],
    )


# --- actions ---------------------------------------------------------------------------


def _not_self(admin: User, user: User, what: str) -> None:
    if admin.id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"You can't {what} your own account here.")


@router.post("/users/{user_id}/sign-out")
def sign_out_everywhere(user_id: int, admin: AdminUser, session: SessionDep) -> UserDetail:
    user = _target(session, user_id)
    user.token_version += 1
    session.add(user)
    _log(session, admin, "sign_out", user)
    session.commit()
    return user_detail(user_id, admin, session)


@router.post("/users/{user_id}/disable")
def disable(user_id: int, admin: AdminUser, session: SessionDep) -> UserDetail:
    user = _target(session, user_id)
    _not_self(admin, user, "disable")
    if user.disabled_at is None:
        user.disabled_at = utcnow()
        user.token_version += 1  # and out of every session now
        session.add(user)
        _log(session, admin, "disable", user)
        session.commit()
    return user_detail(user_id, admin, session)


@router.post("/users/{user_id}/enable")
def enable(user_id: int, admin: AdminUser, session: SessionDep) -> UserDetail:
    user = _target(session, user_id)
    if user.disabled_at is not None:
        user.disabled_at = None
        session.add(user)
        _log(session, admin, "enable", user)
        session.commit()
    return user_detail(user_id, admin, session)


class DeleteIn(BaseModel):
    # Typed by the admin, to be sure they mean this account.
    confirm_email: str


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, body: DeleteIn, admin: AdminUser, session: SessionDep) -> Response:
    """The account and everything in it: rows go by ON DELETE CASCADE, uploaded files
    are removed from storage. Can't be undone."""
    user = _target(session, user_id)
    _not_self(admin, user, "delete")
    if body.confirm_email.strip().lower() != user.email:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Type the account's email address exactly to confirm."
        )
    keys = session.exec(
        select(SourceDocument.storage_key).where(SourceDocument.user_id == user.id)
    ).all()
    counts = {
        "resumes": _count(
            session, select(func.count()).select_from(Resume).where(Resume.user_id == user.id)
        ),
        "uploads": len(keys),
    }
    _log(session, admin, "delete", user, **counts)
    session.delete(user)
    session.commit()
    storage = get_storage()
    for key in keys:  # after the commit: a file left behind is better than a row
        try:
            storage.delete(key)
        except Exception:
            # The account is already gone; the file is orphaned, not exposed (private
            # bucket, random name). Logged so it can be cleaned up.
            log.warning("couldn't delete stored file %s of deleted user %s", key, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- health ----------------------------------------------------------------------------


class FailedUpload(BaseModel):
    id: int
    user_id: int
    user_email: str
    filename: str
    error: str | None
    created_at: datetime


@router.get("/uploads/failed")
def failed_uploads(admin: AdminUser, session: SessionDep, limit: int = 50) -> list[FailedUpload]:
    rows = session.exec(
        select(SourceDocument, User.email)
        .join(User, User.id == SourceDocument.user_id)
        .where(SourceDocument.parse_status == ParseStatus.FAILED)
        .order_by(SourceDocument.created_at.desc())
        .limit(max(1, min(limit, 200)))
    ).all()
    return [
        FailedUpload(
            id=d.id,
            user_id=d.user_id,
            user_email=email,
            filename=d.filename,
            error=d.parse_error,
            created_at=d.created_at,
        )
        for d, email in rows
    ]


@router.get("/log")
def action_log(admin: AdminUser, session: SessionDep, limit: int = 100) -> list[ActionItem]:
    actions = session.exec(
        select(AdminAction).order_by(AdminAction.created_at.desc()).limit(max(1, min(limit, 500)))
    ).all()
    return [ActionItem(**a.model_dump(include=set(ActionItem.model_fields))) for a in actions]
