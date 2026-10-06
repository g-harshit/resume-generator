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
    # Connections this process may hold. A hosted pooler caps clients (Supabase's free
    # session pooler: 15), so stay well under it with room for migrations.
    db_pool_size: int = 5
    db_max_overflow: int = 5

    # Comma-separated: the web app, and the Chrome extension (its ID is fixed by the
    # public key in apps/extension/wxt.config.ts).
    cors_origins: str = (
        "http://localhost:3100,http://127.0.0.1:3100,"
        "chrome-extension://pjddbiflcebndfljpckcgkigckfpmndm"
    )

    # The website, for links in emails (password reset).
    web_url: str = "http://localhost:3100"

    # Outgoing email. Unset in development: emails are written to the API log instead.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # Behind a proxy (Render, Fly…), the client's IP is in X-Forwarded-For. Only trust
    # it when there is a proxy, or anyone could fake their IP past the rate limits.
    trust_proxy_headers: bool = False

    # "development" or "production". Production refuses to start with dev-only defaults.
    environment: str = "development"

    # "Sign in with Google": the OAuth client ID (public; Google Cloud → Credentials).
    # Empty turns Google sign-in off. Only the ID is needed: the API checks the ID
    # token Google gives the browser against Google's published keys.
    google_client_id: str = ""

    # Ping our own public URL every 10 minutes so Render's free plan never puts the
    # API to sleep (app/services/keep_awake.py). Only runs where there's a URL:
    # KEEP_AWAKE_URL, or RENDER_EXTERNAL_URL (set by Render).
    keep_awake: bool = True
    keep_awake_url: str = ""

    # Comma-separated emails with access to the admin panel. Only counts once the
    # account's address is verified (Google sign-in or a password reset), so nobody can
    # sign up with an admin's address first and inherit the rights.
    admin_emails: str = ""

    # Signs login tokens. Anyone holding it can mint a token for any account.
    jwt_secret: str = DEV_JWT_SECRET
    # There is no refresh token yet, so this is how long a login lasts.
    access_token_days: int = 7

    # "openai", or "stub" (canned answers; what the test suite uses).
    ai_provider: str = "openai"
    openai_api_key: str = ""
    # Reads resumes and job descriptions. Configurable because model names change.
    openai_parse_model: str = "gpt-4o-mini"
    # Rewords resumes, and checks the rewording. Compared on the same profile and job
    # (2026-10): gpt-4o-mini embellished 6 of 7 lines ("…improving operational
    # efficiency"), all reverted by the guard, leaving tailoring nearly a no-op;
    # gpt-4.1 reworded cleanly with 1 revert. The guard doesn't depend on the model.
    openai_tailor_model: str = "gpt-4.1"
    # Works the keywords a person picked into one of their lines. A stronger model,
    # since nothing second-guesses it: the person asked for exactly these keywords.
    openai_keywords_model: str = "gpt-5.5"

    # Uploaded files, when stored on local disk (dev). R2 comes with deployment.
    upload_dir: str = "var/uploads"
    # Cloudflare R2 (S3-compatible). With a bucket set, uploads go there instead of
    # `upload_dir`, so they survive restarts on a host without a persistent disk.
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    # Each parse is a paid model call, so these are capped per account per day.
    uploads_per_day: int = 20
    # The free ATS checker, per IP address per day (no account needed).
    ats_checks_per_day: int = 5
    jobs_per_day: int = 50
    resumes_per_day: int = 30
    cover_letters_per_day: int = 20
    # Summaries, condensing and fit-to-pages: each is a few model calls.
    resume_ai_edits_per_day: int = 60

    @property
    def admin_email_list(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

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
