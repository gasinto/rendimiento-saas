"""Board (placa) related models — placas, notas_placa, mediciones_placa, bloques_placa."""

from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Placa(Base):
    """Board model — references tipos_equipo."""

    __tablename__ = "placas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    modelo_placa: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    tipo_equipo_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tipos_equipo.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Placa id={self.id} modelo={self.modelo_placa!r}>"


class NotaPlaca(Base):
    """Board notes — optional tenant_id (NULL = shared)."""

    __tablename__ = "notas_placa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    modelo_placa: Mapped[str] = mapped_column(String(255), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    bloque: Mapped[str] = mapped_column(String(100), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    tenant_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tenants.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<NotaPlaca id={self.id} modelo={self.modelo_placa!r}>"


class MedicionPlaca(Base):
    """Board-specific measurements — optional tenant_id (NULL = shared)."""

    __tablename__ = "mediciones_placa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    modelo_placa: Mapped[str] = mapped_column(String(255), nullable=False)
    punto_medicion: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre: Mapped[str] = mapped_column(String(255), default="")
    valor_esperado: Mapped[str] = mapped_column(String(255), default="")
    categoria: Mapped[str] = mapped_column(String(100), default="")
    ic_referencia: Mapped[str] = mapped_column(String(255), default="")
    notas: Mapped[str] = mapped_column(Text, default="")
    bloque: Mapped[str] = mapped_column(String(100), default="")
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    tenant_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tenants.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<MedicionPlaca id={self.id} punto={self.punto_medicion!r}>"


class BloquePlaca(Base):
    """Board block grouping — for organizing measurements and notes."""

    __tablename__ = "bloques_placa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    modelo_placa: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<BloquePlaca id={self.id} nombre={self.nombre!r}>"
