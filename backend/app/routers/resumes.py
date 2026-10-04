import logging
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlmodel import Session, func, select

from app.ai_providers import AIProviderError, get_ai_provider
from app.auth import CurrentUser
from app.config import get_settings
from app.database import SessionDep
from app.models import (
    JobDescription,
    Profile,
    Resume,
    ResumeRevision,
    RevisionReason,
    User,
    utcnow,
)
from app.rendering.catalog import BY_SLUG
from app.rendering.render import render_html, render_letter_html, render_pdf
from app.routers.templates import PreviewOut, pdf_filename, preview_of
from app.schemas.layout import Layout, default_layout
from app.schemas.resume import ResumeData
from app.services import rate_limit
from app.services.bridge import bridge, missing_skills
from app.services.cover_letter import write_cover_letter
from app.services.fit import (
    FitError,
    SummaryLength,
    condense,
    count_pages,
    fill_page,
    fit_to_pages,
    write_summary,
)
from app.services.keywords import KeywordError, add_keywords
from app.services.match import match_job
from app.services.tailor import tailor

log = logging.getLogger(__name__)

router = APIRouter(prefix="/resumes", tags=["resumes"])


class TailorIn(BaseModel):
    job_id: int
    template: str = Field(max_length=40)


class ResumeSummary(BaseModel):
    id: int
    title: str
    template: str
    version: int
    job_id: int | None
    # About the job it was made for; empty / null if the job is gone.
    company: str
    job_title: str
    source: str | None  # "paste" | "extension"
    created_at: datetime
    updated_at: datetime
    # How many of the job's skills this resume shows; null if the job is gone.
    covered: int | None
    total: int | None


class ResumeOut(ResumeSummary):
    content: ResumeData
    provenance: dict
    match: dict | None
    cover_letter: dict | None
    layout: Layout


def _own(session: Session, user: User, resume_id: int) -> Resume:
    resume = session.get(Resume, resume_id)
    if resume is None or resume.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")
    return resume


def _job(session: Session, resume: Resume) -> JobDescription | None:
    if resume.job_description_id is None:
        return None
    return session.get(JobDescription, resume.job_description_id)


def _match(session: Session, resume: Resume) -> dict | None:
    job = _job(session, resume)
    if job is None:
        return None
    content = ResumeData.model_validate(resume.content)
    # The job's terms no line names (the Skills list doesn't count): what the editor
    # offers to work into a line.
    return {
        **match_job(content, job.parsed),
        "missing_in_lines": missing_skills(content, job.parsed),
    }


def _summary(session: Session, resume: Resume, match: dict | None) -> dict:
    job = _job(session, resume)
    return {
        "id": resume.id,
        "title": resume.title,
        "template": resume.template,
        "version": resume.version,
        "job_id": resume.job_description_id,
        "company": job.company if job else "",
        "job_title": job.title if job else "",
        "source": job.source if job else None,
        "created_at": resume.created_at,
        "updated_at": resume.updated_at,
        "covered": match["covered"] if match else None,
        "total": match["total"] if match else None,
    }


def _out(session: Session, resume: Resume) -> ResumeOut:
    match = _match(session, resume)
    return ResumeOut(
        **_summary(session, resume, match),
        content=ResumeData.model_validate(resume.content),
        provenance=resume.provenance,
        match=match,
        cover_letter=resume.cover_letter,
        layout=_layout(resume),
    )


def _layout(resume: Resume) -> Layout:
    return Layout.model_validate(resume.layout or {})


def _title(job: JobDescription) -> str:
    return " — ".join(x for x in (job.title, job.company) if x) or "Untitled job"


def _reviewed_profile(session: Session, user: User) -> Profile:
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if profile is None or profile.reviewed_at is None:
        # Everything in a resume comes from the profile, so it has to have been checked.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Review and confirm your profile first: every resume is built from it.",
        )
    return profile


def _check_daily_cap(session: Session, user: User) -> None:
    """Tailoring runs (new resumes and re-tailors) per day: each is several model calls."""
    since = utcnow() - timedelta(days=1)
    runs = session.exec(
        select(func.count())
        .select_from(ResumeRevision)
        .join(Resume, Resume.id == ResumeRevision.resume_id)
        .where(
            Resume.user_id == user.id,
            ResumeRevision.created_at > since,
            ResumeRevision.reason.in_([RevisionReason.TAILOR, RevisionReason.RETAILOR]),
        )
    ).one()
    if runs >= get_settings().resumes_per_day:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "You've tailored a lot of resumes today. Please try again tomorrow.",
        )


