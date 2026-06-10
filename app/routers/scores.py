"""
Scores router — Puntajes CRUD + actualizar-valor-punto (tenant-scoped config).

Replicates server.py APIHandler: listar_puntajes, agregar_puntaje,
actualizar_puntaje, eliminar_puntaje, actualizar_valor_punto, listar_tipos.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_current_tenant
from app.models.score import Puntaje
from app.models.user import User

router = APIRouter(prefix="/api/scores", tags=["scores"])


# ── Schemas ──────────────────────────────────────────────────────────────


class PuntajeOut(BaseModel):
    id: int
    tenant_id: int
    tipo: str
    puntaje: float
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PuntajeCreate(BaseModel):
    tipo: str
    puntaje: float = 1


class PuntajeUpdate(BaseModel):
    tipo: str
    puntaje: float = 1


class ValorPuntoUpdate(BaseModel):
    valor: float = 2000


class PuntajeListResponse(BaseModel):
    puntajes: list[PuntajeOut]
    valor_punto: float = 2000


class TiposResponse(BaseModel):
    tipos: list[str]


# ── Helpers ──────────────────────────────────────────────────────────────


async def _get_valor_punto(db: AsyncSession, tenant_id: int) -> float:
    """Get valor_punto from config for this tenant."""
    result = await db.execute(
        text(
            "SELECT valor FROM config WHERE tenant_id = :tid AND clave = 'valor_punto'"
        ),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    return float(row[0]) if row else 2000


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/", response_model=PuntajeListResponse)
async def list_scores(
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """List all puntajes (score types) for this tenant, plus valor_punto."""
    result = await db.execute(
        select(Puntaje)
        .where(Puntaje.tenant_id == tenant_id)
        .order_by(Puntaje.puntaje.desc())
    )
    puntajes = result.scalars().all()
    valor_punto = await _get_valor_punto(db, tenant_id)
    return PuntajeListResponse(puntajes=puntajes, valor_punto=valor_punto)


@router.post("/")
async def create_score(
    data: PuntajeCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Create a new score type. Tipo is normalized to UPPER and stripped."""
    tipo = data.tipo.strip().upper()
    if not tipo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "detail": "Falta tipo"},
        )

    existing = await db.execute(
        select(Puntaje).where(
            Puntaje.tenant_id == tenant_id, Puntaje.tipo == tipo
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "conflict", "detail": "Ya existe ese tipo"},
        )

    puntaje = Puntaje(
        tenant_id=tenant_id,
        tipo=tipo,
        puntaje=data.puntaje,
    )
    db.add(puntaje)
    await db.flush()
    return {"ok": True}


@router.put("/")
async def update_score(
    data: PuntajeUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Update a score type's value."""
    tipo = data.tipo.strip().upper()
    if not tipo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "detail": "Falta tipo"},
        )

    result = await db.execute(
        select(Puntaje).where(
            Puntaje.tenant_id == tenant_id, Puntaje.tipo == tipo
        )
    )
    puntaje = result.scalar_one_or_none()
    if not puntaje:
        # Create if not exists
        puntaje = Puntaje(tenant_id=tenant_id, tipo=tipo, puntaje=data.puntaje)
        db.add(puntaje)
    else:
        puntaje.puntaje = data.puntaje
    await db.flush()
    return {"ok": True}


@router.delete("/")
async def delete_score(
    tipo: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Delete a score type."""
    tipo_norm = tipo.strip().upper()
    if not tipo_norm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "detail": "Falta tipo"},
        )

    result = await db.execute(
        select(Puntaje).where(
            Puntaje.tenant_id == tenant_id, Puntaje.tipo == tipo_norm
        )
    )
    puntaje = result.scalar_one_or_none()
    if puntaje:
        await db.delete(puntaje)
        await db.flush()
    return {"ok": True}


@router.get("/tipos")
async def list_types(
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """List just the score type names (ordered by puntaje desc)."""
    result = await db.execute(
        select(Puntaje.tipo)
        .where(Puntaje.tenant_id == tenant_id)
        .order_by(Puntaje.puntaje.desc())
    )
    tipos = [row[0] for row in result.fetchall()]
    return TiposResponse(tipos=tipos)


@router.put("/valor-punto")
async def update_valor_punto(
    data: ValorPuntoUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Update valor_punto for this tenant."""
    if data.valor <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "detail": "El valor debe ser mayor a 0",
            },
        )

    await db.execute(
        text("""
            INSERT INTO config (tenant_id, clave, valor)
            VALUES (:tid, 'valor_punto', :val)
            ON CONFLICT (tenant_id, clave) DO UPDATE SET valor = :val2
        """),
        {"tid": tenant_id, "val": str(data.valor), "val2": str(data.valor)},
    )
    await db.flush()
    return {"ok": True}
