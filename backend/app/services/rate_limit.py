"""Counting attempts, to slow down password guessing and sign-up floods."""

from datetime import timedelta

from fastapi import HTTPException, Request, status
from sqlmodel import Session, delete, func, select

from app.config import get_settings
from app.models import AuthAttempt, utcnow


def client_ip(request: Request) -> str:
    if get_settings().trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def count(session: Session, kind: str, key: str, within: timedelta) -> int:
    since = utcnow() - within
    return session.exec(
        select(func.count())
        .select_from(AuthAttempt)
        .where(AuthAttempt.kind == kind, AuthAttempt.key == key, AuthAttempt.created_at > since)
    ).one()


def record(session: Session, kind: str, key: str) -> None:
    session.add(AuthAttempt(kind=kind, key=key))
    # Nothing is ever looked back further than a day.
    session.exec(delete(AuthAttempt).where(AuthAttempt.created_at < utcnow() - timedelta(days=1)))
    session.commit()


def check(
    session: Session, kind: str, key: str, limit: int, within: timedelta, message: str
) -> None:
    if count(session, kind, key, within) >= limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, message)
