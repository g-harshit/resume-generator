# resume-generator — plan

A website and a Chrome extension that turn a job description into an ATS-friendly
resume, built from a profile the user owns.

- **Website:** the user pastes a job description.
- **Extension:** reads the job description from the page the user is on.
- Both then: pick a template → tailored resume → edit → download PDF / DOCX.
- On first login the user uploads the resume they already have; it becomes their profile.

Product name and domain: **not decided**. The mockups use "Tailor" as a working name —
keep the name in one config value (`APP_NAME`) so renaming is a one-line change.

UI mockups: https://claude.ai/artifact/GTEZFenLX3qkHhDXzDsfg3 (9 screens: upload,
profile review, paste JD, templates, editor, my resumes, extension ×3).

---

## Principles (read before building anything)

1. **Profile vs resume.** The *profile* (one per user) is every true fact about the
   person. A *resume* (one per job) is a **frozen snapshot** selected, reordered and
   reworded from the profile. Editing the profile never changes a resume already made.
2. **Tailoring never invents facts.** The model may select, reorder and rephrase.
   It may not add a skill, employer, date, number or degree that isn't in the profile.
   This is enforced in code (see Phase 7), not only in the prompt. A skill the job wants
   and the profile lacks is shown as a *gap* the user can answer ("I have this").
3. **The user checks the parse.** Parsing is never perfect. Nothing built from a profile
   is trusted until the user has reviewed it once.
4. **One template, two outputs.** The same HTML/CSS template renders the live preview
   and the PDF, so they cannot drift.
5. **ATS rules are tested, not hoped for.** Single column, real text, standard headings,
   contact in the body. A test extracts text from every template's PDF and checks it.
6. **Stable ids on every entry.** Every role, bullet, skill has an `id`, so a tailored
   bullet can always be traced to the profile bullet it came from.

---

## Tech stack

