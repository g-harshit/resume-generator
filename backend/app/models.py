"""Database tables. Every model is defined or imported here so `SQLModel.metadata`
(used by Alembic and the test suite) always sees the full schema.

Every table that belongs to a user has `user_id ... ON DELETE CASCADE`, so deleting
a user removes everything of theirs; `tests/test_models.py` fails if one doesn't."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
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
    # None for an account that only signs in with Google.
    password_hash: str | None = Field(default=None, max_length=255)
    # Google's stable id for the person ("sub"), once they've signed in with Google.
    google_sub: str | None = Field(default=None, max_length=255, unique=True, index=True)
    # When the address was shown to belong to them (Google said so, for now). An
    # account made with a password and never verified has None.
    email_verified_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    # Every login token carries the version current when it was issued; bumping this
    # (on a password reset) makes all earlier tokens fail — JWTs can't be revoked one
    # by one. A counter, not a timestamp: token times are whole seconds, and a token from
    # the same second as the reset must not survive it.
    token_version: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
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


class JobSource:
    PASTE = "paste"
    EXTENSION = "extension"


class JobDescription(SQLModel, table=True):
    """A job posting the user brought in, and what we read from it."""

    __tablename__ = "job_descriptions"
    # The same posting pasted twice is one row (and one model call).
    __table_args__ = (UniqueConstraint("user_id", "content_hash"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = _owner()
    source: str = Field(default=JobSource.PASTE, max_length=20)
    url: str = Field(default="", max_length=2000)
    title: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=200)
    raw_text: str = Field(sa_column=Column(Text, nullable=False))
    # sha256 of the whitespace-normalised text (see services/jobs.py).
    content_hash: str = Field(max_length=64)
    parsed: dict = Field(sa_column=Column(JSONB, nullable=False))
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class Resume(SQLModel, table=True):
    """A resume made for one job: a frozen snapshot, never a view of the profile.
    Editing the profile later doesn't change a resume someone may already have sent."""

    __tablename__ = "resumes"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = _owner()
    # Kept when the job is gone: the resume still exists and was still sent.
    job_description_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("job_descriptions.id", ondelete="SET NULL"), nullable=True
        ),
    )
    template: str = Field(max_length=40)
    title: str = Field(max_length=300)
    content: dict = Field(sa_column=Column(JSONB, nullable=False))
    # Per bullet id (and "summary"): {"original", "status": kept|reworded|reverted,
    # "attempted", "reason"} — what tailoring changed, and what it wasn't allowed to.
    provenance: dict = Field(sa_column=Column(JSONB, nullable=False))
    profile_version: int
    # Bumped on every save; a save must name the version it edited (as for profiles).
    version: int = Field(default=1, sa_column_kwargs={"server_default": "1"})
    # {"text": letter body, "removed": [{"text", "reason"}], "generated_at"}; null until
    # one is written (services/cover_letter.py).
    cover_letter: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    # Margins, hidden sections and the page goal (schemas/layout.py); null = defaults.
    layout: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class RevisionReason:
    TAILOR = "tailor"
    EDIT = "edit"
    RETAILOR = "retailor"
    COPY = "copy"  # made by duplicating another resume
    AI_EDIT = "ai_edit"  # summary written, a role condensed, or fitted to pages


class ResumeRevision(SQLModel, table=True):
    """Every version of a resume's content: undo, and "what exactly did I send?"."""

    __tablename__ = "resume_revisions"

    id: int | None = Field(default=None, primary_key=True)
    resume_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    content: dict = Field(sa_column=Column(JSONB, nullable=False))
    reason: str = Field(max_length=20)
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class AuthAttempt(SQLModel, table=True):
    """Counted to rate-limit sign-in, sign-up and password-reset requests. In the
    database rather than in memory, so the limits hold across API processes. Rows
    older than a day are pruned as new ones are written."""

    __tablename__ = "auth_attempts"
    __table_args__ = (Index("ix_auth_attempts_kind_key_created", "kind", "key", "created_at"),)

    id: int | None = Field(default=None, primary_key=True)
    kind: str = Field(max_length=30)  # "login_failed:email", "register:ip", ...
    key: str = Field(max_length=320)  # the email or IP it's about
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class PasswordReset(SQLModel, table=True):
    """A password-reset link. Only a hash of its token is stored, so a database leak
    doesn't hand out working links."""

    __tablename__ = "password_resets"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = _owner()
    token_hash: str = Field(max_length=64, unique=True)
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    used_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
