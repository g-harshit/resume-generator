# resume-generator — working notes for Claude Code

Resume tailoring: a website + a Chrome extension. FastAPI backend (`backend/`), Next.js
web app (`apps/web/`), WXT extension (`apps/extension/`, Phase 11). **`plan.md` is the
source of truth** for what's built, what's next and why — read it first, and tick its
boxes as work lands.

Mockups: https://claude.ai/artifact/GTEZFenLX3qkHhDXzDsfg3

## Rules that aren't obvious from the code

- **The product has no name yet.** Never hardcode "Tailor": use `APP_NAME`
  (`apps/web/lib/config.ts`) or `settings.app_name` (backend).
- **Tailoring never invents facts** — no skill, employer, date or number that isn't in the
  profile. Enforced in code after the model returns, not only in the prompt (plan.md,
  Phase 7). A resume is a frozen snapshot; editing the profile never changes one.
- **Postgres everywhere, including tests.** `docker compose up -d db` (host port 5433).
  Tests use the separate `resume_test` database and refuse to run against any database
  whose name doesn't end in `_test`. Don't add SQLite "for convenience": JSONB, enums and
  constraints differ, and those bugs only show up in production.
- **Ports: API 8100, web 3100** — so this project can run beside Signal (8000/3000).
- **Schema changes go through Alembic.** `uv run alembic revision --autogenerate -m "..."`
  then `uv run alembic upgrade head`; `uv run alembic check` must be clean. Tests build
  their schema with `create_all`, so a missing migration won't fail the suite — `alembic
  check` is what catches it.
- **FastAPI deps use `Annotated`** (`SessionDep` in `app/database.py`), not
  `= Depends(...)` defaults — ruff's B008 is on.
- **This Next.js is newer than your training data** (see `apps/web/AGENTS.md`): check
  `apps/web/node_modules/next/dist/docs/` before using an API you're unsure of.
- Run `pnpm build:web` before calling frontend work done; some errors only show in a
  production build.

## Commands

```bash
make dev      # Postgres + API (8100) + web (3100)
make test     # backend tests
make lint     # ruff + eslint
```
