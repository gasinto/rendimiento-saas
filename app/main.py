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
from app.database import async_session_factory, engine, Base
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
                capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent,
                timeout=30,
            )
            if result.returncode == 0:
                logging.info("Alembic migrations applied successfully")
            else:
                logging.warning("Alembic migration stderr: %s", result.stderr)
        except Exception as e:
            logging.warning("Alembic migration failed (may be already applied): %s", e)

        # Seed default tenant + admin user (non-fatal — app works without it)
        try:
            await seed_default_admin()
        except Exception as e:
            logging.warning("Seed failed (db may not be ready yet): %s", e)

    async def seed_default_admin() -> None:
        """Create or update the default tenant and admin user.

        Idempotent — safe to run on every startup.
        If the admin_email or admin_password changed in env vars, the
        existing user is updated in-place.

        Uses raw SQL so bcrypt import or ORM won't block startup.
        """
        import bcrypt as _bcrypt

        hashed = _bcrypt.hashpw(
            settings.admin_password.encode("utf-8"),
            _bcrypt.gensalt(rounds=10),
        ).decode("utf-8")
        slug = settings.admin_email.split("@")[0].lower()
        name = settings.admin_email.split("@")[0]

        from sqlalchemy import text as _text

        async with async_session_factory() as session:
            # Upsert tenant with raw SQL
            try:
                tenant_r = await session.execute(
                    _text(
                        """INSERT INTO tenants (name, slug, config, active)
                           VALUES (:name, :slug, '{}', true)
                           ON CONFLICT (slug) DO UPDATE SET name = :name2
                           RETURNING id"""
                    ),
                    {"name": name, "slug": slug, "name2": name},
                )
                tenant_id = tenant_r.scalar_one()
                logging.info("Tenant %s ready (id=%s)", slug, tenant_id)
            except Exception as e:
                logging.error("Tenant upsert failed: %s", e)
                raise

            # Upsert admin user with raw SQL
            try:
                user_r = await session.execute(
                    _text(
                        """INSERT INTO users (tenant_id, email, password_hash, display_name, role, active)
                           VALUES (:tid, :email, :pw, :display, 'admin', true)
                           ON CONFLICT (email) DO UPDATE SET password_hash = :pw2
                           RETURNING id"""
                    ),
                    {
                        "tid": tenant_id,
                        "email": settings.admin_email,
                        "pw": hashed,
                        "display": "Admin",
                        "pw2": hashed,
                    },
                )
                user_id = user_r.scalar_one()
                await session.commit()
                logging.info(
                    "Admin user seeded: %s (id=%s)", settings.admin_email, user_id
                )
            except Exception as e:
                await session.rollback()
                logging.error("Admin user seed failed: %s", e)
                raise

    @app.on_event("shutdown")
    async def on_shutdown():
        await engine.dispose()
        logging.info("Shutdown complete")

    return app


app = create_app()
