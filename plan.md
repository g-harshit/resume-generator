# resume-generator — plan

A website and a Chrome extension that turn a job description into an ATS-friendly
resume, built from a profile the user owns.

- **Website:** the user pastes a job description.
- **Extension:** reads the job description from the page the user is on.
- Both then: pick a template → tailored resume → edit → download PDF.
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
                   tailor.py render.py export_pdf.py
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
- [x] `users` table + migration `0001` (email stored lower-cased, unique index)
- [x] argon2 hashing, JWT, `CurrentUser` dependency (`app/auth.py`)
  - A login lasts `ACCESS_TOKEN_DAYS` (7). There is no refresh token yet, so "short-lived"
    would mean signing people out constantly; revisit when adding refresh/revocation.
  - `JWT_SECRET` must be set and ≥ 32 bytes outside development — the app refuses to start.
  - Unknown email and wrong password return the same 401 and do the same hashing work,
    so neither the message nor the timing tells an attacker which emails have accounts.
- [x] `/auth/register`, `/auth/login`, `/auth/me`; duplicate email → 409 (also under a
      concurrent double sign-up); case-insensitive, trimmed email
- [x] Web: `/login`, `/register` (shared `AuthForm`), `AuthProvider`/`useAuth`, token in
      localStorage, `/app/*` redirects to `/login?next=…`; `next` only accepts same-site paths
- [x] Only a 401 signs the user out (a network error or 5xx retries `/auth/me` for a minute)
- [x] Tests (16): register, hashing, case-insensitive email, duplicates, validation, login,
      wrong password vs unknown email, missing/garbage/expired/forged tokens, deleted
      account, production secret guard
- [x] Checked in the browser: sign up → `/app`, reload stays signed in, sign out → `/app`
      bounces to login, wrong password shows the error, sign in returns to `/app`,
      phone-width layout

### Phase 2 — Resume schema
- [x] Pydantic `ResumeData` (`app/schemas/resume.py`); ids generated by `default_factory`
      so anything built without one gets one, and never rewritten after
  - Dates are `YYYY` or `YYYY-MM`; an unreadable date is `null`, never a guess
  - `Experience.current` separates "still here" from "end date unknown" (both `end: null`)
  - `extra="forbid"`, trimmed strings, length caps on every text and list
- [x] JSON Schema export → generated TS types in `packages/schema` (`pnpm gen:schema`);
      a test fails if the committed schema is stale
- [x] Validation tests (dates, date order, current roles, unique ids, unknown fields, caps)

### Phase 3 — Upload and parse the draft resume
- [x] `Storage` interface; local-disk implementation under `backend/var/uploads` (random
      file names; the user's filename never touches the disk)
- [x] `source_documents` + `profiles` tables (migration `0002`, both `ON DELETE CASCADE`
      from users; `tests/test_models.py` fails if a future user-owned table forgets)
- [x] `POST /uploads`: PDF/DOCX decided from the bytes, ≤ 5 MB, 20 uploads/user/day
      (each is a paid model call); `GET /uploads/{id}`, `/file` (the original), `/apply`
- [x] Text extraction (`services/extract.py`): PyMuPDF with column detection — columns
      found by left edge, a side column must hold ≥ 15% of the text (so right-aligned
      dates stay with their role), full-width blocks (≥ 75% of the page) split segments;
      python-docx including the page header (where contact details often live) and tables.
      Scanned / password-protected / damaged files fail with a message saying what to do.
- [x] AI provider interface (`ai_providers/`), **OpenAI** (Responses API structured output,
      `store=False`, model = `OPENAI_PARSE_MODEL`, default `gpt-4o-mini`) + stub for tests
- [x] `parse_resume`: the model fills a plain schema; code validates dates (unreadable →
      null + warning, never guessed), resolves current/end conflicts, dedupes skills,
      and **flags any bullet or summary it can't find in the file** (the model is told
      to copy, and this checks it did)
- [x] Background job (FastAPI BackgroundTasks) with its own session; stale after 10 min
- [x] Profile created from the first parse; a new upload replaces an *unreviewed* profile
      but never a reviewed one unless the user asks (`/apply`)
