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
SessionDep = Annotated[Session, Depends(get_session)]
