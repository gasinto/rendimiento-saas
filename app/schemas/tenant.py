"""Tenant schemas."""

from datetime import datetime
from pydantic import BaseModel


class TenantCreate(BaseModel):
    name: str
    slug: str
    config: str = "{}"


class TenantUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    active: bool | None = None
    config: str | None = None


class TenantResponse(BaseModel):
    id: int
    name: str
    slug: str
    active: bool
    config: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
