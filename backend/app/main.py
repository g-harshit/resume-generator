import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  (registers tables on SQLModel.metadata)
from app.config import get_settings
from app.routers import admin, auth, health, jobs, profile, resumes, templates, uploads
from app.services import keep_awake

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Keep Render's free plan from sleeping the API (see app/services/keep_awake.py).
    url = keep_awake.target_url()
    task = asyncio.create_task(keep_awake.ping_forever(url)) if url else None
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title=f"{settings.app_name} API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,  # auth is a bearer token, not a cookie
    allow_methods=["*"],
    allow_headers=["*"],
    # Lets the web app read the page count of a downloaded PDF.
    expose_headers=["X-Page-Count", "Content-Disposition"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(uploads.router)
app.include_router(profile.router)
app.include_router(jobs.router)
app.include_router(templates.router)
app.include_router(resumes.router)
