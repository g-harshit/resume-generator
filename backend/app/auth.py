"""`CurrentUser`: the dependency every signed-in endpoint takes."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.database import SessionDep
from app.models import User
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
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
