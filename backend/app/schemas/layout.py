"""How a resume is laid out on the page, separate from what it says: margins, which
sections show, and how many pages the person is aiming for."""

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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

    # "normal" is the template's own; "narrow" is 10 mm; "custom" is `margin_mm`. Narrow
    # and custom are the same on all four sides.
    margins: Literal["normal", "narrow", "custom"] = "normal"
    margin_mm: int | None = Field(default=None, ge=5, le=30)
    # Sections left out of this resume (the content stays, so showing one again is free).
    hidden: list[Section] = Field(default_factory=list)
    # The page count the person chose when the resume ran long; null until asked.
    pages: int | None = Field(default=None, ge=1, le=3)
    # Header items left off this resume: "headline", "location", "email", "phone", or a
    # link's id. The values stay, so showing one again is a tick away.
    hidden_header: list[Annotated[str, Field(max_length=40)]] = Field(
        default_factory=list, max_length=30
    )
    # The order sections appear in; null for the usual one (SECTIONS). A student's
    # resume leads with education and projects (FRESHER_ORDER).
    order: list[Section] | None = None
    # Room between sections, entries and lines, as a multiple of the usual: set by
    # "fill the page" so a resume with room to spare uses its whole last page.
    spacing: float | None = Field(default=None, ge=1.0, le=5.0)
    # The body text a little larger (×, up to 20%): "fill the page" tries this before
    # spacing, so a short resume reads larger rather than full of gaps.
    font_scale: float | None = Field(default=None, ge=1.0, le=1.2)

    @field_validator("order")
    @classmethod
    def _whole_order(cls, order: list[str] | None) -> list[str] | None:
        """Any sections left out keep their usual places after the ones given."""
        if order is None:
            return None
        given = list(dict.fromkeys(order))
        return given + [s for s in SECTIONS if s not in given]

    def sections(self) -> list[str]:
        return list(self.order or SECTIONS)


# Little or no work history: what they studied and built is the evidence.
FRESHER_ORDER: list[Section] = [
    "summary",
    "education",
    "skills",
    "projects",
    "experience",
    "certifications",
]

_EARLY_ROLE = re.compile(r"\b(intern|internship|trainee|apprentice)\b", re.IGNORECASE)


def default_layout(data) -> "Layout":
    """A new resume's layout: education and projects first for someone with no work
    history beyond internships. `data` is a ResumeData."""
    early = all(_EARLY_ROLE.search(f"{e.title} {e.company}") for e in data.experience)
    return Layout(order=FRESHER_ORDER) if early else Layout()
