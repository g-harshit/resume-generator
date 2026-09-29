"""`CurrentUser`: the dependency every signed-in endpoint takes."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.database import SessionDep
from app.models import User
from app.security import user_id_from_token

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
    user_id = user_id_from_token(credentials.credentials)
    user = session.get(User, user_id) if user_id is not None else None
    if user is None:  # bad/expired token, or the account was deleted
        raise _unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
