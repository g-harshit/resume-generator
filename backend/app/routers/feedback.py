"""The feedback button: anyone can tell us what's wrong or what they'd like built.
Admins read it in the admin panel (app/routers/admin.py)."""

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.auth import OptionalUser
from app.config import get_settings
from app.database import SessionDep
from app.models import Feedback
from app.services import rate_limit

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackIn(BaseModel):
    kind: Literal["problem", "idea", "other"] = "other"
    message: str = Field(min_length=3, max_length=4000)
    page: str = Field(default="", max_length=500)
    email: str = Field(default="", max_length=320)


@router.post("", status_code=status.HTTP_201_CREATED)
def send_feedback(
    body: FeedbackIn, request: Request, user: OptionalUser, session: SessionDep
) -> dict:
    ip = rate_limit.client_ip(request)
    rate_limit.check(
        session,
        "feedback",
        str(user.id) if user else ip,
        get_settings().feedback_per_day,
        timedelta(days=1),
        "Thanks — you've sent a lot of feedback today. Please send the rest tomorrow.",
    )
    message = body.message.strip()
    if len(message) < 3:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Tell us a little more.")
    item = Feedback(
        user_id=user.id if user else None,
        kind=body.kind,
        message=message,
        page=body.page.strip()[:500],
        email="" if user else body.email.strip()[:320],
        user_agent=request.headers.get("user-agent", "")[:500],
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    rate_limit.record(session, "feedback", str(user.id) if user else ip)
    return {"id": item.id}
