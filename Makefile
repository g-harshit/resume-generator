# Everything you need to run the project locally. `make dev` is the usual entry point.
.PHONY: db api web dev migrate test lint

db:          ## start Postgres (docker) and wait until it accepts connections
	docker compose up -d --wait db

api: db      ## API on http://localhost:8100 with reload
	cd backend && uv run alembic upgrade head && uv run uvicorn app.main:app --reload --port 8100

web:         ## web app on http://localhost:3100
	pnpm --filter web dev

dev: db      ## API + web together
	$(MAKE) -j2 api web

migrate:
	cd backend && uv run alembic upgrade head

test: db
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	pnpm --filter web lint
