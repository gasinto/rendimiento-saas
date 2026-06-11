"""
Repairs router — month view, add, delete for reparaciones.

Replicates server.py APIHandler: listar_meses, listar_ordenes (month view),
agregar_orden, eliminar_orden.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_current_tenant
from app.models.order import Orden, Reparacion
from app.models.user import User

router = APIRouter(prefix="/api/repairs", tags=["repairs"])


# ── Schemas ──────────────────────────────────────────────────────────────


class ReparacionOut(BaseModel):
    id: int
    tenant_id: int
    orden_id: int
    fecha: str
    tipo: str
    puntaje: float
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReparacionCreate(BaseModel):
    fecha: str | None = None
    orden: int  # orden numero (legacy compat)
    tipo: str


class ReparacionListResponse(BaseModel):
    ordenes: list[ReparacionOut]


class MesReparacion(BaseModel):
    mes: str
    equipos: int = 0
    puntos_totales: float = 0
    ganancia: float = 0


class MesesResponse(BaseModel):
    meses: list[MesReparacion]
    total_puntos: float = 0
    total_ganancia: float = 0


# ── Helpers ──────────────────────────────────────────────────────────────


async def _get_valor_punto(db: AsyncSession, tenant_id: int) -> float:
    """Get valor_punto from config for this tenant."""
    result = await db.execute(
        text("SELECT valor FROM config WHERE tenant_id = :tid AND clave = 'valor_punto'"),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    return float(row[0]) if row else 2000


async def _lookup_puntaje(db: AsyncSession, tipo: str) -> float | None:
    """Look up score for a tipo from puntajes table."""
    result = await db.execute(
        text("SELECT puntaje FROM puntajes WHERE tipo = :tipo LIMIT 1"),
        {"tipo": tipo},
    )
    row = result.fetchone()
    return float(row[0]) if row else None


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/months", response_model=MesesResponse)
async def list_months(
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """List all months with repair data (grouped by YYYY-MM)."""
    valor_punto = await _get_valor_punto(db, tenant_id)

    result = await db.execute(
        text("""
            SELECT LEFT(fecha, 7) as mes,
                   COUNT(*) as equipos,
                   SUM(puntaje) as puntos_totales
            FROM reparaciones
            WHERE tenant_id = :tid
            GROUP BY mes
            ORDER BY mes DESC
        """),
        {"tid": tenant_id},
    )
    rows = result.fetchall()
    meses = []
    total_puntos = 0.0
    for r in rows:
        pts = float(r[2] or 0)
        total_puntos += pts
        meses.append(
            MesReparacion(
                mes=r[0],
                equipos=r[1],
                puntos_totales=pts,
                ganancia=round(pts * valor_punto, 2),
            )
        )

    total_ganancia = round(total_puntos * valor_punto, 2)
    return MesesResponse(
        meses=meses, total_puntos=total_puntos, total_ganancia=total_ganancia
    )


@router.get("/by-month", response_model=ReparacionListResponse)
async def list_repairs_by_month(
    mes: str | None = None,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """List repairs for a given month (YYYY-MM), or all if no month."""
    stmt = select(Reparacion).where(Reparacion.tenant_id == tenant_id)
    if mes:
        stmt = stmt.where(text("LEFT(fecha, 7) = :mes")).params(mes=mes)
    stmt = stmt.order_by(Reparacion.fecha.desc(), Reparacion.id.desc())

    result = await db.execute(stmt)
    repairs = result.scalars().all()
    return ReparacionListResponse(ordenes=repairs)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_repair(
    data: ReparacionCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Add a repair entry. Looks up puntaje from tipo."""
    fecha = data.fecha or datetime.now().strftime("%Y-%m-%d")
    tipo = data.tipo

    # Look up puntaje
    score = await _lookup_puntaje(db, tipo)
    if score is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "not_found", "detail": f"Tipo '{tipo}' no encontrado"},
        )

    # Look up orden by numero (legacy compat: find ordenes.numero matching data.orden)
    from sqlalchemy import select as sa_select

    result = await db.execute(
        sa_select(Orden).where(
            Orden.tenant_id == tenant_id, Orden.numero == data.orden
        )
    )
    orden = result.scalar_one_or_none()
    if not orden:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "not_found",
                "detail": f"Orden #{data.orden} no encontrada",
            },
        )

    repair = Reparacion(
        tenant_id=tenant_id,
        orden_id=orden.id,
        fecha=fecha,
        tipo=tipo,
        puntaje=score,
    )
    db.add(repair)
    await db.flush()
    await db.refresh(repair)
    return {"ok": True, "id": repair.id}


@router.delete("/{repair_id}")
async def delete_repair(
    repair_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Delete a repair entry."""
    result = await db.execute(
        select(Reparacion).where(
            Reparacion.id == repair_id, Reparacion.tenant_id == tenant_id
        )
    )
    repair = result.scalar_one_or_none()
    if not repair:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "detail": f"Repair {repair_id} not found"},
        )
    await db.delete(repair)
    await db.flush()
    return {"ok": True}
