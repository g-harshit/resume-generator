"""`CurrentUser`: the dependency every signed-in endpoint takes."""

from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.database import SessionDep
from app.models import User, utcnow
from app.security import read_token

_bearer = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not signed in",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise _unauthorized()
    read = read_token(credentials.credentials)
    user = session.get(User, read[0]) if read else None
    if user is None:  # bad/expired token, or the account was deleted
        raise _unauthorized()
    if read[1] != user.token_version:
        raise _unauthorized()  # issued before the password last changed
    if user.disabled_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, DISABLED)
    # Last seen, for the admin panel: at most one write an hour per person.
    now = utcnow()
    if user.last_seen_at is None or now - user.last_seen_at > LAST_SEEN_EVERY:
        user.last_seen_at = now
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


DISABLED = "This account has been disabled. If you think that's a mistake, contact us."
LAST_SEEN_EVERY = timedelta(hours=1)

CurrentUser = Annotated[User, Depends(get_current_user)]


def is_admin(user: User) -> bool:
    """On the admin list, and the address is proven to be theirs."""
    return user.email in get_settings().admin_email_list and user.email_verified_at is not None


def get_admin(user: CurrentUser) -> User:
    if not is_admin(user):
        # 404, not 403: the admin panel's existence is nobody else's business.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return user


AdminUser = Annotated[User, Depends(get_admin)]
