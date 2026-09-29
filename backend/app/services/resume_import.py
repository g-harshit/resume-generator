"""Reading an uploaded resume, as a background job, and turning it into a profile.

Runs after the upload request has returned (FastAPI BackgroundTasks, in the API
process), so it opens its own session via `database.session_factory()` and commits
progress as it goes: the polling UI only sees what has been committed.
"""

import logging
from datetime import timedelta

from sqlmodel import Session, select

from app import database
from app.ai_providers import AIProviderError, get_ai_provider
from app.models import ParseStatus, Profile, SourceDocument, utcnow
from app.services.extract import ExtractionError, extract_text
from app.services.parse_resume import TooLongError, parse_resume
from app.services.storage import get_storage

log = logging.getLogger(__name__)

# A job killed by an API restart stays "running" forever; after this long we report it
# as failed so the user can try again.
STALE_AFTER = timedelta(minutes=10)

_UNEXPECTED = "Something went wrong reading your resume. Please try again."


def notes_of(doc: SourceDocument | None) -> list[dict]:
    """The parse notes, in the current shape. Uploads read before notes pointed at
    entry ids stored {"path", "message"}; those become general notes."""
    if doc is None:
        return []
    return [
        n if "target" in n else {"target": "", "field": None, "message": n.get("message", "")}
        for n in (doc.parse_warnings or [])
    ]


def is_stale(doc: SourceDocument) -> bool:
    return (
        doc.parse_status in (ParseStatus.PENDING, ParseStatus.RUNNING)
        and utcnow() - doc.created_at > STALE_AFTER
    )


def run_parse(document_id: int) -> None:
    with database.session_factory() as session:
        doc = session.get(SourceDocument, document_id)
        if doc is None:
            return
        doc.parse_status = ParseStatus.RUNNING
        doc.started_at = utcnow()
        session.commit()

        try:
            text = extract_text(get_storage().get(doc.storage_key), doc.mime)
            doc.extracted_text = text
            session.commit()

            data, warnings = parse_resume(text, get_ai_provider())
            doc.parsed = data.model_dump(mode="json")
            doc.parse_warnings = warnings
            doc.parse_status = ParseStatus.DONE
            apply_if_unreviewed(session, doc)
        except (ExtractionError, TooLongError, AIProviderError) as exc:
            doc.parse_status = ParseStatus.FAILED
            doc.parse_error = str(exc)
        except Exception:
            log.exception("Parsing source document %s failed", document_id)
            doc.parse_status = ParseStatus.FAILED
            doc.parse_error = _UNEXPECTED
        doc.finished_at = utcnow()
        session.commit()


def apply_if_unreviewed(session: Session, doc: SourceDocument) -> bool:
    """Make `doc` the user's profile, unless they already have a profile they have
    reviewed: that one holds their corrections, and a new upload must never silently
    overwrite them. They can still choose to replace it (`replace_profile`)."""
    profile = session.exec(select(Profile).where(Profile.user_id == doc.user_id)).first()
    if profile is not None and profile.reviewed_at is not None:
        return False
    replace_profile(session, doc, profile)
    return True


def replace_profile(session: Session, doc: SourceDocument, profile: Profile | None) -> Profile:
    if profile is None:
        profile = Profile(user_id=doc.user_id, data=doc.parsed, source_document_id=doc.id)
    else:
        profile.data = doc.parsed
        profile.version += 1
        profile.reviewed_at = None  # a new parse has to be checked again
        profile.source_document_id = doc.id
        profile.updated_at = utcnow()
    session.add(profile)
    return profile
