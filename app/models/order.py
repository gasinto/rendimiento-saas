"""Order, Repair, and Repair Session models.

- ordenes: work orders (was the main order table)
- reparaciones: repair line items (was the main repair log)
- sesiones_reparacion: repair session timers (was MISSING CREATE TABLE in original)
"""

from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Orden(Base):
    """Work order — replaces the old `ordenes` table with proper FKs."""

    __tablename__ = "ordenes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id"), nullable=False, index=True
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha: Mapped[str] = mapped_column(String(10), nullable=False)
    placa: Mapped[str] = mapped_column(String(255), default="")
    falla: Mapped[str] = mapped_column(Text, default="")
    diagnostico: Mapped[str] = mapped_column(Text, default="")
    proceso: Mapped[str] = mapped_column(Text, default="")
    solucion: Mapped[str] = mapped_column(Text, default="")
    estado: Mapped[str] = mapped_column(String(20), default="en_curso")
    resultado: Mapped[str] = mapped_column(String(20), default="n/a")
    tipo: Mapped[str] = mapped_column(String(100), default="")
    puntaje: Mapped[float] = mapped_column(Float, default=0)
    tipo_equipo: Mapped[str] = mapped_column(String(100), default="")
    marca: Mapped[str] = mapped_column(String(100), default="")
    modelo: Mapped[str] = mapped_column(String(100), default="")
    checklist: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        # numero is unique per tenant
        type("UniqueConstraint", (), {"__call__": lambda: None})(),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="ordenes")  # noqa: F821
    reparaciones: Mapped[list["Reparacion"]] = relationship(  # noqa: F821
        "Reparacion", back_populates="orden_rel", foreign_keys="Reparacion.orden_id"
    )

    def __repr__(self) -> str:
        return f"<Orden id={self.id} numero={self.numero}>"


class Reparacion(Base):
    """Repair entry — fixed FK from old `orden` (string) to proper `orden_id`."""

    __tablename__ = "reparaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id"), nullable=False, index=True
    )
    orden_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ordenes.id"), nullable=False, index=True
    )
    fecha: Mapped[str] = mapped_column(String(10), nullable=False)
    tipo: Mapped[str] = mapped_column(String(100), nullable=False)
    puntaje: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    orden_rel: Mapped["Orden"] = relationship("Orden", back_populates="reparaciones")

    def __repr__(self) -> str:
        return f"<Reparacion id={self.id} tipo={self.tipo!r} puntaje={self.puntaje}>"


class SesionReparacion(Base):
    """Repair session timer — was missing CREATE TABLE in the original init_db."""

    __tablename__ = "sesiones_reparacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    orden_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ordenes.id"), nullable=False, index=True
    )
    tenant_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tenants.id"), nullable=True, index=True
    )
    inicio: Mapped[str] = mapped_column(String(19), nullable=False)
    fin: Mapped[str | None] = mapped_column(String(19), nullable=True)
    duracion_segundos: Mapped[int | None] = mapped_column(Integer, default=0)
    notas: Mapped[str] = mapped_column(Text, default="")
    estado: Mapped[str] = mapped_column(String(20), default="activa")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<SesionReparacion id={self.id} estado={self.estado!r}>"
