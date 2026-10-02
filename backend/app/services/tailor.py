"""Profile + job → a resume for that job. The model words; code decides what's true.

The model never writes a resume. It returns a *plan* that points at the profile by
id: which bullets to show for each role, in what order, and how to word them; a
summary; which skills to list. `apply_plan` then builds the resume from the profile,
checking every line the model wrote against the line it came from:

- a bullet can only come from a bullet of the same role (or project)
- a reworded bullet may not contain a number its original didn't
- it may not name a skill or job keyword its original didn't (that's how a model
  "tailors" a Kafka claim onto the wrong job)
- it may not grow much longer than the original (that's embellishment)
- skills must already be in the profile; the summary gets the number and skill
  checks against the whole profile

Anything that fails reverts to the person's own words and is recorded in the
provenance, so the editor can say what was kept and why. Names, titles, employers,
dates, education and certifications are always copied from the profile; every role
stays, in the profile's order, so the resume never shows a gap that isn't real.
"""

import json
import logging
import re

from pydantic import BaseModel

from app.ai_providers import AIProvider
from app.schemas.resume import Bullet, ResumeData, SkillGroup
from app.services.jobs import is_written
from app.services.match import alternatives, normalise

log = logging.getLogger(__name__)


# --- what the model fills ------------------------------------------------------------


class PlanBullet(BaseModel):
    source_id: str  # the profile bullet this line is a rewording of
    text: str


class PlanEntry(BaseModel):
    id: str  # a profile experience or project id
    bullets: list[PlanBullet]


class PlanSkillGroup(BaseModel):
    group: str
    items: list[str]


class TailorPlan(BaseModel):
    summary: str
    experience: list[PlanEntry]
    projects: list[PlanEntry]
    skills: list[PlanSkillGroup]


INSTRUCTIONS = """\
You tailor a person's resume to one job. You get their profile (JSON, every entry and
bullet has an id) and the job. Return a plan that points at the profile by id.

What you may do:
- For each role in `experience`, choose the bullets that matter most for this job
  (usually 3-6; at least 1 when the role has any) and put the most relevant first.
  Choosing and ordering is most of the work. Every bullet you return names the
  `source_id` of the profile bullet it comes from, from that same role.
- Reword bullets where it helps this job: use the job's name for something the
  bullet already describes, lead with the part the job cares about, tighten it.
  Stay close to the original; the facts must not change.
- Choose and order the projects that help (or none), the same way. When the profile
  has little or no work experience (a student or recent graduate), projects are the
  main evidence: keep every project that's relevant, with its best lines.
- Write a 2-3 sentence `summary` for this job using only facts from the profile.
- Order `skills` so the job's skills come first. You may regroup them.

What you must never do:
- Add any fact that is not in the source bullet: no new numbers, tools, technologies,
  responsibilities, team sizes, outcomes or employers. If a bullet doesn't mention
  Kubernetes, your rewording doesn't either, even if the job asks for it.
- Move an achievement from one role to another.
- List a skill that is not in the profile's skills.
- Make a bullet much longer. Rewording means clearer and more relevant, not more.
- Add qualities or outcomes the bullet doesn't state: "optimizing", "significantly",
  "robust", "ensuring reliability", "improving efficiency" are new claims.
You may use the job's name for something the bullet already describes (the bullet
says "Postgres" and the job says "PostgreSQL").
"""


# --- checks ----------------------------------------------------------------------------

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*(?:\s?(?:%|[kmb]\b|x\b))?", re.IGNORECASE)
_NUMBER_WORDS = {
    w: str(i)
    for i, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve".split()
    )
}


def numbers_in(text: str) -> set[str]:
    """Every number written in `text`, normalised: "1,200" → "1200", "60 %" → "60%".
    Number words count too, so rewording "four engineers" as "4 engineers" is fine."""
    found = {re.sub(r"[\s,]", "", m).lower().rstrip(".") for m in _NUMBER.findall(text)}
    for word in re.findall(r"[a-z]+", text.lower()):
        if word in _NUMBER_WORDS:
            found.add(_NUMBER_WORDS[word])
    return found