def _fill(
    profile: Profile,
    job: JobDescription,
    content: ResumeData,
    provenance: dict,
    slug: str,
    layout: Layout,
) -> tuple[ResumeData, dict, Layout]:
    """Use the room left on the last page (the person's own left-out lines first). A
    nicety: if it fails, the resume is as tailored."""
    try:
        result = fill_page(
            content,
            layout,
            slug,
            ResumeData.model_validate(profile.data),
            job.parsed,
            get_ai_provider(),
            provenance,
            # Tailoring just wrote the summary for this job; no second model call.
            longer_summary=False,
        )
    except Exception:
        log.exception("filling the page failed")
        return content, provenance, layout
    return result.resume, result.provenance, result.layout


def _tailor(profile: Profile, job: JobDescription) -> tuple[ResumeData, dict]:
    try:
        return tailor(
            ResumeData.model_validate(profile.data), job.parsed, job.raw_text, get_ai_provider()
        )
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None


@router.post("", status_code=status.HTTP_201_CREATED)
def create_resume(body: TailorIn, user: CurrentUser, session: SessionDep) -> ResumeOut:
    """Tailor the profile to a job. Waits for the model (usually 10-30 s)."""
    if body.template not in BY_SLUG:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No such template")
    job = session.get(JobDescription, body.job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    profile = _reviewed_profile(session, user)
    _check_daily_cap(session, user)
    content, provenance = _tailor(profile, job)
    content, provenance, layout = _fill(
        profile, job, content, provenance, body.template, default_layout(content)
    )

    data = content.model_dump(mode="json")
    resume = Resume(
        user_id=user.id,
        job_description_id=job.id,
        template=body.template,
        title=_title(job)[:300],
        content=data,
        provenance=provenance,
        profile_version=profile.version,
        layout=layout.model_dump(),
    )
    session.add(resume)
    session.flush()
    session.add(ResumeRevision(resume_id=resume.id, content=data, reason=RevisionReason.TAILOR))
    session.commit()
    session.refresh(resume)
    return _out(session, resume)


@router.get("")
def list_resumes(user: CurrentUser, session: SessionDep) -> list[ResumeSummary]:
    resumes = session.exec(
        select(Resume).where(Resume.user_id == user.id).order_by(Resume.updated_at.desc())
    ).all()
    return [ResumeSummary(**_summary(session, r, _match(session, r))) for r in resumes]


@router.get("/{resume_id}")
def get_resume(resume_id: int, user: CurrentUser, session: SessionDep) -> ResumeOut:
    return _out(session, _own(session, user, resume_id))


class SaveIn(BaseModel):
    # The version the editor last loaded; a stale one gets 409, as for profiles.
    version: int
    content: ResumeData
    template: str = Field(max_length=40)
    # Optional, so a client that doesn't know about layout leaves it alone.
    layout: Layout | None = None


# Autosave fires every few seconds while someone types. Saves within this long of the
# last "edit" revision update it rather than adding one, so the history stays useful.
EDIT_REVISION_WINDOW = timedelta(minutes=10)


def _conflict() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        "This resume was changed somewhere else (another tab?). Reload to see the latest.",
    )


@router.put("/{resume_id}")
def save_resume(resume_id: int, body: SaveIn, user: CurrentUser, session: SessionDep) -> ResumeOut:
    """The person's own edits. Unlike tailoring, nothing here is checked against the
    profile: it's their resume and their words."""
    resume = _own(session, user, resume_id)
    if body.template not in BY_SLUG:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No such template")
    data = body.content.model_dump(mode="json")
    now = utcnow()
    result = session.exec(
        update(Resume)
        .where(Resume.id == resume.id, Resume.version == body.version)
        .values(
            content=data,
            template=body.template,
            version=Resume.version + 1,
            updated_at=now,
            **({"layout": body.layout.model_dump()} if body.layout else {}),
        )
    )
    if result.rowcount != 1:
        session.rollback()
        raise _conflict()

    latest = session.exec(
        select(ResumeRevision)
        .where(ResumeRevision.resume_id == resume.id)
        .order_by(ResumeRevision.created_at.desc())
    ).first()
    if (
        latest is not None
        and latest.reason == RevisionReason.EDIT
        and now - latest.created_at < EDIT_REVISION_WINDOW
    ):
        latest.content = data
        session.add(latest)
    else:
        session.add(ResumeRevision(resume_id=resume.id, content=data, reason=RevisionReason.EDIT))
    session.commit()
    session.refresh(resume)
    return _out(session, resume)


