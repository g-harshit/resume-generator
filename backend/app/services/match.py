"""Which of a job's skills does the profile show? Plain code, no model.

Deterministic on purpose: the answer has to be explainable ("found in your Paylane
bullets"), identical every time, and free to recompute whenever the profile changes.

A term counts as covered when the profile lists it as a skill, or when it appears in
the profile's own prose (headline, summary, titles, bullets). Variants are folded
together by `SYNONYMS` ("Postgres" = "PostgreSQL", "K8s" = "Kubernetes").
"""

import re
from dataclasses import asdict, dataclass, field

from app.schemas.resume import ResumeData

# Each group is one skill; the first spelling is how we display it.
_SYNONYM_GROUPS: list[tuple[str, ...]] = [
    ("PostgreSQL", "postgres", "psql", "postgre sql"),
    ("Kubernetes", "k8s", "kube"),
    ("JavaScript", "js", "ecmascript"),
    ("TypeScript", "ts"),
    ("Node.js", "nodejs", "node js", "node"),
    ("React", "react.js", "reactjs"),
    ("Next.js", "nextjs", "next js"),
    ("Vue", "vue.js", "vuejs"),
    ("Angular", "angularjs", "angular.js"),
    ("Go", "golang"),
    ("Python", "python3"),
    ("C++", "cpp"),
    ("C#", "csharp", "c sharp"),
    (".NET", "dotnet", "dot net"),
    ("AWS", "amazon web services"),
    ("GCP", "google cloud", "google cloud platform"),
    ("Azure", "microsoft azure"),
    ("CI/CD", "cicd", "ci cd", "continuous integration"),
    ("REST", "rest api", "rest apis", "restful", "restful api", "restful apis"),
    ("GraphQL", "graph ql"),
    ("gRPC", "grpc"),
    ("Machine learning", "ml"),
    ("Natural language processing", "nlp"),
    ("Large language models", "llm", "llms"),
    ("MongoDB", "mongo"),
    ("Elasticsearch", "elastic search", "elastic"),
    ("Terraform", "tf"),
    ("Docker",),
    ("Microservices", "micro services", "microservice"),
    ("Distributed systems", "distributed system"),
    ("Spring Boot", "springboot", "spring-boot"),
    ("SQL", "structured query language"),
    ("Git", "github", "gitlab"),
    ("Linux", "unix"),
]

_CANONICAL: dict[str, str] = {}
for _group in _SYNONYM_GROUPS:
    for _spelling in _group:
        _CANONICAL[_spelling.lower()] = _group[0].lower()

# Also ordinary English words. In prose they only count when written exactly as the
# technology is ("Go", "REST", "React"), so "go to market" or "Rest of the team" isn't
# a skill. In a skills list any casing counts.
_AMBIGUOUS: dict[str, tuple[str, ...]] = {
    "go": ("Go",), "r": ("R",), "c": ("C",), "rest": ("REST",), "react": ("React",),
    "spring": ("Spring",), "swift": ("Swift",), "express": ("Express", "Express.js"),
    "ember": ("Ember",), "dart": ("Dart",), "make": ("Make",), "chef": ("Chef",),
    "puppet": ("Puppet",), "salt": ("Salt", "SaltStack"), "flask": ("Flask",),
    "rails": ("Rails",), "next": ("Next",), "node": ("Node",), "elastic": ("Elastic",),
    "tf": ("TF",), "ts": ("TS",), "js": ("JS",), "ml": ("ML",), "kube": ("Kube",),
}  # fmt: skip

# Technologies we know by name: what a generated line may not mention unless its
# source does.
KNOWN_SKILLS: list[str] = list(
    dict.fromkeys(
        [group[0] for group in _SYNONYM_GROUPS]
        # Not the ones a sentence can start with ("Make", "Next").
        + [
            names[0]
            for key, names in _AMBIGUOUS.items()
            if len(key) > 2 and key not in {"make", "next", "salt", "chef", "node", "kube"}
        ]
    )
)


def normalise(term: str) -> str:
    t = re.sub(r"\s+", " ", term.strip().lower()).strip(" .,;:")
    return _CANONICAL.get(t, t)


def alternatives(term: str) -> list[str]:
    """ "Kubernetes (K8s)" → ["Kubernetes", "K8s"]: a model often adds the other name
    in brackets. The first is the one to display."""
    parts = [p.strip() for p in re.split(r"[()]", term) if p.strip()]
    return parts or [term.strip()]


def _number_forms(spelling: str) -> list[str]:
    """ "payments" also matches "payment", and "ledger" matches "ledgers": on the last
    word only, and not on short or ambiguous terms ("Go" is not "Gos")."""
    *head, last = spelling.split(" ")
    if len(last) < 4 or spelling in _AMBIGUOUS or not last.isalpha():
        return [spelling]
    other = last[:-1] if last.endswith("s") and not last.endswith("ss") else last + "s"
    return [spelling, " ".join([*head, other])]


def _spellings(canonical: str) -> list[str]:
    """Every way of writing a canonical skill, singular and plural."""
    names = [s.lower() for g in _SYNONYM_GROUPS if g[0].lower() == canonical for s in g]
    return [form for name in names or [canonical] for form in _number_forms(name)]


def mentioned_casually(term: str, text: str) -> bool:
    """Is `term` named in `text`, in any casing? For the person's own notes ("built it
    in react"), where the strict prose rule for ambiguous words would miss it."""
    lower = text.lower()
    return any(
        re.search(rf"(?<![\w.+#]){re.escape(form)}(?![\w+#])", lower)
        for alt in alternatives(term)
        for form in _spellings(normalise(alt))
    )