def new_numbers(new: str, allowed_in: str) -> set[str]:
    allowed = numbers_in(allowed_in)
    # "60%" is supported by "60 percent" or "60"; compare on the digits.
    allowed_digits = {re.sub(r"[^\d.]", "", n) for n in allowed}
    return {
        n
        for n in numbers_in(new)
        if n not in allowed and re.sub(r"[^\d.]", "", n) not in allowed_digits
    }


def new_terms(new: str, allowed_in: str, terms: list[str]) -> list[str]:
    return [t for t in terms if is_written(t, new) and not is_written(t, allowed_in)]


def _too_long(new: str, original: str) -> bool:
    return len(new) > max(len(original) * 1.6, len(original) + 60)


def check_rewording(new: str, original: str, terms: list[str]) -> str | None:
    """Why `new` can't stand in for `original`, or None if it can."""
    if not new.strip():
        return "came back empty"
    if extra := new_numbers(new, original):
        return f"added a number that isn't in your original ({', '.join(sorted(extra))})"
    if extra := new_terms(new, original, terms):
        return f"mentioned {', '.join(extra)}, which this line of yours doesn't"
    if _too_long(new, original):
        return "made it much longer than your original"
    return None


# --- building the resume ---------------------------------------------------------------


def skill_terms(profile: ResumeData, job: dict) -> list[str]:
    """What a line may not name unless its original does: the job's required and
    preferred skills, and the person's own skills, once each ("Go" is often both).
    The job's domain keywords ("payments") aren't here: whether one adds context is
    a judgement about the whole line, which the verifier makes."""
    seen: set[str] = set()
    out = []
    for t in [*job.get("must_have", []), *job.get("nice_to_have", []), *profile.all_skills()]:
        key = normalise(alternatives(t)[0])
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out


def check_summary(
    new: str, profile: ResumeData, terms: list[str], max_chars: int = 600
) -> str | None:
    """Like `check_rewording`, against the whole profile rather than one line. The
    length cap stops a "summary" that is really the profile pasted in."""
    whole = profile_prose(profile)
    if extra := new_numbers(new, whole):
        return f"added a number that isn't in your profile ({', '.join(sorted(extra))})"
    if extra := new_terms(new, whole, terms):
        return f"mentioned {', '.join(extra)}, which isn't in your profile"
    if "\n" in new.strip() or len(new) > max_chars:
        return "wasn't a short summary paragraph"
    return not_resume_voice(new, profile.basics.name)


_PRONOUNS = re.compile(r"\b(?:(?i:he|she|his|her|hers|him|they|their|my|me)|I)\b")


def not_resume_voice(summary: str, name: str) -> str | None:
    """Resume summaries name no one and use no pronouns — and a name says nothing
    about how someone is referred to, so a model must not guess."""
    first = name.strip().split()[0] if name.strip() else ""
    if first and re.search(rf"\b{re.escape(first)}\b", summary, re.IGNORECASE):
        return "used the person's name; resume summaries don't"
    if found := _PRONOUNS.search(summary):
        return f"used “{found.group(0)}”; resume summaries use no pronouns"
    return None


def profile_prose(profile: ResumeData) -> str:
    parts = [profile.basics.headline, profile.summary]
    for e in profile.experience:
        parts += [e.title, *(b.text for b in e.bullets)]
    for p in profile.projects:
        parts += [p.name, *(b.text for b in p.bullets)]
    # Education is fact too: a student's summary leads with their degree and year.
    for ed in profile.education:
        parts += [ed.degree, ed.field, ed.institution, ed.details, ed.start or "", ed.end or ""]
    parts += [f"{c.name} {c.issuer}" for c in profile.certifications]
    parts += profile.all_skills()
    return "\n".join(p for p in parts if p)


