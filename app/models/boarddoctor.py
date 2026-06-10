"""BoardDoctor models — diagramas, IC marcas, and IC compatibilidad (all global)."""

from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Diagrama(Base):
    """Board diagram / schematic reference — from BoardDoctor catalog."""

    __tablename__ = "diagramas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    marca: Mapped[str] = mapped_column(String(100), default="")
    modelo: Mapped[str] = mapped_column(String(255), default="")
    tipo: Mapped[str] = mapped_column(String(50), default="")
    gdrive_id: Mapped[str] = mapped_column(String(255), default="")
    nombre_archivo: Mapped[str] = mapped_column(String(255), default="")
    tamaño_mb: Mapped[float | None] = mapped_column(Float, default=0)
    ultima_sync: Mapped[str] = mapped_column(String(30), default="")

    def __repr__(self) -> str:
        return f"<Diagrama id={self.id} modelo={self.modelo!r}>"


class IcMarca(Base):
    """IC marking-to-model mapping — from BoardDoctor catalog."""

    __tablename__ = "ic_marcas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    marking: Mapped[str] = mapped_column(String(100), default="")
    modelo: Mapped[str] = mapped_column(String(255), default="")
    fabricante: Mapped[str] = mapped_column(String(255), default="")
    funcion: Mapped[str] = mapped_column(String(255), default="")
    compatibilidad: Mapped[str] = mapped_column(String(255), default="")

    def __repr__(self) -> str:
        return f"<IcMarca id={self.id} marking={self.marking!r}>"


class IcCompatibilidad(Base):
    """IC compatibility replacements — from BoardDoctor catalog."""

    __tablename__ = "ic_compatibilidad"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fabricante: Mapped[str] = mapped_column(String(255), default="")
    modelo: Mapped[str] = mapped_column(String(255), default="")
    compatibles: Mapped[str] = mapped_column(Text, default="")

    def __repr__(self) -> str:
        return f"<IcCompatibilidad id={self.id} modelo={self.modelo!r}>"
