from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  (registers tables on SQLModel.metadata)
from app.config import get_settings
from app.routers import health

settings = get_settings()

app = FastAPI(title=f"{settings.app_name} API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,  # auth is a bearer token, not a cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