class _Builder:
    def __init__(self, profile: ResumeData, job: dict):
        self.profile = profile
        self.terms = skill_terms(profile, job)
        self.provenance: dict[str, dict] = {}

    def record(self, entry_id: str, original: str, attempted: str | None, reason: str | None):
        if attempted is None or attempted.strip() == original:
            status = "kept"
        elif reason:
            status = "reverted"
            log.info("tailor reverted %s: %s", entry_id, reason)
        else:
            status = "reworded"
        self.provenance[entry_id] = {
            "original": original,
            "status": status,
            "attempted": attempted if status == "reverted" else None,
            "reason": reason if status == "reverted" else None,
        }

    def bullets(self, source: list[Bullet], planned: list[PlanBullet] | None) -> list[dict]:
        by_id = {b.id: b for b in source}
        out: list[dict] = []
        seen: set[str] = set()
        for pb in planned or []:
            original = by_id.get(pb.source_id)
            if original is None or pb.source_id in seen:
                continue  # not a bullet of this entry, or used twice
            seen.add(pb.source_id)
            text = pb.text.strip()
            reason = check_rewording(text, original.text, self.terms)
            self.record(original.id, original.text, text, reason)
            out.append({"id": original.id, "text": original.text if reason else text})
        if not out:  # nothing usable came back: the person's own bullets, unchanged
            for b in source:
                self.record(b.id, b.text, None, None)
                out.append({"id": b.id, "text": b.text})
        return out

    def summary(self, planned: str) -> str:
        original = self.profile.summary
        planned = planned.strip()
        if not planned:
            if original:
                self.record("summary", original, None, None)
            return original
        reason = check_summary(planned, self.profile, self.terms)
        self.record("summary", original, planned, reason)
        return original if reason else planned

    def skills(self, planned: list[PlanSkillGroup]) -> list[dict]:
        # Only the profile's own skills, in the profile's own spelling.
        known = {normalise(s): s for s in self.profile.all_skills()}
        used: set[str] = set()
        groups = []
        for g in planned:
            items = []
            for item in g.items:
                key = normalise(alternatives(item)[0])
                if key in known and key not in used:
                    used.add(key)
                    items.append(known[key])
                elif key not in known:
                    log.info("tailor dropped a skill not in the profile: %r", item)
            if items:
                groups.append({"group": g.group.strip()[:200], "items": items[:60]})
        if not groups:
            return [s.model_dump() for s in self.profile.skills]
        # Anything the plan left out goes at the end, so tailoring never deletes a skill.
        rest = [s for s in self.profile.all_skills() if normalise(s) not in used]
        if rest:
            groups.append({"group": "Other", "items": rest})
        return [SkillGroup(**g).model_dump() for g in groups[:20]]


def apply_plan(profile: ResumeData, job: dict, plan: TailorPlan) -> tuple[ResumeData, dict]:
    b = _Builder(profile, job)

    planned_exp = {}
    for entry in plan.experience:
        planned_exp.setdefault(entry.id, entry)
    experience = [
        {
            **e.model_dump(exclude={"bullets"}),
            "bullets": b.bullets(e.bullets, getattr(planned_exp.get(e.id), "bullets", None)),
        }
        for e in profile.experience
    ]

    by_id = {p.id: p for p in profile.projects}
    projects, seen = [], set()
    for entry in plan.projects:
        project = by_id.get(entry.id)
        if project is None or entry.id in seen:
            continue
        seen.add(entry.id)
        projects.append(
            {
                **project.model_dump(exclude={"bullets"}),
                "bullets": b.bullets(project.bullets, entry.bullets),
            }
        )

    content = ResumeData.model_validate(
        {
            "basics": profile.basics.model_dump(),
            "summary": b.summary(plan.summary)[:2000],
            "experience": experience,
            "education": [e.model_dump() for e in profile.education],
            "skills": b.skills(plan.skills),
            "projects": projects,
            "certifications": [c.model_dump() for c in profile.certifications],
        }
    )
    return content, b.provenance


