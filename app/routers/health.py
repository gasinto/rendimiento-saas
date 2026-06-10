"""Health check endpoint — used by Railway for container health probes.

This endpoint is intentionally dependency-free (no get_db) so it can
respond even when the database is unavailable, preventing Railway
from cycling the container on cold start.
"""

from fastapi import APIRouter
from sqlalchemy import text

from app.database import async_session_factory
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Verifies that the application is running and the database is reachable.
    Returns 200 with `{ "status": "ok", "db": "connected" }` on success,
    or `{ "status": "degraded", "db": "disconnected" }` if the DB is down.
    """
    db_status = "disconnected"
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception:
        pass

    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        db=db_status,
    )
