# The API, as deployed (Render). Build from this folder: docker build -t quickfitcv-api .
FROM python:3.12-slim-bookworm

# WeasyPrint draws PDFs with Pango; fonts stand in for the templates' Georgia /
# Helvetica / Arial (see fonts/60-metric-aliases.conf).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 \
        fonts-liberation2 fontconfig \
    && rm -rf /var/lib/apt/lists/*

COPY fonts/*.ttf /usr/share/fonts/truetype/gelasio/
COPY fonts/60-metric-aliases.conf /etc/fonts/conf.d/60-metric-aliases.conf
RUN fc-cache -f

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1

WORKDIR /app
# Dependencies first, so a code change doesn't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Never run as root.
RUN useradd --create-home --uid 10001 api
USER api

# Render sets PORT. Migrations run first: one instance, so they can't race.
# Uploads go to R2; set R2_* or they land on the container's (temporary) disk.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