# --- the second check: does a rewording say anything new? -------------------------------
#
# The rules above catch new numbers, tools and padding. They can't catch a new claim
# in plain words ("…on AWS ECS, optimizing job scheduling" — a real model wrote that).
# So every line that survived them is shown, beside its original, to a separate call
# that answers one question. It can only revert; it never approves what the rules
# rejected.


class Verdict(BaseModel):
    id: str
    # First, so the model reasons before it answers. With the boolean first, a real
    # model answered "adds information: true" and then explained that it didn't.
    reasoning: str
    adds_information: bool
    added: str  # what it adds, in a few words; "" if nothing


class Verification(BaseModel):
    verdicts: list[Verdict]


VERIFY_INSTRUCTIONS = """\
You check rewritten resume lines against the person's original wording. For each
item, decide whether REWRITTEN states anything ORIGINAL does not.

It adds information if it introduces any new action, responsibility, result, scope,
tool, number, context or quality claim ("optimizing", "significantly", "robust",
"ensuring reliability", "at scale", "led" when the original says "worked on").
It does not add information if it says the same facts in other words, reorders them,
shortens them, uses a more standard name for the same thing ("Postgres" →
"PostgreSQL"), or names the role's own employer or project given in CONTEXT.
For the summary, ORIGINAL is the whole profile: any fact found anywhere in it is fine.

For each id, first give one or two sentences of reasoning, then the verdict, and in
`added` name what it adds in a few words ("" if nothing). Be strict: if you are
unsure, it adds information.
"""


def verify(
    resume: ResumeData,
    provenance: dict,
    profile: ResumeData,
    provider: AIProvider,
    only: set[str] | None = None,
) -> None:
    """Revert, in place, every reworded line the verifier says adds information
    (just the lines in `only`, when given)."""
    current = {b.id: b for e in [*resume.experience, *resume.projects] for b in e.bullets}
    context = _line_context(profile)
    items = [
        {
            "id": entry_id,
            "context": context.get(entry_id, ""),
            "original": p["original"],
            "rewritten": current[entry_id].text,
        }
        for entry_id, p in provenance.items()
        if p["status"] == "reworded" and entry_id in current and (only is None or entry_id in only)
    ]
    if provenance.get("summary", {}).get("status") == "reworded" and (
        only is None or "summary" in only
    ):
        # Judged against the whole profile: a verifier shown the old summary as
        # ORIGINAL rejects every fact the old summary didn't happen to mention.
        items.append(
            {
                "id": "summary",
                "context": "The summary. ORIGINAL is everything in the person's profile.",
                "original": profile_prose(profile),
                "rewritten": resume.summary,
            }
        )
    for entry_id, added in check_pairs(items, provider).items():
        _revert(resume, provenance, entry_id, f"added something your original doesn't say: {added}")


def check_pairs(items: list[dict], provider: AIProvider) -> dict[str, str]:
    """The second check, for any {id, context, original, rewritten} pairs: id → what
    the rewrite adds, for each one that adds something. A pair with no verdict is
    returned as failing: unchecked isn't approved."""
    if not items:
        return {}
    result = provider.extract(
        task="verify_tailoring",
        instructions=VERIFY_INSTRUCTIONS,
        text=json.dumps(items, ensure_ascii=False),
        schema=Verification,
    )
    flagged = {v.id: v.added for v in result.verdicts if v.adds_information}
    answered = {v.id for v in result.verdicts}
    for item in items:
        if item["id"] not in answered:
            flagged[item["id"]] = "it couldn't be checked"
    return {i["id"]: flagged[i["id"]] for i in items if i["id"] in flagged}


def _line_context(profile: ResumeData) -> dict[str, str]:
    """Where each bullet sits ("Software Engineer at Tradewise", "Project: ledgerkit"),
    so naming the role's own employer or project isn't mistaken for a new fact."""
    out = {}
    for e in profile.experience:
        where = " at ".join(x for x in (e.title, e.company) if x)
        out |= {b.id: f"Role: {where}" for b in e.bullets}
    for p in profile.projects:
        out |= {b.id: f"Project: {p.name}" for b in p.bullets}
    return out


