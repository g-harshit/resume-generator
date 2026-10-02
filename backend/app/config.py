from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-not-a-secret-never-use-in-production"
JWT_SECRET_MIN_BYTES = 32  # HS256 wants a key at least as long as its output


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # The product has no name yet; everything user-facing reads it from here.
    app_name: str = "Tailor"

    database_url: str = "postgresql+psycopg://resume:resume@localhost:5433/resume"

    # Comma-separated. The web app in dev; the extension's origin is added in Phase 11.
    cors_origins: str = "http://localhost:3100,http://127.0.0.1:3100"

    # "development" or "production". Production refuses to start with dev-only defaults.
    environment: str = "development"

    # Signs login tokens. Anyone holding it can mint a token for any account.
    jwt_secret: str = DEV_JWT_SECRET
    # There is no refresh token yet, so this is how long a login lasts.
    access_token_days: int = 7

    # "openai", or "stub" (canned answers; what the test suite uses).
    ai_provider: str = "openai"
    openai_api_key: str = ""
    # Reads resumes and job descriptions. Configurable because model names change.
    openai_parse_model: str = "gpt-4o-mini"

    # Uploaded files, when stored on local disk (dev). R2 comes with deployment.
    upload_dir: str = "var/uploads"
    # Each parse is a paid model call, so these are capped per account per day.
    uploads_per_day: int = 20
    jobs_per_day: int = 50

    @model_validator(mode="after")
    def _no_dev_secrets_in_production(self) -> "Settings":
        if self.environment != "development" and self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET must be set outside development")
        if len(self.jwt_secret.encode()) < JWT_SECRET_MIN_BYTES:
            raise ValueError(f"JWT_SECRET must be at least {JWT_SECRET_MIN_BYTES} bytes")
        return self

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
