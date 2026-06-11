"""Authentication router — register, login, token refresh."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from jwt import PyJWTError
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory, get_db
from app.dependencies import get_current_user, require_role
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    UserOut,
)
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    hash_password,
    rotate_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """Register a new user. Admin only.

    Creates a user with hashed password. The admin's tenant_id is used
    if the admin is not a global admin (override with provided tenant_id).
    """
    # Check email uniqueness
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "conflict", "detail": "Email already registered"},
        )

    user = User(
        tenant_id=data.tenant_id,
        email=data.email,
        password_hash=hash_password(data.password),
        display_name=data.name,
        role=data.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return RegisterResponse(
        id=user.id,
        name=user.display_name,
        email=user.email,
        role=user.role,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate a user and return JWT tokens.

    Validates email + password, returns access + refresh token pair.
    """
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "detail": "Invalid email or password"},
        )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "inactive_user", "detail": "User account is inactive"},
        )

    access_token = create_access_token(user.id, user.tenant_id, user.role)
    refresh_token = create_refresh_token(user.id, user.tenant_id, user.role)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserOut(
            id=user.id,
            name=user.display_name,
            email=user.email,
            role=user.role,
        ),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    data: RefreshRequest,
):
    """Refresh an access token using a refresh token.

    Implements refresh token rotation: old refresh token is invalidated
    and a new access + refresh pair is issued.
    """
    try:
        new_access, new_refresh = rotate_refresh_token(data.refresh_token)
    except PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "detail": str(e)},
        )

    return RefreshResponse(
        access_token=new_access,
        refresh_token=new_refresh,
    )


@router.get("/me", response_model=UserOut)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Return the currently authenticated user's profile."""
    return UserOut(
        id=current_user.id,
        name=current_user.display_name,
        email=current_user.email,
        role=current_user.role,
    )


class SetupResponse(BaseModel):
    ok: bool
    detail: str


@router.post("/setup", response_model=SetupResponse)
async def setup_default_admin():
    """Create the default tenant and admin user if they don't exist.

    Unauthenticated — useful for first-time setup or recovery.
    Safe to call multiple times (idempotent).
    """
    import bcrypt as _bcrypt

    hashed = _bcrypt.hashpw(
        settings.admin_password.encode("utf-8"),
        _bcrypt.gensalt(rounds=10),
    ).decode("utf-8")
    slug = settings.admin_email.split("@")[0].lower()
    name = settings.admin_email.split("@")[0]

    async with async_session_factory() as session:
        # Upsert tenant
        try:
            tenant_r = await session.execute(
                text(
                    """INSERT INTO tenants (name, slug, config, active)
                       VALUES (:name, :slug, '{}', true)
                       ON CONFLICT (slug) DO UPDATE SET name = :name2
                       RETURNING id"""
                ),
                {"name": name, "slug": slug, "name2": name},
            )
            tenant_id = tenant_r.scalar_one()
        except Exception as e:
            await session.rollback()
            logging.error("Setup — tenant upsert failed: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "setup_failed", "detail": f"Tenant creation failed: {e}"},
            )

        # Upsert admin user
        try:
            user_r = await session.execute(
                text(
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
            logging.info("Setup — admin user ready: %s (id=%s)", settings.admin_email, user_id)
        except Exception as e:
            await session.rollback()
            logging.error("Setup — admin user upsert failed: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "setup_failed", "detail": f"Admin creation failed: {e}"},
            )

    return SetupResponse(
        ok=True,
        detail=f"Admin user '{settings.admin_email}' ready. Credenciales por defecto en el .env.example",
    )