def _revert(resume: ResumeData, provenance: dict, entry_id: str, reason: str) -> None:
    p = provenance[entry_id]
    if entry_id == "summary":
        p["attempted"], resume.summary = resume.summary, p["original"]
    else:
        for entry in [*resume.experience, *resume.projects]:
            for bullet in entry.bullets:
                if bullet.id == entry_id:
                    p["attempted"], bullet.text = bullet.text, p["original"]
    p["status"], p["reason"] = "reverted", reason
    log.info("tailor verifier reverted %s: %s", entry_id, reason)


# --- one more try for what was reverted ----------------------------------------------
#
# Models embellish unevenly from run to run; a line rejected once usually only needs a
# plainer second attempt. Rejected lines go back once, with the reason. New attempts
# face the same rules and the verifier; whatever fails again keeps the original.


class Repair(BaseModel):
    id: str
    text: str


class Repairs(BaseModel):
    lines: list[Repair]


REPAIR_INSTRUCTIONS = """\
These rewordings of resume lines were rejected, each for the reason given. For each
id, write a new version that keeps the job-relevant phrasing but states only what
ORIGINAL states: no new claims, qualities, context, scale, tools or numbers. If you
can't improve on ORIGINAL without adding something, return ORIGINAL unchanged.
For the id "summary", write 2-3 sentences using only FACTS (the person's profile).
"""


def repair(
    resume: ResumeData, provenance: dict, profile: ResumeData, job: dict, provider: AIProvider
) -> None:
    rejected = {k: p for k, p in provenance.items() if p["status"] == "reverted"}
    if not rejected:
        return
    context = _line_context(profile)
    items = [
        {
            "id": k,
            "context": context.get(k, ""),
            "original": p["original"],
            **({"facts": profile_prose(profile)} if k == "summary" else {}),
            "rejected": p["attempted"],
            "why": p["reason"],
        }
        for k, p in rejected.items()
    ]
    result = provider.extract(
        task="repair_tailoring",
        instructions=REPAIR_INSTRUCTIONS,
        text=json.dumps(items, ensure_ascii=False),
        schema=Repairs,
    )
    terms = skill_terms(profile, job)
    retry: set[str] = set()
    lines = {b.id: b for e in [*resume.experience, *resume.projects] for b in e.bullets}
    for line in result.lines:
        p = rejected.get(line.id)
        text = line.text.strip()
        if p is None or text == p["original"]:
            continue
        if line.id == "summary":
            if check_summary(text, profile, terms) is None:
                resume.summary = text
            else:
                continue
        elif line.id in lines and check_rewording(text, p["original"], terms) is None:
            lines[line.id].text = text
        else:
            continue
        p.update(status="reworded", attempted=None, reason=None)
        retry.add(line.id)
    if retry:
        verify(resume, provenance, profile, provider, only=retry)


def _prompt_input(profile: ResumeData, job: dict, job_text: str) -> str:
    lean = profile.model_dump(
        mode="json",
        exclude={"basics": {"email", "phone", "links"}},  # not needed, so not sent
    )
    return json.dumps(
        {
            "job": {
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "must_have": job.get("must_have", []),
                "nice_to_have": job.get("nice_to_have", []),
                "keywords": job.get("keywords", []),
                "posting": job_text[:8000],
            },
            "profile": lean,
        },
        ensure_ascii=False,
    )


def tailor(
    profile: ResumeData, job: dict, job_text: str, provider: AIProvider
) -> tuple[ResumeData, dict]:
    plan = provider.extract(
        task="tailor",
        instructions=INSTRUCTIONS,
        text=_prompt_input(profile, job, job_text),
        schema=TailorPlan,
    )
    resume, provenance = apply_plan(profile, job, plan)
    verify(resume, provenance, profile, provider)
    repair(resume, provenance, profile, job, provider)
    return resume, provenance
