"""
Equipment types router — Tipos de equipo CRUD.

Replicates server.py APIHandler: listar_tipos_equipo, agregar_tipo_equipo,
eliminar_tipo_equipo.
Global table — no tenant isolation.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.equipment import TipoEquipo
from app.models.user import User

router = APIRouter(prefix="/api/types", tags=["types"])


# ── Schemas ──────────────────────────────────────────────────────────────


class TipoEquipoOut(BaseModel):
    id: int
    nombre: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class TipoEquipoCreate(BaseModel):
    nombre: str


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/")
async def list_tipos(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all equipment types."""
    result = await db.execute(
        select(TipoEquipo).order_by(TipoEquipo.nombre)
    )
    tipos = result.scalars().all()
    return {"tipos": tipos}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_tipo(
    data: TipoEquipoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new equipment type."""
    nombre = data.nombre.strip()
    if not nombre:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "detail": "Falta nombre"},
        )

    try:
        tipo = TipoEquipo(nombre=nombre)
        db.add(tipo)
        await db.flush()
        await db.refresh(tipo)
        return {"ok": True, "id": tipo.id}
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "conflict",
                "detail": "Ya existe ese tipo de equipo",
            },
        )


@router.delete("/{tipo_id}")
async def delete_tipo(
    tipo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an equipment type. Unlinks from boards first."""
    result = await db.execute(
        select(TipoEquipo).where(TipoEquipo.id == tipo_id)
    )
    tipo = result.scalar_one_or_none()
    if not tipo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "detail": f"TipoEquipo {tipo_id} not found",
            },
        )

    # Unlink from boards
    await db.execute(
        text("UPDATE placas SET tipo_equipo_id = NULL WHERE tipo_equipo_id = :tid"),
        {"tid": tipo_id},
    )
    await db.delete(tipo)
    await db.flush()
    return {"ok": True}
