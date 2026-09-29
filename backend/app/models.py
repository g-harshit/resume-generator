"""Database tables. Every model is defined or imported here so `SQLModel.metadata`
(used by Alembic and the test suite) always sees the full schema."""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    # Always stored lower-cased (see `normalise_email`), so the unique index is
    # effectively case-insensitive: Alice@x.com and alice@x.com are one account.
    email: str = Field(max_length=320, unique=True, index=True)
    name: str = Field(max_length=120)
    password_hash: str = Field(max_length=255)
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


def normalise_email(email: str) -> str:
    return email.strip().lower()