- [x] Web: upload screen (mockup 1) with drag-and-drop, progress while reading, errors,
      "what we read" summary and "things to check"
- [x] Fixture resumes built in code (`tests/fixtures.py`: two-column PDF, dated one-column
      PDF, blank PDF, DOCX with header + table) — all invented people
- [x] Checked in the browser: upload → reading → clear failure without an API key; the
      "what we read" screen with warnings. **Not yet run against the real OpenAI API**
      (needs `OPENAI_API_KEY` in `backend/.env`).
- Found on the way: a form submitted before the page's JavaScript loaded did a native
  GET and put the password in the URL. Auth forms are now `method="post"`.
- `SessionDep` closes the session when the handler returns (`scope="function"`), so a
  background job never runs inside a request's transaction.

### Phase 4 — Profile review and editing
- [x] `GET/PUT /profile` with optimistic `version` check — one compare-and-set UPDATE, so
      two tabs can't both win; a stale version gets 409 and the UI offers a reload.
      `version: 0` creates a profile from scratch (no upload).
- [x] `POST /profile/confirm` (needs the latest version and no *blocking* check: a name,
      each role a title or company, …); `GET /uploads/{id}/text` for Word files
- [x] Two kinds of "things to check", both pointing at an entry **by id** (positions go
      stale the moment a role is moved):
  - **checks** (`services/profile_checks.py`): what's missing *now*, recomputed on every
    save, so they vanish when fixed
  - **notes**: what only the parse knows (a date it couldn't read, quoting it; a line not
    found in the file; what the model couldn't place). Shown until the profile is
    confirmed; a date note settles once that date has a value. Where a note and a check
    are about the same field, only the note shows (`toShow` in `lib/notes.ts`).
- [x] Web: review screen (mockup 2) at `/app/profile` — the original beside the form
      (PDF as-is; Word as the text we read), issues under the field they're about,
      "Looks right — save my profile" → confirm
- [x] Web: full editor — every section; add / remove / reorder (up/down buttons, not
      drag, so it works by keyboard) roles, lines, links, education, skill groups,
      projects, certifications; skills as chips (Enter or comma; pasting "Go, SQL" adds
      both); dates as month (optional) + year, so year-only education works
- [x] Autosave 800 ms after the last edit; saves never overlap and always send the latest;
      a warning on closing the tab with unsaved edits
- [x] Checked in the browser with a real OpenAI parse: the "“21”" note beside Tradewise's
      end date, fixed by entering Feb 2021 (saved, note gone), a skill added, confirmed,
      home shows "Your profile is ready"; phone width has no sideways scroll

### Phase 5 — Job description intake and matching
- [x] `job_descriptions` table (migration `0003`); unique `(user_id, content_hash)` — the
      hash is of whitespace-normalised, lower-cased text, so re-pasting the same posting
      returns the first reading with no second model call
- [x] `POST /jobs` (synchronous, a few seconds: the page and the extension want the answer
      at once; 200–30,000 chars; 50/user/day), `GET /jobs/{id}`
- [x] `parse_job` (`services/jobs.py`): title, company, location, seniority (as written),
      must-have, nice-to-have, keywords. **Every term must be written in the posting**
      (`is_written`) — a model adding "Docker" to a job that never says it is dropped.
      Tolerant of phrasing: "Kubernetes (K8s)" when the posting says K8s.
- [x] `match` (`services/match.py`): deterministic, free, recomputed on every read so it
      follows the profile. Covered = listed in skills or written in the profile's prose,
      and it says where ("Paylane", "Summary"). Synonym table (Postgres/PostgreSQL,
      K8s/Kubernetes, golang/Go…), singular/plural ("payments" ↔ "payment systems"),
      bracketed alternatives. Words that are also English ("Go", "REST", "React") count
      in prose only when written as the technology — "go to market" isn't Go.
- [x] Web: `/app/new` (mockup 3) — paste, "Read the job", chips (✓ covered, dashed
      missing, with where-found for screen readers and on hover), "covers X of Y";
      `?job=` keeps the result across a refresh. "Choose a template" waits for Phase 6.
- [x] Checked against the real OpenAI API: on the Northwind posting it added nothing that
      wasn't written; in the browser, 5 of 9 covered, each correct (after fixing the
      plural miss it caught on "payments").
