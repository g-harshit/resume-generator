"""`ResumeData`: the one shape for both a user's profile and a tailored resume.

Every entry carries a stable `id`. Ids are what let a tailored bullet be traced back
to the profile bullet it came from (plan.md, Principle 6), so they are generated once
and never rewritten. Anything built without an id gets one from `default_factory`.

The TypeScript types in `packages/schema` are generated from this file
(`pnpm gen:schema`); never edit them by hand.
"""

import re
import secrets
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

# --- building blocks ---------------------------------------------------------


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


def _id_field(prefix: str):
    return Field(default_factory=lambda: new_id(prefix), min_length=1, max_length=40)


_YEAR_MONTH = re.compile(r"^\d{4}(-(0[1-9]|1[0-2]))?$")


def _check_year_month(v: str | None) -> str | None:
    if v is not None and not _YEAR_MONTH.match(v):
        raise ValueError("Use YYYY or YYYY-MM")
    return v


# "2021-03" or "2021". A date a parser couldn't read is None, not a guess.
YearMonth = Annotated[str | None, AfterValidator(_check_year_month)]

ShortText = Annotated[str, Field(max_length=200)]
LongText = Annotated[str, Field(max_length=2000)]


class _Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        # Fields with defaults (ids, empty lists) are always present in API responses,
        # so the generated TS types mark them required.
        json_schema_serialization_defaults_required=True,
    )


def _check_order(start: str | None, end: str | None) -> None:
    # YYYY and YYYY-MM compare correctly as strings on their shared prefix.
    if start and end and end[: len(start)] < start[: len(end)]:
        raise ValueError("End date is before start date")


# --- sections ------------------------------------------------------------------


class Bullet(_Model):
    id: str = _id_field("b")
    text: LongText


class Link(_Model):
    id: str = _id_field("lnk")
    label: ShortText = ""
    url: Annotated[str, Field(max_length=500)]


class Basics(_Model):
    name: ShortText = ""
    headline: ShortText = ""
    email: ShortText = ""
    phone: ShortText = ""
    location: ShortText = ""
    links: list[Link] = Field(default_factory=list, max_length=10)


class Experience(_Model):
    id: str = _id_field("exp")
    company: ShortText = ""
    title: ShortText = ""
    location: ShortText = ""
    start: YearMonth = None
    end: YearMonth = None
    # Distinguishes "still here" from "end date unknown" — both have end = None.
    current: bool = False
    bullets: list[Bullet] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def _dates(self) -> Self:
        if self.current and self.end:
            raise ValueError("A current role can't have an end date")
        _check_order(self.start, self.end)
        return self


class Education(_Model):
    id: str = _id_field("edu")
    institution: ShortText = ""
    degree: ShortText = ""
    field: ShortText = ""
    location: ShortText = ""
    start: YearMonth = None
    end: YearMonth = None
    details: LongText = ""  # grade, honours, relevant coursework

    @model_validator(mode="after")
    def _dates(self) -> Self:
        _check_order(self.start, self.end)
        return self


class SkillGroup(_Model):
    id: str = _id_field("sk")
    group: ShortText = ""  # "Languages", "Tools"… empty for an ungrouped list
    items: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(
        default_factory=list, max_length=60
    )


class Project(_Model):
    id: str = _id_field("prj")
    name: ShortText = ""
    url: Annotated[str, Field(max_length=500)] = ""
    start: YearMonth = None
    end: YearMonth = None
    bullets: list[Bullet] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _dates(self) -> Self:
        _check_order(self.start, self.end)
        return self


class Certification(_Model):
    id: str = _id_field("cert")
    name: ShortText
    issuer: ShortText = ""
    date: YearMonth = None
    url: Annotated[str, Field(max_length=500)] = ""


# --- the whole document --------------------------------------------------------


class ResumeData(_Model):
    basics: Basics = Field(default_factory=Basics)
    summary: LongText = ""
    experience: list[Experience] = Field(default_factory=list, max_length=30)
    education: list[Education] = Field(default_factory=list, max_length=15)
    skills: list[SkillGroup] = Field(default_factory=list, max_length=20)
    projects: list[Project] = Field(default_factory=list, max_length=20)
    certifications: list[Certification] = Field(default_factory=list, max_length=30)

    def all_ids(self) -> list[str]:
        ids: list[str] = [link.id for link in self.basics.links]
        for exp in self.experience:
            ids += [exp.id, *(b.id for b in exp.bullets)]
        ids += [e.id for e in self.education]
        ids += [s.id for s in self.skills]
        for prj in self.projects:
            ids += [prj.id, *(b.id for b in prj.bullets)]
        ids += [c.id for c in self.certifications]
        return ids

    def all_skills(self) -> list[str]:
        return [item for group in self.skills for item in group.items]

    @model_validator(mode="after")
    def _unique_ids(self) -> Self:
        seen: set[str] = set()
        for i in self.all_ids():
            if i in seen:
                raise ValueError(f"Duplicate id: {i}")
            seen.add(i)
        return self
