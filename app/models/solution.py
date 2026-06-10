"""Solution model — optional tenant_id (NULL = shared globally)."""

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Solucion(Base):
    """Repair solution — shared by default, can be tenant-private."""

    __tablename__ = "soluciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    placa: Mapped[str] = mapped_column(String(255), nullable=False)
    falla: Mapped[str] = mapped_column(Text, default="")
    solucion: Mapped[str] = mapped_column(Text, default="")
    ics: Mapped[str] = mapped_column(String(500), default="[]")
    tenant_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tenants.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Solucion id={self.id} placa={self.placa!r}>"
