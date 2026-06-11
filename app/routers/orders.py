"""
Orders router — CRUD + list + import for ordenes (work orders).

Replicates server.py APIHandler: listar_ordenes_detalle, agregar_orden_detalle,
actualizar_orden_detalle, eliminar_orden_detalle, importar_ordenes.
"""

import csv
import io
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_current_tenant
from app.models.order import Orden
from app.models.user import User

router = APIRouter(prefix="/api/orders", tags=["orders"])


# ── Schemas ──────────────────────────────────────────────────────────────


class OrdenOut(BaseModel):
    id: int
    numero: int
    tenant_id: int
    fecha: str
    placa: str
    falla: str
    diagnostico: str
    proceso: str
    solucion: str
    estado: str
    resultado: str
    tipo: str
    puntaje: float
    tipo_equipo: str
    marca: str
    modelo: str
    checklist: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class OrdenCreate(BaseModel):
    numero: int
    fecha: str | None = None
    placa: str = ""
    falla: str = ""
    diagnostico: str = ""
    proceso: str = ""
    solucion: str = ""
    estado: str = "en_curso"
    resultado: str | None = None
    tipo: str = ""
    puntaje: float = 0
    tipo_equipo: str = ""
    marca: str = ""
    modelo: str = ""


class OrdenUpdate(BaseModel):
    placa: str | None = None
    falla: str | None = None
    diagnostico: str | None = None
    proceso: str | None = None
    solucion: str | None = None
    estado: str | None = None
    resultado: str | None = None
    tipo: str | None = None
    puntaje: float | None = None
    tipo_equipo: str | None = None
    marca: str | None = None
    modelo: str | None = None
    checklist: str | None = None


class OrdenBulkImport(BaseModel):
    ordenes: list[dict[str, Any]]


class OrdenBulkImportResponse(BaseModel):
    ok: bool = True
    importadas: int = 0


class OrdenListResponse(BaseModel):
    ordenes: list[OrdenOut]


# ── Helpers ──────────────────────────────────────────────────────────────


def _normalize_estado_resultado(
    estado: str | None, resultado: str | None
) -> tuple[str, str]:
    """Map legacy estado values (reparado, no_reparado) to new (estado, resultado)."""
    if resultado is not None:
        return estado or "en_curso", resultado
    if estado == "reparado":
        return "completado", "reparado"
    if estado == "no_reparado":
        return "completado", "no_reparado"
    if estado == "completado":
        return "completado", "n/a"
    return estado or "en_curso", "n/a"


