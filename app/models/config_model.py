"""Tenant-scoped configuration model.

Composite PK of (tenant_id, clave). Replaces the old global config table.
"""

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Config(Base):
    """Per-tenant configuration key-value store.

    Each tenant gets its own config entries. The old global 'valor_punto'
    becomes per-tenant via (tenant_id=1, clave='valor_punto').
    """

    __tablename__ = "config"

    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id"), primary_key=True, nullable=False
    )
    clave: Mapped[str] = mapped_column(String(100), primary_key=True, nullable=False)
    valor: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def __repr__(self) -> str:
        return f"<Config tenant={self.tenant_id} clave={self.clave!r}>"
