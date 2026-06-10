"""Equipment type model — global, shared across all tenants."""

from datetime import datetime
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TipoEquipo(Base):
    """Equipment type (e.g. Notebook, TV, Monitor) — global reference."""

    __tablename__ = "tipos_equipo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<TipoEquipo id={self.id} nombre={self.nombre!r}>"
