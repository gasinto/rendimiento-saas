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
        """
        from sqlalchemy import select

        from app.models.tenant import Tenant
        from app.models.user import User
        from app.services.auth_service import hash_password

        async with async_session_factory() as session:
            slug = settings.admin_email.split("@")[0].lower()

            # Upsert default tenant
            result = await session.execute(
                select(Tenant).where(Tenant.slug == slug)
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                tenant = Tenant(
                    name=settings.admin_email.split("@")[0],
                    slug=slug,
                    config="{}",
                    active=True,
                )
                session.add(tenant)
                await session.flush()
                logging.info("Created default tenant: %s", slug)
            else:
                logging.info("Tenant %s already exists, reusing it", slug)

            # Upsert admin user by email
            hashed = hash_password(settings.admin_password)
            result = await session.execute(
                select(User).where(User.email == settings.admin_email)
            )
            admin = result.scalar_one_or_none()
            if admin:
                # Update password if it changed
                if admin.password_hash != hashed:
                    admin.password_hash = hashed
                    await session.commit()
                    logging.info("Updated admin password for: %s", settings.admin_email)
                else:
                    logging.info("Admin user already up to date, skipping")
            else:
                admin = User(
                    tenant_id=tenant.id,
                    email=settings.admin_email,
                    password_hash=hashed,
                    display_name="Admin",
                    role="admin",
                    active=True,
                )
                session.add(admin)
                await session.commit()
                logging.info("Seeded admin user: %s", settings.admin_email)

    @app.on_event("shutdown")
    async def on_shutdown():
        await engine.dispose()
        logging.info("Shutdown complete")

    return app


app = create_app()
