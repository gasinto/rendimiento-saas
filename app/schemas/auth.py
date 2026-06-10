"""Authentication schemas — request/response models for auth endpoints."""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: "UserOut"


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    tenant_id: int
    role: str = "viewer"


class RegisterResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str


class TokenPayload(BaseModel):
    sub: int  # user_id
    tenant_id: int
    role: str
    type: str  # "access" or "refresh"
