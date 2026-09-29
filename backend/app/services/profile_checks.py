"""What's missing or inconsistent in a profile *as it is now*.

Recomputed on every read and save, so a check disappears the moment the user fixes
it. Each check points at an entry by id (`target`) and a `field`, like the parse
notes, so the editor can show it beside the right input.

`blocking` checks stop the profile being confirmed; the rest are advice.
"""

from app.schemas.resume import ResumeData


def _check(target: str, field: str | None, message: str, blocking: bool = False) -> dict:
    return {"target": target, "field": field, "message": message, "blocking": blocking}


def profile_checks(data: ResumeData) -> list[dict]:
    out: list[dict] = []
    b = data.basics
    if not b.name:
        out.append(_check("basics", "name", "Add your name.", blocking=True))
    if not b.email:
        out.append(
            _check("basics", "email", "Add an email address. Recruiters need a way to reply.")
        )
    if not b.phone:
        out.append(_check("basics", "phone", "Add a phone number."))

    for exp in data.experience:
        if not exp.company and not exp.title:
            out.append(_check(exp.id, "title", "Add a job title or company.", blocking=True))
        if not exp.start:
            out.append(_check(exp.id, "start", "Add a start date."))
        if not exp.current and not exp.end:
            out.append(_check(exp.id, "end", "Add an end date, or mark this as your current role."))
        if not exp.bullets:
            out.append(_check(exp.id, None, "Add at least one line about what you did here."))

    for edu in data.education:
        if not edu.institution and not edu.degree:
            out.append(
                _check(edu.id, "institution", "Add the school or the degree.", blocking=True)
            )

    for prj in data.projects:
        if not prj.name:
            out.append(_check(prj.id, "name", "Give this project a name.", blocking=True))

    return out


def blocking(checks: list[dict]) -> list[dict]:
    return [c for c in checks if c["blocking"]]