@router.post("/{resume_id}/retailor")
def retailor(resume_id: int, user: CurrentUser, session: SessionDep) -> ResumeOut:
    """Tailor again from the profile as it is now (say, after adding a skill). The
    edits made to this resume are replaced; the previous version stays in its history."""
    resume = _own(session, user, resume_id)
    job = _job(session, resume)
    if job is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "The job this resume was made for is gone.")
    profile = _reviewed_profile(session, user)
    _check_daily_cap(session, user)
    started_at_version = resume.version
    content, provenance = _tailor(profile, job)  # 20-40 s; the editor may save meanwhile
    content, provenance, layout = _fill(
        profile, job, content, provenance, resume.template, _layout(resume)
    )

    data = content.model_dump(mode="json")
    result = session.exec(
        update(Resume)
        .where(Resume.id == resume.id, Resume.version == started_at_version)
        .values(
            content=data,
            provenance=provenance,
            profile_version=profile.version,
            layout=layout.model_dump(),
            version=Resume.version + 1,
            updated_at=utcnow(),
        )
    )
    if result.rowcount != 1:  # edited while tailoring: don't throw those edits away
        session.rollback()
        raise _conflict()
    session.add(ResumeRevision(resume_id=resume.id, content=data, reason=RevisionReason.RETAILOR))
    session.commit()
    session.refresh(resume)
    return _out(session, resume)


@router.post("/{resume_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate(resume_id: int, user: CurrentUser, session: SessionDep) -> ResumeOut:
    """A copy to try something different on. No model call, so not part of the cap."""
    source = _own(session, user, resume_id)
    copy = Resume(
        user_id=user.id,
        job_description_id=source.job_description_id,
        template=source.template,
        title=f"{source.title} (copy)"[:300],
        content=source.content,
        provenance=source.provenance,
        profile_version=source.profile_version,
    )
    session.add(copy)
    session.flush()
    session.add(ResumeRevision(resume_id=copy.id, content=copy.content, reason=RevisionReason.COPY))
    session.commit()
    session.refresh(copy)
    return _out(session, copy)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: int, user: CurrentUser, session: SessionDep) -> Response:
    """Deletes the resume and its history. The job it was made for stays."""
    session.delete(_own(session, user, resume_id))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- fitting to the page ------------------------------------------------------------


class AiEditIn(BaseModel):
    # The version the editor holds: the model takes seconds, and an autosave in between
    # must not be overwritten (409 instead).
    version: int


class SummaryIn(AiEditIn):
    length: SummaryLength = "same"


class CondenseIn(AiEditIn):
    entry_id: str = Field(max_length=40)
    bullets: int = Field(ge=1, le=10)


class FitIn(AiEditIn):
    pages: int = Field(ge=1, le=3)


class FitOut(BaseModel):
    resume: ResumeOut
    pages_before: int
    pages_after: int
    steps: list[str]
    notes: list[str]


def _ai_edit_start(session: Session, user: User, resume_id: int, version: int):
    resume = _own(session, user, resume_id)
    if resume.version != version:
        raise _conflict()
    job = _job(session, resume)
    rate_limit.check(
        session,
        "resume_ai",
        str(user.id),
        get_settings().resume_ai_edits_per_day,
        timedelta(days=1),
        "You've used a lot of AI edits today. Please try again tomorrow.",
    )
    return resume, job.parsed if job else {}


def _ai_edit_save(
    session: Session,
    user: User,
    resume: Resume,
    started_at_version: int,
    content: ResumeData,
    provenance: dict,
    layout: Layout | None = None,
) -> None:
    data = content.model_dump(mode="json")
    result = session.exec(
        update(Resume)
        .where(Resume.id == resume.id, Resume.version == started_at_version)
        .values(
            content=data,
            provenance=provenance,
            version=Resume.version + 1,
            updated_at=utcnow(),
            **({"layout": layout.model_dump()} if layout else {}),
        )
    )
    if result.rowcount != 1:  # edited while the model was working
        session.rollback()
        raise _conflict()
    session.add(ResumeRevision(resume_id=resume.id, content=data, reason=RevisionReason.AI_EDIT))
    rate_limit.record(session, "resume_ai", str(user.id))  # commits
    session.refresh(resume)