| Layer | Choice |
|---|---|
| Repo | Monorepo, pnpm workspaces |
| Website | Next.js (App Router) + TypeScript + Tailwind |
| Extension | WXT (Manifest V3) + React + TypeScript, Chrome side panel |
| Shared | `packages/schema` (TS types generated from the backend's JSON Schema), `packages/ui` |
| Backend | FastAPI + SQLModel + Alembic, Python 3.12 |
| Database | PostgreSQL (JSONB) — Docker locally, same engine as production |
| File storage | Local disk in dev behind a `Storage` interface; Cloudflare R2 later |
| Text extraction | PyMuPDF (PDF), python-docx (DOCX) |
| AI | Provider interface (`ai_providers/`), one implementation to start; a stub provider for tests |
| PDF | WeasyPrint (HTML/CSS → text PDF) |
| DOCX | python-docx |
| Auth (now) | Email + password, argon2 hashes, JWT bearer token |
| Auth (later) | Google OAuth, matched to existing accounts by verified email |

Why Postgres locally and not SQLite: JSONB, enums and constraints behave differently on
SQLite, and bugs from that gap only show up in production. Dev and tests run on the same
engine as prod from day one.

---

## Repo layout

```
resume-generator/
  plan.md
  CLAUDE.md                 working notes for Claude Code
  docker-compose.yml        postgres for dev + tests
  backend/
    app/
      main.py  config.py  database.py  models.py  schemas/
      routers/     auth.py profile.py uploads.py jobs.py templates.py resumes.py
      services/    storage.py extract.py parse_resume.py parse_jd.py match.py
                   tailor.py render.py export_pdf.py export_docx.py
      ai_providers/  base.py <provider>.py stub.py
      templates/     classic/ modern/ compact/ executive/   (html + css)
    alembic/
    tests/
  apps/
    web/                    Next.js
    extension/              WXT
  packages/
    schema/                 generated TS types for ResumeData, JobDescription...
    ui/                     shared React components (chips, match panel, preview frame)
```

---

## Data model

```
users              id, email (unique), password_hash, name, created_at

source_documents   id, user_id, filename, mime, size_bytes, storage_key,
                   extracted_text, parse_status (pending|done|failed),
                   parsed JSONB, parse_warnings JSONB, created_at

profiles           id, user_id (unique), data JSONB (ResumeData), version int,
                   reviewed_at (null until the user confirms the parse), updated_at

job_descriptions   id, user_id, source (paste|extension), url, company, title,
                   raw_text, parsed JSONB, content_hash, created_at
                   unique (user_id, content_hash)

templates          id, slug (unique), name, description, sort_order, is_active
                   -- html/css live in backend/app/templates/<slug>/; the row controls
                   -- which are offered and in what order

resumes            id, user_id, job_description_id, template_id,
                   content JSONB (ResumeData snapshot), provenance JSONB,
                   match JSONB, profile_version int, title, created_at, updated_at

resume_revisions   id, resume_id, content JSONB, reason (tailor|edit|retailor), created_at
```

Every table with a `user_id` is deleted with its user (a single `cascade_delete` service
+ a test that walks the metadata and fails if a table is missed).

### `ResumeData` (shared by `profiles.data` and `resumes.content`)

Based on the open JSON Resume shape, with an `id` on every entry:

```json
{
  "basics": { "name": "", "headline": "", "email": "", "phone": "", "location": "",
              "links": [ { "id": "", "label": "", "url": "" } ] },
  "summary": "",
  "experience": [
    { "id": "exp_…", "company": "", "title": "", "location": "",
      "start": "2021-03", "end": null,
      "bullets": [ { "id": "b_…", "text": "" } ] }
  ],
  "education":      [ { "id": "", "institution": "", "degree": "", "field": "", "start": "", "end": "" } ],
  "skills":         [ { "id": "", "group": "Languages", "items": [ "Go", "SQL" ] } ],
  "projects":       [ { "id": "", "name": "", "url": "", "bullets": [ { "id": "", "text": "" } ] } ],
  "certifications": [ { "id": "", "name": "", "issuer": "", "date": "" } ]
}
```

Defined once as Pydantic models in `backend/app/schemas/resume.py`; `pnpm gen:schema`
exports JSON Schema and generates `packages/schema` TS types. Never hand-edit the TS.

### `provenance` (on a resume)

Maps each resume entry id → the profile entry id it came from, plus whether its text was
reworded. This is what powers "Reworded for this job · See original · Undo" in the
editor and the no-invention check.

---

## API (v1)

```
POST /auth/register                 email, password, name → token
POST /auth/login                    email, password → token
GET  /auth/me

POST /uploads                       multipart file → source_document (parse starts in background)
GET  /uploads/{id}                  status, parsed, warnings

GET  /profile                       data, version, reviewed_at
PUT  /profile                       full ResumeData (version check → 409 on conflict)
POST /profile/confirm               sets reviewed_at
POST /profile/skills                "I have this": add a skill (+ where it was used)

POST /jobs                          { raw_text, url?, source } → parsed JD + match vs profile
GET  /jobs/{id}

GET  /templates
GET  /templates/{slug}/preview      HTML rendered with the caller's profile

POST /resumes                       { job_id, template_slug } → tailored resume
GET  /resumes                       list
GET  /resumes/{id}
PUT  /resumes/{id}                  save edits (writes a revision)
POST /resumes/{id}/retailor         rebuild from current profile
GET  /resumes/{id}/preview          HTML
GET  /resumes/{id}/pdf
GET  /resumes/{id}/docx
DELETE /resumes/{id}
```

---

## Phases

Each phase ends with passing tests and something runnable. Tick boxes as they land.

### Phase 0 — Repo and local dev
- [x] `git init`
- [x] `.gitignore`, `README.md`, `CLAUDE.md`
- [x] Toolchain: `uv` + Python 3.12 (system Python is 3.9), pnpm via Homebrew
      (`corepack enable` can't write to `/usr/local/bin` on this machine)
- [x] `docker-compose.yml` with Postgres 18 on host port 5433 (`resume` + `resume_test`)
- [x] Backend skeleton: FastAPI app, settings from `.env`, `/health` (touches the DB),
      SQLModel engine, Alembic wired to app settings (`alembic check` clean)
- [x] pytest against the Docker Postgres with a transaction-per-test fixture; refuses any
      database not named `*_test`
- [x] Web skeleton: Next.js 16 + Tailwind 4, design tokens from the mockups in
      `globals.css` (`bg-ground`, `bg-accent`, `text-warn-ink`, …), Instrument Serif +
      IBM Plex Sans; home page shows whether the API is reachable
- [x] pnpm workspace (`apps/*`, `packages/*`) — `packages/schema` and `packages/ui` are
      created when they get content (Phase 2 / when the extension needs shared UI)
- [x] One command to run everything locally: `make dev` (API 8100, web 3100)

### Phase 1 — Email + password auth
- [ ] `users` table + migration
- [ ] argon2 hashing, JWT (short-lived access token), `get_current_user` dependency
- [ ] `/auth/register`, `/auth/login`, `/auth/me`; duplicate email → 409; case-insensitive email
- [ ] Web: `/login`, `/register`, auth context, token in localStorage, protected `/app/*`
- [ ] Only a 401 signs the user out (a network error or 5xx retries instead)
- [ ] Tests: register, login, wrong password, protected route without token

### Phase 2 — Resume schema
- [ ] Pydantic `ResumeData` + id generation helpers
- [ ] JSON Schema export → generated TS types in `packages/schema`
- [ ] Validation tests (dates, required fields, unique ids)

### Phase 3 — Upload and parse the draft resume
- [ ] `Storage` interface; local-disk implementation under `backend/var/uploads`
- [ ] `source_documents` table; `POST /uploads` (PDF/DOCX, ≤ 5 MB, magic-byte check)
- [ ] Text extraction: PyMuPDF with reading-order sorting (handles two-column drafts),
      python-docx for Word
- [ ] AI provider interface + first provider + stub provider
- [ ] `parse_resume`: extracted text → `ResumeData` via schema-constrained output;
      assign ids; collect `parse_warnings` (unreadable dates, missing email/phone, empty sections)
- [ ] Background job with status polling; job own DB session; stale-job timeout
- [ ] Create or update the profile from the parse
- [ ] Web: onboarding upload screen (mockup 1) with progress
- [ ] Fixture resumes in `tests/fixtures/` (one-column PDF, two-column PDF, DOCX) — all invented people

### Phase 4 — Profile review and editing
- [ ] `GET/PUT /profile` with optimistic `version` check
- [ ] Web: review screen (mockup 2) — original file preview beside the parsed form,
      warnings highlighted, "Looks right" → `POST /profile/confirm`
- [ ] Web: full profile editor (add/remove/reorder roles, bullets, skills, education, projects)
- [ ] Autosave with debounce

### Phase 5 — Job description intake and matching
- [ ] `job_descriptions` table; dedupe on `(user_id, content_hash)`
- [ ] `parse_jd`: raw text → title, company, location, seniority, must-have skills,
      nice-to-have skills, keywords
- [ ] `match`: **deterministic** comparison of JD skills/keywords against the profile
      (normalised, with a small synonym table: "Postgres" = "PostgreSQL", "K8s" = "Kubernetes").
      No model here, so the result is explainable and free.
- [ ] Web: paste screen (mockup 3) with parsed chips, covered vs missing

### Phase 6 — Templates and rendering
- [ ] Four templates as Jinja2 HTML + CSS: Classic, Modern, Compact, Executive
- [ ] `templates` table seeded on startup when empty
- [ ] `render`: ResumeData + template → HTML; `/templates/{slug}/preview` with the user's data
- [ ] PDF via WeasyPrint; page-count check (warn when > 1 page for < 10 years' experience)
- [ ] **ATS test**: for every template, render a fixture, extract the PDF text, assert
      reading order, standard headings, contact details present, no text in header/footer
- [ ] Web: template picker (mockup 4) with live previews

### Phase 7 — Tailoring
- [ ] Prompt: profile + parsed JD → selected/reordered/reworded `ResumeData` + provenance
- [ ] **Invention guard** (code, after the model returns):
  - every experience/project/education entry id exists in the profile
  - every bullet has a source bullet id in the profile
  - no skill that isn't in the profile
  - no number in a reworded bullet that isn't in its source bullet
  - violations are dropped/reverted to the source text and logged, never shown as-is
- [ ] Summary may be rewritten, but only from facts in the profile (same number check)
- [ ] `POST /resumes` stores snapshot + provenance + match + first revision
- [ ] Tests with the stub provider, including a stub that tries to invent a skill

### Phase 8 — Editor
- [ ] Web: three-pane editor (mockup 5)
  - left: sections, include/exclude per bullet, reorder, edit text, "See original" / "Undo"
  - middle: live preview (server-rendered HTML in an iframe)
  - right: match panel, gaps with "I have this", ATS checks
- [ ] "I have this" → asks where it was used → saves to the profile → offers to re-tailor
- [ ] Template switcher; autosave writes a revision
- [ ] Download PDF and DOCX

### Phase 9 — DOCX export
- [ ] python-docx builder per template (same section order, real headings, no tables)
- [ ] Test: open the DOCX, check headings and text order

### Phase 10 — My resumes
- [ ] Web: list (mockup 6) — job, company, template, match, source, updated
- [ ] Open, download, duplicate, re-tailor, delete
- [ ] Profile card with outstanding warnings (e.g. missing phone)

### Phase 11 — Chrome extension
- [ ] WXT app in `apps/extension`, side panel, permissions: `activeTab`, `scripting`,
      `sidePanel`, `storage` only (no all-sites host permission)
- [ ] JD extraction, in order: JSON-LD `JobPosting` → site-specific selectors
      (LinkedIn, Naukri, Indeed, Greenhouse, Lever, Workday) → readable main text →
      "Use my selection"
- [ ] Auth handoff: sign-in opens the website; the site sends the token to the extension
      via `externally_connectable` + `chrome.runtime.sendMessage`
- [ ] Screens: signed out, job detected, resume ready (mockups 7–9)
- [ ] CORS for the extension origin on the API
- [ ] Load unpacked locally; Chrome Web Store listing comes later

### Later (not in the first build)
- [ ] Google OAuth login (email + password stays as the fallback)
- [ ] Credits and payments (if we monetise that way) — every paid action must store its
      result so a refresh never charges twice
- [ ] Deploy (API, web, Postgres, R2), domain, name
- [ ] Public landing page
- [ ] Cover letter from the same profile + JD
- [ ] Rate limiting on auth and AI endpoints, email verification, password reset

---

## Open decisions

| Decision | Status |
|---|---|
| Product name + domain | Later |
| AI provider and models (parse / tailor) | Pick in Phase 3; behind the provider interface either way |
| Monetisation (credits vs free with limits) | Later |
| Hosting | Later; local only for now |

---

## Running locally

See [README.md](README.md): `make dev` after `pnpm install` and `uv sync`.
