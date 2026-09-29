from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # The product has no name yet; everything user-facing reads it from here.
    app_name: str = "Tailor"

    database_url: str = "postgresql+psycopg://resume:resume@localhost:5433/resume"

    # Comma-separated. The web app in dev; the extension's origin is added in Phase 11.
    cors_origins: str = "http://localhost:3100"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def normalise_db_url(url: str) -> str:
    """Hosted Postgres hands out `postgres://` / `postgresql://` URLs, which SQLAlchemy
    maps to psycopg2. We ship psycopg 3, so pin the driver. Alembic calls this too."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url
