from fastapi import APIRouter

from ..es.client import ping as es_ping
from ..providers.factory import active_provider_name

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness probe used by the container healthcheck."""
    return {"status": "ok"}


@router.get("/api/health/detailed")
def health_detailed() -> dict:
    """Readiness detail for the dashboard."""
    db_ok = True
    try:
        from sqlalchemy import text

        from ..db.database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False

    return {
        "status": "ok",
        "components": {
            "api": "up",
            "database": "up" if db_ok else "down",
            "elasticsearch": "up" if es_ping() else "down",
        },
        "aiProvider": active_provider_name(),
    }
