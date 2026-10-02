"""How a resume is laid out on the page, separate from what it says: margins, which
sections show, and how many pages the person is aiming for."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Section = Literal["summary", "experience", "education", "skills", "projects", "certifications"]
SECTIONS: tuple[str, ...] = (
    "summary",
    "experience",
    "education",
    "skills",
    "projects",
    "certifications",
)


class Layout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    margins: Literal["normal", "narrow"] = "normal"
    # Sections left out of this resume (the content stays, so showing one again is free).
    hidden: list[Section] = Field(default_factory=list)
    # The page count the person chose when the resume ran long; null until asked.
    pages: int | None = Field(default=None, ge=1, le=3)
