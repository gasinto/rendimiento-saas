"""Reference model — technical reference articles (global)."""

from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Referencia(Base):
    """Technical reference — global, shared across all tenants."""

    __tablename__ = "referencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    categoria: Mapped[str] = mapped_column(String(100), nullable=False, default="Electronica General")
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    contenido_html: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Referencia id={self.id} titulo={self.titulo!r}>"
