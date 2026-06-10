"""Score/puntaje model — per-tenant scoring definitions."""

from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Puntaje(Base):
    """Score type definition — per-tenant.

    Each tenant can define their own repair score types and values.
    Migration copies the original global defaults to tenant 1.
    """

    __tablename__ = "puntajes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(100), nullable=False)
    puntaje: Mapped[float] = mapped_column(Float, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Puntaje id={self.id} tipo={self.tipo!r} puntaje={self.puntaje}>"
