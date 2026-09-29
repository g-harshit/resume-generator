from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine
from sqlmodel import Session, create_engine

from app.config import get_settings, normalise_db_url

engine: Engine = create_engine(
    normalise_db_url(get_settings().database_url),
    pool_pre_ping=True,
)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


# Use as a parameter type: `def handler(session: SessionDep)`.
# scope="function" closes the session as soon as the handler returns, not after the
# response and its background tasks: a job never shares a request's transaction, and
# the connection goes back to the pool sooner. Handlers return Pydantic models, never
# ORM objects, so nothing lazy-loads after the close.
SessionDep = Annotated[Session, Depends(get_session, scope="function")]


def session_factory() -> Session:
    """A fresh session for background jobs, which outlive the request's session.
    Call it as `database.session_factory()` (not a from-import) so the test suite
    can point it at the test transaction."""
    return Session(engine)
