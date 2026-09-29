"""Database tables. Every model is defined or imported here so `SQLModel.metadata`
(used by Alembic and the test suite) always sees the full schema.

Every table that belongs to a user has `user_id ... ON DELETE CASCADE`, so deleting
a user removes everything of theirs; `tests/test_models.py` fails if one doesn't."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


def _owner() -> Any:
    return Field(
        sa_column=Column(
            Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )


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


class ParseStatus:
    """Plain strings, not a DB enum: an enum's labels are one more thing that can
    differ between the model and Postgres."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class SourceDocument(SQLModel, table=True):
    """A resume file the user uploaded, and what we read from it."""

    __tablename__ = "source_documents"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = _owner()
    filename: str = Field(max_length=255)
    mime: str = Field(max_length=100)
    size_bytes: int
    storage_key: str = Field(max_length=100)

    parse_status: str = Field(default=ParseStatus.PENDING, max_length=20)
    # Shown to the user as-is, so it's written for them, not a stack trace.
    parse_error: str | None = Field(default=None, sa_column=Column(Text))
    extracted_text: str | None = Field(default=None, sa_column=Column(Text))
    parsed: dict | None = Field(default=None, sa_column=Column(JSONB))
    # Notes from reading the file: [{"target": entry id, "field", "message"}].
    parse_warnings: list | None = Field(default=None, sa_column=Column(JSONB))

    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    started_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    finished_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


class Profile(SQLModel, table=True):
    """Everything true about the user: the only source of facts for their resumes."""

    __tablename__ = "profiles"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
        )
    )
    data: dict = Field(sa_column=Column(JSONB, nullable=False))
    # Bumped on every save; a PUT must name the version it edited (Phase 4).
    version: int = 1
    # Null until the user has confirmed the parse. Nothing is tailored from an
    # unreviewed profile, and a new upload may replace one freely.
    reviewed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    source_document_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("source_documents.id", ondelete="SET NULL"), nullable=True
        ),
    )
    updated_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