- Not built (mockup 3 showed it): editing the extracted chips by hand. Add if the model
  turns out to misread postings in practice.

### Phase 6 — Templates and rendering
- [x] Four templates — Classic, Modern, Compact, Executive — as **one** Jinja2 structure
      (`rendering/templates/resume.html.j2`) and a stylesheet each. The ATS-critical
      things (single column, real text, standard headings, contact in the body, reading
      order) live in the shared HTML, so a new look can't break them.
- [x] ~~`templates` table~~ — a code registry instead (`rendering/catalog.py`). The HTML
      and CSS are code anyway, so a new template needs a deploy regardless; a table would
      only have toggled visibility. Revisit if templates become user- or admin-made.
- [x] `render_html` (autoescaped; only http(s) links are clickable, `javascript:` stays
      text) and `render_pdf` (WeasyPrint, with a URL fetcher that refuses everything, so
      user text can never make the server fetch an address). Same HTML for both.
- [x] `GET /templates`, `/templates/{slug}/preview` (HTML + page count from the real PDF
      layout), `/templates/{slug}/pdf` (the profile as a PDF; `X-Page-Count`)
- [x] **ATS test** (`tests/test_rendering.py`), for every template: text extracts in
      reading order (contact → headings in order → each role's title before its dates),
      every bullet is one unbroken string, nothing in the top/bottom 10 mm (no running
      header/footer), fonts embedded, the template's own font is the one used, user text
      escaped, only http(s)/mailto links
- [x] Web: `/app/templates` (mockup 4) — live previews of the user's own profile in a
      sandboxed iframe (the same HTML as the PDF), page-count badge when > 1, full-size
      view of the selected one, Download PDF. "Tailor my resume" waits for Phase 7.
- Found while checking the rendered PDFs: Jinja autoescaped the stylesheets, turning
  `"Helvetica Neue"` into `&#34;Helvetica Neue&#34;`; browsers and WeasyPrint dropped the
  rule and three of four templates silently rendered in Times. Now covered by a test.
- Environment: WeasyPrint needs Pango (`brew install pango`; `render.py` points macOS at
  Homebrew's lib folder itself). Fonts are the system's Georgia / Helvetica / Arial —
  **a Linux server needs these or metric-compatible ones (or bundle OFL fonts) before
  deploying**, and the font test will say so. Paper is A4 only for now.

### Phase 7 — Tailoring
- [x] The model returns a **plan that points at the profile by id** (which bullets per
      role, their order and wording; a summary; skill order), never a resume.
      `apply_plan` builds the resume from the profile: names, titles, employers, dates,
      education and certifications are always copied; every role stays, in order.
- [x] **Invention guard, rules** (`services/tailor.py`), per reworded line:
  - the bullet must come from a bullet of the **same** role/project (moving an
    achievement between jobs is refused); unknown ids ignored; a role never ends empty
  - no number its original doesn't have (number words count: "four" = "4")
  - no skill — job must-have/nice-to-have or the person's own — its original doesn't
    name (that's how Kafka gets "tailored" onto the wrong job). Domain keywords
    ("payments") are left to the verifier.
  - not much longer than the original
  - skills only from the profile, in the profile's spelling; none silently dropped
  - summary: same number and skill checks against the whole profile; one paragraph
- [x] **Invention guard, verifier**: a separate call sees each surviving rewording beside
      its original (with its role/project as context) and answers "does it state
      anything the original doesn't?" — reasoning first, then the verdict. It can only
      revert. Added because a real model wrote "…on AWS ECS, optimizing job scheduling",
      which no rule can catch.
- [x] **One repair round**: reverted lines go back once with the reason; new attempts
      face the rules and the verifier again; whatever fails keeps the original.
- [x] Provenance per line: `kept | reworded | reverted`, with the original, and for a
      revert what the model tried and why — shown on the resume page
- [x] `POST /resumes` (needs a **confirmed** profile; 30/day) stores the snapshot,
      provenance, profile version and the first revision; `GET /resumes`, `/{id}`,
      `/{id}/preview?template=`, `/{id}/pdf?template=`. Match is recomputed against the
      resume's own content.
- [x] Tests with the stub (`tests/test_tailor.py`): each kind of invention a model might
      try — new number, job skill slipped in, skill moved between jobs, foreign or made-up
      bullet ids, embellishment, invented skills, invented summary facts, a summary that's
      a dump of the whole profile — plus the verifier and repair rounds
- [x] Web: "Tailor my resume" on the template page → `/app/resume?id=` (preview, template
      switch, PDF, job match with honest gaps, "What we changed" with originals and the
      reasons for anything kept); `/app/resumes` list
- Model choice, from real runs on the same profile and job: `gpt-4o-mini` embellished 6
  of 7 lines (all reverted, tailoring nearly a no-op); `gpt-4.1` reworded cleanly. Default
  `OPENAI_TAILOR_MODEL=gpt-4.1` (tailor, verify, repair; ~1¢ per resume), low temperature.
- Found in real runs and fixed: the verifier answering "true" then explaining "false"
  (verdict before reasoning); the verifier rejecting summary facts because it compared
  against the old summary rather than the profile; the repair round turning the summary
  into a dump of the whole profile.
- Honest limit: with conservative instructions, well-written bullets often come back
  unchanged; tailoring is then mostly choosing, ordering, the summary and skill order.
  That's the intended trade-off for "never invent"; revisit with real users' resumes.
- Tailoring is synchronous (~20–40 s). Move to a background job if it proves too slow.

### Phase 8 — Editor
- [x] Web: three-pane editor at `/app/resume?id=` (mockup 5)
  - left: summary; per role, **every line from the profile** — ticked ones in the
    resume (edit, reorder, untick), unticked ones "left out for this job" (tick to
    add back); projects and skills the same way. Each changed line shows "Reworded for
    this job" / "Edited" with **See original** and **Use original**. Names, titles,
    employers, dates and education are read-only here: they're facts and live in the
    profile.
  - middle: live preview, re-rendered from what's saved after each autosave
  - right: job match (ring, covered, missing with **I have this**), ATS checks (contact
    in body, every role dated, every role has a line, page count)
- [x] **I have this** → "Where did you use it?" (a role, a project, or just the skills
      list) → for a role, the person writes the line themselves → `POST /profile/skills`
      saves skill + line to the profile (row-locked), and the editor adds the same line
      (same id) to this resume. Nothing inferred, nothing generated.
- [x] **Re-tailor** (`POST /resumes/{id}/retailor`): rebuilds from the profile as it is
      now, after a confirm (it replaces this resume's edits; the old version stays in its
      history). Compare-and-set against the version it started from, so an autosave during
      the 20-40 s model call is never thrown away (409 instead). Counts towards the daily
      cap, which now counts tailoring runs rather than resumes.
- [x] Template switcher; `PUT /resumes/{id}` with optimistic `version` (migration `0005`).
      Autosave writes a revision, but saves within 10 minutes of the last *edit* revision
      update it instead, so typing doesn't create hundreds of rows.
- [x] Autosave extracted to `lib/use-autosave.ts`; the profile editor and the resume
      editor share it (debounce, no overlapping saves, latest-data-wins, 409 → conflict)
- [x] Download PDF (saves pending edits first). No DOCX export (Phase 9, skipped).
- [x] Checked in the browser: ticked a left-out line (saved), "I have this" for
      Kubernetes with a line under Paylane (profile and resume both updated, match 6/9 →
      7/9), "Use original" on the summary, preview following each save; the profile
      editor still autosaves on the shared hook.

### Phase 9 — DOCX export — **skipped** (decided 2026-10-02)
Not needed: resumes download as PDF only. Word files are still accepted as *uploads*
(Phase 3); this was only about exporting. Revisit if users or ATS portals ask for .docx.

### Phase 10 — My resumes
- [x] Web: `/app/resumes` (mockup 6) — job (the resume's own title, so a copy reads
      "(copy)"), company, template, keyword match, source (pasted / extension), updated
- [x] Open, PDF, Duplicate (`POST /resumes/{id}/duplicate`: no model call, so not in the
      daily cap; revision reason `copy`), Re-tailor, Delete (`DELETE /resumes/{id}`, with
      an inline confirm; revisions go with it, the job stays)
- [x] Profile card: counts, last updated, "not confirmed yet", and what's left to check
- [x] Checked in the browser: list, duplicate (opens the copy), delete with confirm

### Phase 11 — Chrome extension
- [x] WXT (React, MV3) app in `apps/extension`, side panel. Permissions: `sidePanel`,
      `storage`, `activeTab`, `scripting` — **no host permissions up front**. activeTab
      covers the tab where the icon was clicked; other sites are asked for per site
      (`optional_host_permissions`) when the person clicks "Allow on this site".
- [x] JD extraction (`lib/extract.ts`, injected with `scripting.executeScript`, so
      self-contained), in order: JSON-LD `JobPosting` (incl. `@graph`, malformed JSON
      skipped) → site containers (LinkedIn, Naukri, Indeed, Greenhouse, Lever, Workday) →
      the page's main job-like text block (not the whole page) → "Use my selection".
      vitest + jsdom tests for each path.
- [x] Auth handoff: "Sign in" opens the website's `/extension/connect`, which (after
      login) sends the token with `chrome.runtime.sendMessage(EXTENSION_ID, …)`. Only our
      website's origin may send (`externally_connectable`, and checked again in the
      background script); the token lives in `chrome.storage.local`; a 401 signs the
      extension out. The page says plainly when the extension isn't installed.
- [x] Fixed extension ID `pjddbiflcebndfljpckcgkigckfpmndm` from a public key in the
      manifest (the private key was never kept: not needed in dev, and the Web Store signs
      published builds itself). The API's CORS allows that origin.
- [x] Screens (mockups 7–9): signed out; job found (title, company, a snippet, "Use my
      selection", template choice, "Tailor my resume"); resume ready (match, skills not in
      the profile, Download PDF, Open in editor). Follows the person across tabs.
- [x] `make extension` builds to `apps/extension/.output/chrome-mv3`; README says how to
      load it unpacked. `make lint` / `make test` include the extension.
- **Not yet tried in a real Chrome** — the built-in browser can't load extensions. Needs
  someone to load it unpacked and run it on real LinkedIn / Naukri / company pages.
- Chrome Web Store listing: later (needs a developer account, name, icon, privacy policy).

### Later (not in the first build)
- [x] Google sign-in (email + password stays). Google Identity Services button on
      sign-in and sign-up; Google hands the browser a signed ID token and `POST
      /auth/google` checks it against Google's published keys (signature, our client ID,
      issuer, expiry, verified email) — only a client ID is needed, no secret. Accounts:
      found by Google's stable `sub`; else linked by email (if that address was never
      verified, its password is removed and its sessions ended, since whoever set it may
      not own the inbox); else created without a password. A password login on a
      Google-only account says to use Google; "Forgot password" can add one. Google
      Cloud project `quickfit-cv`, web client for https://quickfitcv.com and
      http://localhost:3100. `/privacy` and `/terms` pages (needed to publish the app).
