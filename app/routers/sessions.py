"""
Session timer router — start/pause/finish, pendiente, stats.

Replicates server.py APIHandler: iniciar_sesion, pausar_sesion,
finalizar_sesion, listar_sesiones, sesion_pendiente, tiempos_reparacion.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_current_tenant
from app.models.order import SesionReparacion, Orden
from app.models.user import User

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# ── Schemas ──────────────────────────────────────────────────────────────


class SesionOut(BaseModel):
    id: int
    orden_id: int
    tenant_id: int | None = None
    inicio: str
    fin: str | None = None
    duracion_segundos: int | None = 0
    notas: str = ""
    estado: str = "activa"
    created_at: datetime | None = None
    numero: int | None = None
    placa: str | None = None
    duracion_total: int | None = None

    model_config = {"from_attributes": True}


class SesionStartRequest(BaseModel):
    orden_id: int


class SesionPauseRequest(BaseModel):
    id: int
    duracion_segundos: int = 0
    notas: str = ""


class SesionFinishRequest(BaseModel):
    id: int
    duracion_segundos: int = 0
    notas: str = ""


class PendienteResponse(BaseModel):
    sesion: SesionOut | None = None


class TiemposResponse(BaseModel):
    promedio_general: int = 0
    total_sesiones: int = 0
    por_tipo: list[dict[str, Any]] = []


# ── Endpoints ────────────────────────────────────────────────────────────


@router.post("/start")
async def start_session(
    data: SesionStartRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Start or resume a repair session for an order."""
    orden_id = data.orden_id

    # Verify order exists
    result = await db.execute(
        select(Orden).where(Orden.id == orden_id, Orden.tenant_id == tenant_id)
    )
    orden = result.scalar_one_or_none()
    if not orden:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "detail": "Orden no encontrada"},
        )

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Check for PAUSED session to resume
    result = await db.execute(
        select(SesionReparacion)
        .where(
            SesionReparacion.orden_id == orden_id,
            SesionReparacion.estado == "pausada",
        )
        .order_by(SesionReparacion.inicio.desc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing:
        # Resume it
        acumulado = existing.duracion_segundos or 0
        existing.estado = "activa"
        existing.inicio = ahora
        existing.fin = None
        await db.flush()
        return {
            "ok": True,
            "id": existing.id,
            "inicio": ahora,
            "duracion_acumulada": acumulado,
        }

    # Create new session
    sesion = SesionReparacion(
        orden_id=orden_id,
        tenant_id=tenant_id,
        inicio=ahora,
        estado="activa",
    )
    db.add(sesion)
    await db.flush()
    await db.refresh(sesion)
    return {
        "ok": True,
        "id": sesion.id,
        "inicio": ahora,
        "duracion_acumulada": 0,
    }


@router.post("/pause")
async def pause_session(
    data: SesionPauseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pause an active session."""
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    result = await db.execute(
        select(SesionReparacion).where(
            SesionReparacion.id == data.id,
            SesionReparacion.estado == "activa",
        )
    )
    sesion = result.scalar_one_or_none()
    if not sesion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "not_found",
                "detail": "Sesion no encontrada o ya finalizada",
            },
        )

    sesion.fin = ahora
    sesion.duracion_segundos = data.duracion_segundos
    sesion.notas = data.notas
    sesion.estado = "pausada"
    await db.flush()
    return {"ok": True, "fin": ahora, "duracion_segundos": data.duracion_segundos}


@router.post("/finish")
async def finish_session(
    data: SesionFinishRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Finish (complete) a session."""
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    result = await db.execute(
        select(SesionReparacion).where(SesionReparacion.id == data.id)
    )
    sesion = result.scalar_one_or_none()
    if not sesion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "not_found", "detail": "Sesion no encontrada"},
        )

    sesion.fin = ahora
    sesion.duracion_segundos = data.duracion_segundos
    sesion.notas = data.notas
    sesion.estado = "finalizada"
    await db.flush()
    return {"ok": True, "fin": ahora}


@router.get("/")
async def list_sessions(
    orden_id: int | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List sessions, optionally filtered by order_id."""
    stmt = select(SesionReparacion).order_by(SesionReparacion.inicio.desc())
    if orden_id:
        stmt = stmt.where(SesionReparacion.orden_id == orden_id)
    else:
        stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    sesiones = result.scalars().all()
    return {"sesiones": sesiones}


@router.get("/pending", response_model=PendienteResponse)
async def get_pending_session(
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Get the latest non-finalized session (activa or pausada) with calculated duration."""
    # Using raw SQL for the JOIN with ordenes
    result = await db.execute(
        text("""
            SELECT s.*, o.numero, o.placa
            FROM sesiones_reparacion s
            JOIN ordenes o ON s.orden_id = o.id
            WHERE s.estado IN ('activa', 'pausada')
            AND (s.tenant_id = :tid OR s.tenant_id IS NULL)
            ORDER BY s.inicio DESC
            LIMIT 1
        """),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    if not row:
        return PendienteResponse(sesion=None)

    sesion_dict = dict(row._mapping)
    ahora = datetime.now()

    if sesion_dict["estado"] == "activa":
        inicio = datetime.strptime(sesion_dict["inicio"], "%Y-%m-%d %H:%M:%S")
        elapsed = (ahora - inicio).total_seconds()
        sesion_dict["duracion_total"] = (sesion_dict.get("duracion_segundos") or 0) + int(
            elapsed
        )
    else:
        sesion_dict["duracion_total"] = sesion_dict.get("duracion_segundos") or 0

    return PendienteResponse(sesion=SesionOut(**sesion_dict))


@router.get("/stats")
async def session_stats(
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Session time statistics — averages, totals, breakdown by type."""
    # General average
    result = await db.execute(
        text("""
            SELECT AVG(duracion_segundos) as promedio, COUNT(*) as total
            FROM sesiones_reparacion
            WHERE duracion_segundos > 0 AND (tenant_id = :tid OR tenant_id IS NULL)
        """),
        {"tid": tenant_id},
    )
    general = result.fetchone()
    promedio = round(float(general[0])) if general and general[0] else 0
    total = general[1] if general else 0

    # Average by repair type
    result = await db.execute(
        text("""
            SELECT o.tipo, AVG(s.duracion_segundos) as promedio, COUNT(*) as total
            FROM sesiones_reparacion s
            JOIN ordenes o ON s.orden_id = o.id
            WHERE s.duracion_segundos > 0
              AND o.tipo != ''
              AND (s.tenant_id = :tid OR s.tenant_id IS NULL)
            GROUP BY o.tipo
            ORDER BY total DESC
        """),
        {"tid": tenant_id},
    )
    por_tipo = [{"tipo": r[0], "promedio": round(float(r[1])), "total": r[2]} for r in result.fetchall()]

    return TiemposResponse(
        promedio_general=promedio, total_sesiones=total, por_tipo=por_tipo
    )
