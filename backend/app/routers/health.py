from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.database import SessionDep

router = APIRouter()


@router.get("/health")
def health(session: SessionDep) -> dict:
    # Touch the database so "healthy" means the API can actually serve requests.
    session.exec(text("SELECT 1"))
    return {"status": "ok", "app": get_settings().app_name}
