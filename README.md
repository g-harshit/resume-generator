# resume-generator

Turn a job description into an ATS-friendly resume, built from a profile you own.
A website (paste the job description) and a Chrome extension (reads it from the page).

The build plan and its progress are in [plan.md](plan.md).

## Run it locally

You need Docker Desktop, [uv](https://docs.astral.sh/uv/) and pnpm
(`brew install uv pnpm pango` — Pango is for PDF rendering). Python 3.12 is fetched by uv.

```bash
pnpm install
cd backend && uv sync && cd ..
make dev
```

- Web: http://localhost:3100
- API: http://localhost:8100 (docs at `/docs`)
- Postgres: `localhost:5433`, user/password/db `resume` (tests use `resume_test`)

Other commands: `make test`, `make lint`, `make migrate`.

Settings come from the environment or `backend/.env` (see `backend/.env.example`);
the defaults work with the Docker database.