@router.post("/{resume_id}/summary")
def write_resume_summary(
    resume_id: int, body: SummaryIn, user: CurrentUser, session: SessionDep
) -> ResumeOut:
    """Write (or rewrite) the summary from the resume's own facts: shorter, about the
    same length, or longer than the one there now."""
    resume, job = _ai_edit_start(session, user, resume_id, body.version)
    content = ResumeData.model_validate(resume.content)
    try:
        summary = write_summary(content, job, get_ai_provider(), body.length)
    except FitError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None
    provenance = {
        **resume.provenance,
        "summary": {
            "original": content.summary,
            "status": "written",
            "attempted": None,
            "reason": None,
        },
    }
    content.summary = summary
    _ai_edit_save(session, user, resume, body.version, content, provenance)
    return _out(session, resume)


@router.post("/{resume_id}/condense")
def condense_entry(
    resume_id: int, body: CondenseIn, user: CurrentUser, session: SessionDep
) -> FitOut:
    """Shorten one role or project to at most `bullets` lines."""
    resume, job = _ai_edit_start(session, user, resume_id, body.version)
    content = ResumeData.model_validate(resume.content)
    if not any(e.id == body.entry_id for e in [*content.experience, *content.projects]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That role or project isn't in this resume.")
    layout = _layout(resume)
    before = count_pages(content, resume.template, layout)
    try:
        shorter, new_lines, notes = condense(
            content, {body.entry_id: body.bullets}, job, get_ai_provider()
        )
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None
    _ai_edit_save(session, user, resume, body.version, shorter, {**resume.provenance, **new_lines})
    return FitOut(
        resume=_out(session, resume),
        pages_before=before,
        pages_after=count_pages(shorter, resume.template, layout),
        steps=[],
        notes=notes,
    )


class BridgeOut(BaseModel):
    resume: ResumeOut
    added: list[str]  # the job's skills now named in a line


@router.post("/{resume_id}/bridge")
def bridge_skills(
    resume_id: int, body: AiEditIn, user: CurrentUser, session: SessionDep
) -> BridgeOut:
    """Name the job's skills in the lines that already prove them ("Django" → Python),
    for a resume as it is now. New resumes get this when they're tailored."""
    resume, job = _ai_edit_start(session, user, resume_id, body.version)
    if not job:
        raise HTTPException(status.HTTP_409_CONFLICT, "The job this resume was made for is gone.")
    content = ResumeData.model_validate(resume.content)
    provenance = {**resume.provenance}
    # The resume is the evidence: every line in it is the person's own or checked.
    added = bridge(content, provenance, content.model_copy(deep=True), job, get_ai_provider())
    if added:
        _ai_edit_save(session, user, resume, body.version, content, provenance)
    return BridgeOut(resume=_out(session, resume), added=added)


class KeywordsIn(AiEditIn):
    keywords: list[Annotated[str, Field(min_length=1, max_length=60)]] = Field(
        min_length=1, max_length=8
    )
    again: bool = False  # "Rewrite again": a different wording of the same keywords


@router.post("/{resume_id}/lines/{line_id}/keywords")
def line_keywords(
    resume_id: int, line_id: str, body: KeywordsIn, user: CurrentUser, session: SessionDep
) -> ResumeOut:
    """Rewrite one line to include the keywords the person chose for it."""
    resume, _ = _ai_edit_start(session, user, resume_id, body.version)
    content = ResumeData.model_validate(resume.content)
    entry = next(
        (
            e
            for e in [*content.experience, *content.projects]
            if any(b.id == line_id for b in e.bullets)
        ),
        None,
    )
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That line isn't in this resume.")
    bullet = next(b for b in entry.bullets if b.id == line_id)
    before = resume.provenance.get(line_id, {})
    # Rewrite from the line as it was before any keyword rewrite, so "again" doesn't
    # stack keywords on keywords.
    base = before.get("base") if before.get("status") == "keywords" else bullet.text
    keywords = list(dict.fromkeys(k.strip() for k in body.keywords if k.strip()))
    where = getattr(entry, "company", None) or getattr(entry, "name", "")
    try:
        text = add_keywords(
            base,
            keywords,
            f"{getattr(entry, 'title', '')} {where}".strip(),
            get_ai_provider(),
            avoid=[bullet.text] if body.again else None,
        )
    except KeywordError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Couldn't rewrite the line: {exc}."
        ) from None
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None
    bullet.text = text
    provenance = {
        **resume.provenance,
        line_id: {
            "original": before.get("original") or base,
            "status": "keywords",
            "keywords": keywords,
            "base": base,
            "attempted": None,
            "reason": None,
        },
    }
    _ai_edit_save(session, user, resume, body.version, content, provenance)
    return _out(session, resume)


