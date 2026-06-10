"""
FastAPI application factory for rendimiento-saas.

Creates and configures the FastAPI application, registers middleware,
and mounts all routers. Designed for Railway deployment.
"""

import logging
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette import status
from starlette.requests import Request

from app.config import settings
from app.database import engine, Base
from app.middleware import setup_middleware
from app.routers import (
    auth,
    boarddoctor,
    boards,
    dashboard,
    health,
    ics,
    measurements,
    orders,
    references,
    repairs,
    reports,
    scores,
    search,
    sessions,
    solutions,
    tenants,
    types,
)


def create_app() -> FastAPI:
    """Create and return a configured FastAPI application instance."""

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )

    # ── Middleware ───────────────────────────────────────────────
    setup_middleware(app)

    # ── Routers (API routes first, before static catch-all) ──────
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(tenants.router)
    app.include_router(orders.router)
    app.include_router(repairs.router)
    app.include_router(sessions.router)
    app.include_router(scores.router)
    app.include_router(boards.router)
    app.include_router(ics.router)
    app.include_router(measurements.router)
    app.include_router(solutions.router)
    app.include_router(references.router)
    app.include_router(types.router)
    app.include_router(dashboard.router)
    app.include_router(reports.router)
    app.include_router(search.router)
    app.include_router(boarddoctor.router)

    # ── Static files (catch-all — serves frontend SPA) ──────────
    static_dir = Path(__file__).resolve().parent.parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    # ── Exception handlers ───────────────────────────────────────
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "validation_error",
                    "detail": str(exc.errors()),
                }
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logging.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "detail": "An internal error occurred",
                }
            },
        )

    # ── Startup / Shutdown ───────────────────────────────────────
    @app.on_event("startup")
    async def on_startup():
        logging.info("Starting %s", settings.app_name)
        # Run Alembic migrations on fresh database
        try:
            result = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent
            )
            if result.returncode == 0:
                logging.info("Alembic migrations applied successfully")
            else:
                logging.warning("Alembic migration stderr: %s", result.stderr)
        except Exception as e:
            logging.warning("Alembic migration failed (may be already applied): %s", e)

    @app.on_event("shutdown")
    async def on_shutdown():
        await engine.dispose()
        logging.info("Shutdown complete")

    return app


app = create_app()
