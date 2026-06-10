"""
Authentication service — JWT creation/validation, bcrypt hashing, refresh rotation.

Uses PyJWT for token management and bcrypt for password hashing.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.config import settings


def hash_password(password: str) -> str:
    """Hash a plain-text password with bcrypt (cost factor 12)."""
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_access_token(user_id: int, tenant_id: int, role: str) -> str:
    """Create a short-lived JWT access token (15 min default)."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int, tenant_id: int, role: str) -> str:
    """Create a long-lived JWT refresh token (7 days default)."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload: dict[str, Any] = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "type": "refresh",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token. Raises jwt.PyJWTError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def rotate_refresh_token(old_token: str) -> tuple[str, str]:
    """
    Rotate a refresh token: validate the old one, issue new access + refresh pair.

    Returns (new_access_token, new_refresh_token).
    Raises jwt.PyJWTError if the old token is invalid or expired.
    """
    payload = decode_token(old_token)
    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("Token is not a refresh token")

    user_id = payload["sub"]
    tenant_id = payload["tenant_id"]
    role = payload["role"]

    new_access = create_access_token(user_id, tenant_id, role)
    new_refresh = create_refresh_token(user_id, tenant_id, role)

    return new_access, new_refresh