@router.post("/{resume_id}/fit")
def fit(resume_id: int, body: FitIn, user: CurrentUser, session: SessionDep) -> FitOut:
    """Make the resume fit `pages`: narrower margins first, then fewer lines for older
    roles (the newest keeps the most), re-rendering after each round. 20-60 s."""
    resume, job = _ai_edit_start(session, user, resume_id, body.version)
    try:
        own = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
        result = fit_to_pages(
            ResumeData.model_validate(resume.content),
            _layout(resume),
            resume.template,
            body.pages,
            job,
            get_ai_provider(),
            profile=ResumeData.model_validate(own.data) if own else None,
            provenance=resume.provenance,
        )
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None
    _ai_edit_save(
        session,
        user,
        resume,
        body.version,
        result.resume,
        {**resume.provenance, **result.provenance},
        result.layout,
    )
    return FitOut(
        resume=_out(session, resume),
        pages_before=result.pages_before,
        pages_after=result.pages_after,
        steps=result.steps,
        notes=result.notes,
    )


# --- cover letter ------------------------------------------------------------------


@router.post("/{resume_id}/cover-letter")
def write_letter(resume_id: int, user: CurrentUser, session: SessionDep) -> ResumeOut:
    """Write (or rewrite) the cover letter for this resume's job, from this resume.
    Waits for the model, usually 15-30 s."""
    resume = _own(session, user, resume_id)
    job = _job(session, resume)
    if job is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "The job this resume was made for is gone.")
    rate_limit.check(
        session,
        "cover_letter",
        str(user.id),
        get_settings().cover_letters_per_day,
        timedelta(days=1),
        "You've written a lot of cover letters today. Please try again tomorrow.",
    )
    try:
        letter = write_cover_letter(
            ResumeData.model_validate(resume.content), job.parsed, job.raw_text, get_ai_provider()
        )
    except AIProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None
    rate_limit.record(session, "cover_letter", str(user.id))
    resume.cover_letter = {**letter, "generated_at": utcnow().isoformat()}
    resume.updated_at = utcnow()
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return _out(session, resume)


class LetterIn(BaseModel):
    text: str = Field(max_length=10_000)


@router.put("/{resume_id}/cover-letter")
def save_letter(
    resume_id: int, body: LetterIn, user: CurrentUser, session: SessionDep
) -> ResumeOut:
    """The person's own edits to the letter: theirs, so not checked."""
    resume = _own(session, user, resume_id)
    if resume.cover_letter is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no cover letter yet.")
    resume.cover_letter = {**resume.cover_letter, "text": body.text}
    resume.updated_at = utcnow()
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return _out(session, resume)


@router.get("/{resume_id}/cover-letter/pdf")
def letter_pdf(
    resume_id: int, user: CurrentUser, session: SessionDep, template: str | None = None
) -> Response:
    resume = _own(session, user, resume_id)
    if not resume.cover_letter:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no cover letter yet.")
    data = ResumeData.model_validate(resume.content)
    job = _job(session, resume)
    html = render_letter_html(
        data,
        resume.cover_letter["text"],
        job.company if job else "",
        _template(resume, template),
        _layout(resume),
    )
    rendered = render_pdf(html)
    filename = pdf_filename(data).replace("-Resume.pdf", "-Cover-Letter.pdf")
    return Response(
        rendered.content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


def _template(resume: Resume, override: str | None) -> str:
    slug = override or resume.template
    if slug not in BY_SLUG:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such template")
    return slug


@router.get("/{resume_id}/preview")
def preview(
    resume_id: int, user: CurrentUser, session: SessionDep, template: str | None = None
) -> PreviewOut:
    resume = _own(session, user, resume_id)
    html = render_html(
        ResumeData.model_validate(resume.content), _template(resume, template), _layout(resume)
    )
    return preview_of(html)


@router.get("/{resume_id}/pdf")
def pdf(
    resume_id: int, user: CurrentUser, session: SessionDep, template: str | None = None
) -> Response:
    resume = _own(session, user, resume_id)
    data = ResumeData.model_validate(resume.content)
    rendered = render_pdf(render_html(data, _template(resume, template), _layout(resume)))
    return Response(
        rendered.content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{pdf_filename(data)}"',
            "X-Page-Count": str(rendered.pages),
            "Cache-Control": "private, no-store",
        },
    )