def _display(term: str) -> str:
    canonical = normalise(term)
    for g in _SYNONYM_GROUPS:
        if g[0].lower() == canonical:
            return g[0]
    return term.strip()


def _in_prose(spelling: str, text: str, text_lower: str) -> bool:
    # Whole words only, and tolerant of the punctuation in "C++", "C#", ".NET", "CI/CD".
    def word(s: str) -> str:
        return rf"(?<![\w+#.]){re.escape(s)}(?![\w+#])"

    if spelling in _AMBIGUOUS:
        return any(re.search(word(form), text) for form in _AMBIGUOUS[spelling])
    return re.search(word(spelling), text_lower) is not None


@dataclass
class Evidence:
    section: str  # "skills" | "experience" | "projects" | "summary" | "headline"
    label: str  # what to show: "Skills", "Paylane", "ledgerkit"
    id: str | None = None  # the entry, so the UI can point at it


@dataclass
class TermMatch:
    term: str
    covered: bool
    where: list[Evidence] = field(default_factory=list)


class _ProfileIndex:
    def __init__(self, profile: ResumeData):
        self.skills = {normalise(s) for s in profile.all_skills()}
        # (evidence, original text) for everything the person wrote in prose.
        self.prose: list[tuple[Evidence, str]] = []
        if profile.basics.headline:
            self.prose.append((Evidence("headline", "Job title"), profile.basics.headline))
        if profile.summary:
            self.prose.append((Evidence("summary", "Summary"), profile.summary))
        for e in profile.experience:
            text = " ".join([e.title, *(b.text for b in e.bullets)])
            self.prose.append((Evidence("experience", e.company or e.title, e.id), text))
        for p in profile.projects:
            text = " ".join([p.name, *(b.text for b in p.bullets)])
            self.prose.append((Evidence("projects", p.name, p.id), text))

    def find(self, term: str) -> TermMatch:
        canonicals = {normalise(a) for a in alternatives(term)}
        spellings = [s for c in canonicals for s in _spellings(c)]
        where: list[Evidence] = []
        if canonicals & self.skills:
            where.append(Evidence("skills", "Skills"))
        for evidence, text in self.prose:
            lower = text.lower()
            # `names` too: "ecommerce" for "e-commerce", "backend" for "Backend
            # development" — the same test the editor uses when it rewrites a line.
            if any(_in_prose(s, text, lower) for s in spellings) or names(term, text):
                where.append(evidence)
        return TermMatch(_display(alternatives(term)[0]), bool(where), where)


def _unique(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for t in terms:
        key = normalise(alternatives(t)[0])
        if key and key not in seen:
            seen.add(key)
            out.append(t)
    return out


def match(profile: ResumeData, must_have: list[str], nice_to_have: list[str], keywords: list[str]):
    """Coverage of each list, in the job's order. A term in more than one list is
    counted in the first (must-have beats nice-to-have beats keyword)."""
    index = _ProfileIndex(profile)
    must = _unique(must_have)

    def key(t: str) -> str:
        return normalise(alternatives(t)[0])

    taken = {key(t) for t in must}
    nice = [t for t in _unique(nice_to_have) if key(t) not in taken]
    taken |= {key(t) for t in nice}
    keys = [t for t in _unique(keywords) if key(t) not in taken]

    result = {
        "must_have": [index.find(t) for t in must],
        "nice_to_have": [index.find(t) for t in nice],
        "keywords": [index.find(t) for t in keys],
    }
    scored = result["must_have"] + result["nice_to_have"]
    return {
        **result,
        "covered": sum(m.covered for m in scored),
        "total": len(scored),
    }


def appears_in(term: str, text: str) -> bool:
    """Is `term` (or a synonym) actually written in `text`? Used to drop requirements
    a model inferred rather than read."""
    lower = text.lower()
    return any(_in_prose(s, text, lower) for s in _spellings(normalise(term)))


def match_job(data: ResumeData, parsed_job: dict) -> dict:
    """`match` for a stored job, as plain JSON (for API responses)."""
    result = match(
        data,
        parsed_job.get("must_have", []),
        parsed_job.get("nice_to_have", []),
        parsed_job.get("keywords", []),
    )
    return {
        key: [asdict(m) for m in value] if isinstance(value, list) else value
        for key, value in result.items()
    }


# "Backend development" is named by "backend", "Distributed systems" by "distributed";
# "System design" isn't named by "system".
_GENERIC = {"systems", "system", "development", "engineering", "services", "experience"}


def names(term: str, text: str) -> bool:
    """Does `text` name `term`, a synonym of it, or (for a phrase like "Backend
    development") the phrase without its generic last word ("backend")?
    "High-throughput", "high throughput" and "highthroughput" are the same."""
    if any(appears_in(a, text) for a in alternatives(term)):
        return True
    flat_term, flat_text = term.replace("-", " "), text.replace("-", " ")
    if (flat_term, flat_text) != (term, text) and appears_in(flat_term, flat_text):
        return True
    if "-" in term and appears_in(term.replace("-", ""), text):  # "ecommerce"
        return True
    words = re.findall(r"[\w+#./]+", flat_term.lower())
    core = list(words)
    while len(core) > 1 and core[-1] in _GENERIC:
        core.pop()
    return core != words and appears_in(" ".join(core), flat_text)
