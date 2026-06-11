"""
FastAPI dependencies — auth, tenant isolation, role checks.

Every protected endpoint must use `get_current_user` or `get_current_tenant`
to ensure the request is authenticated and tenant-scoped.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from jwt import PyJWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services.auth_service import decode_token

security = HTTPBearer(auto_error=False)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token_data: str | None = Depends(security),
) -> User:
    """
    Extract and validate the current user from the JWT Bearer token.

    Returns the User ORM instance. Raises 401 if token is missing or invalid.
    """
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "detail": "Missing authentication token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(token_data.credentials)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "invalid_token", "detail": "Token is not an access token"},
            )
        user_id = int(payload.get("sub"))
    except PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "detail": str(e)},
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "detail": "User not found or inactive"},
        )

    return user


async def get_current_tenant(current_user: User = Depends(get_current_user)) -> int:
    """Return the tenant_id from the authenticated user."""
    return current_user.tenant_id


def require_role(*roles: str):
    """
    Factory for role-checking dependency.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role("admin"))):
            ...
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "forbidden",
                    "detail": f"Role {current_user.role!r} not in {roles}",
                },
            )
        return current_user

    return role_checker