async def _lookup_puntaje(db: AsyncSession, tipo: str) -> float | None:
    """Look up score for a tipo from puntajes table (legacy compat, tenant-agnostic)."""
    from sqlalchemy import text as sa_text

    result = await db.execute(
        sa_text("SELECT puntaje FROM puntajes WHERE tipo = :tipo LIMIT 1"),
        {"tipo": tipo},
    )
    row = result.fetchone()
    return float(row[0]) if row else None


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/", response_model=OrdenListResponse)
async def list_ordenes(
    empresa_id: str | None = None,
    estado: str | None = None,
    resultado: str | None = None,
    mes: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """List work orders with optional filters. Tenant-scoped."""
    # Build query
    from sqlalchemy import select as sa_select
    from sqlalchemy.orm import joinedload

    stmt = sa_select(Orden).where(Orden.tenant_id == tenant_id)

    if estado:
        stmt = stmt.where(Orden.estado == estado)
    if resultado:
        stmt = stmt.where(Orden.resultado == resultado)
    if mes:
        stmt = stmt.where(text("LEFT(fecha, 7) = :mes")).params(mes=mes)
    if q:
        pat = f"%{q.upper()}%"
        stmt = stmt.where(
            text(
                "UPPER(placa) LIKE :q OR UPPER(falla) LIKE :q "
                "OR UPPER(solucion) LIKE :q OR CAST(numero AS TEXT) LIKE :q"
            ).bindparams(q=pat)
        )

    stmt = stmt.order_by(Orden.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    ordenes = result.scalars().all()
    return OrdenListResponse(ordenes=ordenes)


@router.get("/{orden_id}", response_model=OrdenOut)
async def get_orden(
    orden_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Get a single work order by ID."""
    result = await db.execute(
        select(Orden).where(Orden.id == orden_id, Orden.tenant_id == tenant_id)
    )
    orden = result.scalar_one_or_none()
    if not orden:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "detail": f"Order {orden_id} not found"},
        )
    return orden


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_orden(
    data: OrdenCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Create a new work order. Auto-looks up puntaje if tipo is provided."""
    fecha = data.fecha or datetime.now().strftime("%Y-%m-%d")
    estado, resultado = _normalize_estado_resultado(data.estado, data.resultado)
    puntaje = data.puntaje

    # Auto-lookup puntaje if tipo given but puntaje is 0
    if data.tipo and not puntaje:
        score = await _lookup_puntaje(db, data.tipo)
        if score is not None:
            puntaje = score

    orden = Orden(
        tenant_id=tenant_id,
        numero=data.numero,
        fecha=fecha,
        placa=data.placa.strip().upper(),
        falla=data.falla.strip(),
        diagnostico=data.diagnostico.strip(),
        proceso=data.proceso.strip(),
        solucion=data.solucion.strip(),
        estado=estado,
        resultado=resultado,
        tipo=data.tipo.strip(),
        puntaje=puntaje,
        tipo_equipo=data.tipo_equipo.strip(),
        marca=data.marca.strip(),
        modelo=data.modelo.strip(),
    )
    db.add(orden)
    try:
        await db.flush()
        await db.refresh(orden)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "conflict",
                "detail": "Ya existe esa orden para esta empresa",
            },
        )
    return {"ok": True, "id": orden.id}


@router.put("/{orden_id}")
async def update_orden(
    orden_id: int,
    data: OrdenUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Update a work order. Handles legacy estado/resultado normalization."""
    result = await db.execute(
        select(Orden).where(Orden.id == orden_id, Orden.tenant_id == tenant_id)
    )
    orden = result.scalar_one_or_none()
    if not orden:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "detail": f"Order {orden_id} not found"},
        )

    update_data = data.model_dump(exclude_unset=True)

    # Auto-lookup puntaje if tipo is being changed
    if "tipo" in update_data and update_data["tipo"]:
        score = await _lookup_puntaje(db, update_data["tipo"])
        if score is not None:
            update_data["puntaje"] = score

    # Normalize legacy estado/resultado
    estado_val = update_data.get("estado", orden.estado)
    resultado_val = update_data.get("resultado", orden.resultado)
    norm_estado, norm_resultado = _normalize_estado_resultado(
        estado_val, resultado_val
    )
    update_data["estado"] = norm_estado
    update_data["resultado"] = norm_resultado

    for field, value in update_data.items():
        if isinstance(value, str):
            value = value.strip()
        if field == "placa":
            value = value.upper()
        setattr(orden, field, value)

    await db.flush()
    await db.refresh(orden)
    return {"ok": True}


@router.get("/export/csv")
async def export_ordenes_csv(
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Export all work orders as CSV for this tenant."""
    result = await db.execute(
        select(Orden).where(Orden.tenant_id == tenant_id).order_by(Orden.fecha.desc(), Orden.numero.desc())
    )
    ordenes = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Numero", "Fecha", "Placa", "Falla", "Diagnostico", "Proceso",
        "Solucion", "Estado", "Resultado", "Tipo", "Puntaje",
        "Tipo Equipo", "Marca", "Modelo", "Creado"
    ])
    for o in ordenes:
        writer.writerow([
            o.id, o.numero, o.fecha, o.placa, o.falla, o.diagnostico, o.proceso,
            o.solucion, o.estado, o.resultado, o.tipo, o.puntaje,
            o.tipo_equipo, o.marca, o.modelo, o.created_at,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reparaciones.csv"},
    )


@router.delete("/{orden_id}")
async def delete_orden(
    orden_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Delete a work order."""
    result = await db.execute(
        select(Orden).where(Orden.id == orden_id, Orden.tenant_id == tenant_id)
    )
    orden = result.scalar_one_or_none()
    if not orden:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "detail": f"Order {orden_id} not found"},
        )
    await db.delete(orden)
    await db.flush()
    return {"ok": True}


@router.post("/import", response_model=OrdenBulkImportResponse)
async def import_ordenes(
    data: OrdenBulkImport,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Bulk import orders from a list. Skips duplicates (by numero)."""
    importadas = 0
    for raw in data.ordenes:
        fecha = raw.get("fecha")
        orden_num = raw.get("orden")
        tipo = raw.get("tipo")
        if not all([fecha, orden_num, tipo]):
            continue

        # Check if order already exists for this tenant
        existing = await db.execute(
            select(Orden).where(
                Orden.tenant_id == tenant_id, Orden.numero == int(orden_num)
            )
        )
        if existing.scalar_one_or_none():
            continue

        # Look up puntaje
        score = await _lookup_puntaje(db, tipo)
        puntaje = score if score is not None else 1

        orden = Orden(
            tenant_id=tenant_id,
            numero=int(orden_num),
            fecha=fecha,
            tipo=tipo,
            puntaje=puntaje,
        )
        db.add(orden)
        importadas += 1

    if importadas > 0:
        await db.flush()

    return OrdenBulkImportResponse(ok=True, importadas=importadas)