- [ ] Credits and payments (if we monetise that way) — every paid action must store its
      result so a refresh never charges twice
- [x] Deploy (API, web, Postgres, R2), domain, name — **live at https://quickfitcv.com** (2026-10-03). Domain: **quickfitcv.com**.
      Postgres: **Supabase** (Postgres 17 — the whole suite and every migration checked on
      17). Connect through the **Session pooler** URI (IPv4; the direct host is IPv6-only
      on the free plan, which Render can't reach), with `sslmode=require`; pool capped at
      5 + 5 (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`). Migration 0009 locks every table away
      from Supabase's public Data API (RLS on, no grants for `anon`/`authenticated`) —
      checked against simulated Supabase roles: anon gets "permission denied".
      **Chosen instead: Aiven** (Postgres 18.6, DigitalOcean Bangalore, 15 connections) —
      migrations applied, schema clean. **R2** bucket `quickfitcv-uploads`, private,
      checked end to end. **Render** (`render.yaml`): `quickfitcv-web` static site (Next
      `output: "export"`, `trailingSlash`, a rewrite per page for slash-less links) on
      quickfitcv.com + www; `quickfitcv-api` Docker on the free plan in Singapore at
      api.quickfitcv.com, migrations on start, non-root. Server fonts: Gelasio (bundled,
      OFL) for Georgia, Liberation Sans for Helvetica/Arial — same widths, so all 12
      page counts checked match the Mac. The production image was run against Aiven + R2
      (health, upload → R2 → download), and the static build clicked through.
      Extension: `pnpm zip:extension:prod` → the Chrome Web Store zip.
      DNS at GoDaddy: A `@` → 216.24.57.1, CNAME `www` → quickfitcv-web.onrender.com,
      CNAME `api` → quickfitcv-api.onrender.com; Render certificates on all three.
      Render isn't linked to the GitHub account, so **pushes don't deploy**: use the
      Blueprint's "Manual sync" (or link GitHub in Render). Render's free workspace allows
      2 custom domains per service. The first build failed on `corepack enable`
      (read-only /usr/bin on Render) — removed; Render installs pnpm itself.
      Still for the owner: rotate the keys pasted in chat (OpenAI, Aiven, R2) and update
      them in Render; Chrome Web Store listing (needs a privacy policy); SMTP (Resend)
      for reset emails; the $7 API plan once real users arrive (free sleeps).
- [x] Public landing page (`/`): hero with a stylised match + "what changed" view, how it
      works, "It never makes things up" with **real** rewordings the guard rejected in
      testing, ATS templates, honest gaps / "I have this", FAQ. Claims only what ships:
      the extension is "coming to the Chrome Web Store", no pricing (undecided).
      `robots.txt` (keeps `/app` out) and `sitemap.xml`; `NEXT_PUBLIC_SITE_URL` for deploys.
- [ ] Privacy policy and terms — needed before launch; their content is a decision for
      the owner (what's collected, OpenAI as a processor, retention, jurisdiction).
- [x] Cover letter from the resume + JD (`services/cover_letter.py`, `/app/cover-letter?id=`):
      checked **sentence by sentence** — rule checks (no number / skill the resume lacks,
      plus a fixed list of embellishing words unless the resume uses them), then the
      second check; failing sentences get one rewrite, then are left out and listed with
      the reason. Greeting, name and sign-off come from code. PDF in the resume's
      template; 20/day. Real runs drove the design: paragraph-level checking let
      "which improved reliability" through, and a rewrite duplicated a sentence (now
      deduplicated). **Web page not yet checked in the browser.**
- [x] Rate limiting on auth: failed sign-ins 10 per account and 50 per IP per 15 min
      (only failures count), sign-ups 10 per IP per hour, reset requests 3 per account /
      20 per IP per hour. Counted in Postgres (`auth_attempts`, pruned after a day) so it
      holds across processes. `TRUST_PROXY_HEADERS` decides whether X-Forwarded-For is
      believed. AI endpoints already had per-user daily caps.
- [x] Password reset: emailed one-hour, single-use link (only a hash stored); the same
      answer whether or not the account exists; using it signs out every other session
      (`users.token_version` in every token — a counter, because a timestamp let a token
      from the same second survive) and cancels other links. `/forgot-password`,
      `/reset-password`. Email via SMTP (`services/mailer.py`); **unset, the email is
      written to the API log** — real sending needs SMTP settings.
- [x] Fit to N pages (`services/fit.py`, the editor's "Length" panel): past one page the
      editor asks how many pages the person wants. Then: margins (normal / narrow, all
      four sides; or **custom**, 5–30 mm, the same on every side, by slider or typed),
      which sections to include (`resumes.layout`: hidden sections stay in
      the content, just not on the page), "Fit to N pages for me" (narrow margins first;
      then rounds of fewer lines per role by recency — newest keeps the most, e.g.
      5/3/2 — re-rendering the PDF to count pages), lines per role up or down (down
      merges with AI; up adds back the person's own lines, undoing a merge if needed), and
      "Write / Rewrite with AI" for the summary at a chosen length (shorter / same /
      longer — checked by word count, one retry). The panel is always shown, with a
      1/2-page dropdown, so a resume can grow as well as shrink. Every AI edit has Undo. Merged lines
      name the lines they came from and pass the same rule checks + second check as
      tailoring; a role whose merge fails keeps its own top lines instead. A real run
      had a summary say "previously … using Go" of roles that used Java — now the prompt
      and the check both forbid tying a skill to the wrong role or time.
- [x] Build a profile from scratch (`/app/build`), for people with no resume to upload.
      Two tracks: **student / fresher** (contact → education → projects → internships,
      optional → skills → certifications → summary → check and save) and **experienced**
      (work first). Saved as you go; blank entries dropped between steps; resumable.
      "Help me write these lines" under every project and role (profile editor too):
      the person describes it in their own words and gets resume lines, each checked
      against those notes — numbers, known technologies (case-insensitive in notes:
      "react" counts), embellishing words, then the second check; failing lines are left
      out with the reason (`services/draft.py`, `POST /profile/lines`). Summary written
      from the profile (`POST /profile/summary`). A fresher's resume (no roles, or only
      internships) leads with Summary, Education, Skills, Projects (`layout.order`), and
      tailoring keeps all relevant projects; any resume's section order can be changed
      in the Length panel. A real run had a summary say "Riya Shah is… She built…" —
      summaries now name no one and use no pronouns (a name says nothing about how
      someone is referred to), checked in code for tailoring and writing alike.
- [x] Preview shows every page: the API renders each page of the real PDF to an image
      (`page_images`, pymupdf, 144 dpi JPEG, ~0.25 s for two pages), stacked with "Page 1
      of 2" — the HTML preview couldn't know where WeasyPrint breaks a page, so page 2
      was cut off. Used in the resume editor (its sticky column scrolls inside itself)
      and the template's full-size view. The sidebar is sticky and full height on wide
      screens, so the account and Sign out stay at its foot.
- [x] Links, kept and clickable. Upload: links hidden behind text (a certificate's name
      linked to its credential, "LinkedIn" linked to a profile) are read out of PDF link
      annotations and Word hyperlinks and listed after the text, and the parser attaches
      each to its item; an address is kept only if the file has it (written or linked),
      so a "completed" link can't slip in. Resume: certificate names link to the
      credential, with a short visible link ("credly.com/…") for print and ATS; phone is
      a `tel:` link; email, profile links and projects were already. Preview: the PDF's
      link areas are clickable over the page images (web, mail and phone only). Profile
      editor: a credential-link field on certifications. Checked with a real upload:
      credential, LinkedIn and GitHub all came through.
- [x] Header per resume: a Header card in the resume editor — name and job title, each
      contact item (job title, email, phone, location, every link) can be left off with
      a tick (`layout.hidden_header`; the value stays) or edited for this resume, links
      added or removed, and a profile link removed here can be added back. The cover
      letter's header leaves off the same items. The profile is never changed.
- [x] Admin panel (`/app/admin`, API `/admin/*`). Admins are `ADMIN_EMAILS` whose address
      is verified (Google sign-in or a password reset) — so nobody can sign up with the
      admin's address first and inherit the rights; everyone else gets 404. Overview
      (users new/active, Google vs password, profiles, resumes, cover letters, jobs,
      uploads and failures, 30-day sign-ups chart); users list with search, paging and
      CSV export; per-user page with activity — resumes, jobs, uploads and their errors,
      profile section counts, **not** resume text; actions: sign out everywhere,
      disable/enable (blocks sign-in and every token), delete account with its data and
      R2 files (type the email to confirm; not your own); failed uploads; an admin log
      (`admin_actions`) of every action, kept after an account is deleted. `last_seen_at`
      is updated at most hourly on signed-in requests.
- [ ] Email verification — not built: adds friction before the product proves itself;
      the reset flow already proves control of the address when it matters.

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
