"""
Dashboard router — summary, trends, top types/marcas/modelos/placas, success rate.

Replicates server.py APIHandler: dashboard.
"""

import calendar
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_current_tenant
from app.models.user import User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ── Schemas ──────────────────────────────────────────────────────────────


class MesActual(BaseModel):
    mes: str
    equipos: int = 0
    dias: int = 0
    puntos: float = 0
    ganancia: float = 0
    promedio_pts_dia: float = 0
    promedio_equipos_dia: float = 0


class TendenciaItem(BaseModel):
    mes: str
    equipos: int = 0
    puntos: float = 0
    ganancia: float = 0


class GananciaAcumulada(BaseModel):
    mes: str
    acumulado: float = 0


class TopItem(BaseModel):
    tipo: str | None = None
    marca: str | None = None
    modelo: str | None = None
    placa: str | None = None
    total: int = 0
    puntos: float | None = 0


class TasaExitoMensual(BaseModel):
    mes: str
    total: int = 0
    reparados: int = 0
    no_reparados: int = 0
    en_curso: int = 0
    porcentaje_exito: float = 0


class DashboardResponse(BaseModel):
    mes_actual: MesActual
    tendencia: list[TendenciaItem]
    top_tipos: list[TopItem]
    ganancia_acumulada: list[GananciaAcumulada]
    resumen_anual: dict[str, Any]
    tasa_exito_mensual: list[TasaExitoMensual]
    tasa_exito_anual: dict[str, Any]
    top_marcas: list[TopItem]
    top_modelos: list[TopItem]
    top_placas: list[TopItem]


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Dashboard with 10 query blocks in a single response."""

    # valor_punto
    result = await db.execute(
        text("SELECT valor FROM config WHERE tenant_id = :tid AND clave = 'valor_punto'"),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    valor_punto = float(row[0]) if row else 2000

    # 1. Current month summary (from reparaciones)
    result = await db.execute(
        text("""
            SELECT TO_CHAR(fecha, 'YYYY-MM') as mes,
                   COUNT(*) as equipos,
                   COUNT(DISTINCT fecha) as dias,
                   SUM(puntaje) as puntos
            FROM reparaciones
            WHERE tenant_id = :tid
              AND TO_CHAR(fecha, 'YYYY-MM') = TO_CHAR(CURRENT_DATE, 'YYYY-MM')
            GROUP BY mes
        """),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    now = datetime.now()
    _, days_in_month = calendar.monthrange(now.year, now.month)

    if row:
        mes_actual = MesActual(
            mes=row[0],
            equipos=row[1],
            dias=row[2],
            puntos=float(row[3] or 0),
            ganancia=round(float(row[3] or 0) * valor_punto, 2),
            promedio_pts_dia=round(float(row[3] or 0) / days_in_month, 2)
            if days_in_month > 0
            else 0,
            promedio_equipos_dia=round(row[1] / row[2], 2) if row[2] > 0 else 0,
        )
    else:
        mes_actual = MesActual(
            mes=now.strftime("%Y-%m"),
            equipos=0,
            puntos=0,
            ganancia=0,
            promedio_pts_dia=0,
            promedio_equipos_dia=0,
        )

    # 2. Trend (last 12 months)
    result = await db.execute(
        text("""
            SELECT TO_CHAR(fecha, 'YYYY-MM') as mes,
                   COUNT(*) as equipos,
                   SUM(puntaje) as puntos
            FROM reparaciones
            WHERE tenant_id = :tid
              AND fecha >= CURRENT_DATE - INTERVAL '12 months'
            GROUP BY mes
            ORDER BY mes ASC
        """),
        {"tid": tenant_id},
    )
    tendencia = []
    for r in result.fetchall():
        pts = float(r[2] or 0)
        tendencia.append(
            TendenciaItem(
                mes=r[0],
                equipos=r[1],
                puntos=pts,
                ganancia=round(pts * valor_punto, 2),
            )
        )

    # 3. Top 5 types
    result = await db.execute(
        text("""
            SELECT tipo, COUNT(*) as total, SUM(puntaje) as puntos
            FROM reparaciones
            WHERE tenant_id = :tid
            GROUP BY tipo
            ORDER BY total DESC
            LIMIT 5
        """),
        {"tid": tenant_id},
    )
    top_tipos = [
        TopItem(tipo=r[0], total=r[1], puntos=float(r[2] or 0))
        for r in result.fetchall()
    ]

    # 4. Accumulated gain (running sum over trend)
    ganancia_acumulada = []
    running = 0.0
    for t in tendencia:
        running += t.ganancia
        ganancia_acumulada.append(GananciaAcumulada(mes=t.mes, acumulado=round(running, 2)))

    # 5. Annual summary
    result = await db.execute(
        text("""
            SELECT TO_CHAR(fecha, 'YYYY') as anio,
                   COUNT(*) as equipos,
                   SUM(puntaje) as puntos
            FROM reparaciones
            WHERE tenant_id = :tid
              AND TO_CHAR(fecha, 'YYYY') = TO_CHAR(CURRENT_DATE, 'YYYY')
            GROUP BY anio
        """),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    if row:
        resumen_anual = {
            "anio": row[0],
            "equipos": row[1],
            "puntos": float(row[2] or 0),
            "ganancia": round(float(row[2] or 0) * valor_punto, 2),
        }
    else:
        resumen_anual = {
            "anio": now.strftime("%Y"),
            "equipos": 0,
            "puntos": 0,
            "ganancia": 0,
        }

    # 6. Monthly success rate (last 12 months from ordenes)
    result = await db.execute(
        text("""
            SELECT TO_CHAR(fecha, 'YYYY-MM') as mes,
                   COUNT(*) as total,
                   SUM(CASE WHEN resultado = 'reparado' THEN 1 ELSE 0 END) as reparados,
                   SUM(CASE WHEN resultado = 'no_reparado' THEN 1 ELSE 0 END) as no_reparados,
                   SUM(CASE WHEN estado = 'en_curso' THEN 1 ELSE 0 END) as en_curso
            FROM ordenes
            WHERE tenant_id = :tid
              AND fecha >= CURRENT_DATE - INTERVAL '12 months'
            GROUP BY mes
            ORDER BY mes ASC
        """),
        {"tid": tenant_id},
    )
    tasa_exito_mensual = []
    for r in result.fetchall():
        d = {
            "mes": r[0],
            "total": r[1],
            "reparados": r[2],
            "no_reparados": r[3],
            "en_curso": r[4],
        }
        denom = d["total"] - d["en_curso"]
        d["porcentaje_exito"] = round(d["reparados"] / denom * 100, 2) if denom > 0 else 0
        tasa_exito_mensual.append(TasaExitoMensual(**d))

    # 7. Annual success rate
    result = await db.execute(
        text("""
            SELECT TO_CHAR(fecha, 'YYYY') as anio,
                   COUNT(*) as total,
                   SUM(CASE WHEN resultado = 'reparado' THEN 1 ELSE 0 END) as reparados,
                   SUM(CASE WHEN resultado = 'no_reparado' THEN 1 ELSE 0 END) as no_reparados,
                   SUM(CASE WHEN estado = 'en_curso' THEN 1 ELSE 0 END) as en_curso
            FROM ordenes
            WHERE tenant_id = :tid
            GROUP BY anio
            ORDER BY anio DESC
        """),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    if row:
        denom = row[1] - row[4]
        tasa_exito_anual = {
            "anio": row[0],
            "total": row[1],
            "reparados": row[2],
            "no_reparados": row[3],
            "en_curso": row[4],
            "porcentaje_exito": round(row[2] / denom * 100, 2) if denom > 0 else 0,
        }
    else:
        tasa_exito_anual = {
            "anio": "",
            "total": 0,
            "reparados": 0,
            "no_reparados": 0,
            "en_curso": 0,
            "porcentaje_exito": 0,
        }

    # 8. Top marcas
    result = await db.execute(
        text("""
            SELECT COALESCE(NULLIF(marca, ''), '—') as marca, COUNT(*) as total
            FROM ordenes
            WHERE tenant_id = :tid AND marca IS NOT NULL AND marca != ''
            GROUP BY marca
            ORDER BY total DESC
            LIMIT 5
        """),
        {"tid": tenant_id},
    )
    top_marcas = [TopItem(marca=r[0], total=r[1]) for r in result.fetchall()]

    # 9. Top modelos
    result = await db.execute(
        text("""
            SELECT COALESCE(NULLIF(modelo, ''), '—') as modelo, COUNT(*) as total
            FROM ordenes
            WHERE tenant_id = :tid AND modelo IS NOT NULL AND modelo != ''
            GROUP BY modelo
            ORDER BY total DESC
            LIMIT 5
        """),
        {"tid": tenant_id},
    )
    top_modelos = [TopItem(modelo=r[0], total=r[1]) for r in result.fetchall()]

    # 10. Top placas
    result = await db.execute(
        text("""
            SELECT COALESCE(NULLIF(placa, ''), '—') as placa, COUNT(*) as total
            FROM ordenes
            WHERE tenant_id = :tid AND placa IS NOT NULL AND placa != ''
            GROUP BY placa
            ORDER BY total DESC
            LIMIT 5
        """),
        {"tid": tenant_id},
    )
    top_placas = [TopItem(placa=r[0], total=r[1]) for r in result.fetchall()]

    return DashboardResponse(
        mes_actual=mes_actual,
        tendencia=tendencia,
        top_tipos=top_tipos,
        ganancia_acumulada=ganancia_acumulada,
        resumen_anual=resumen_anual,
        tasa_exito_mensual=tasa_exito_mensual,
        tasa_exito_anual=tasa_exito_anual,
        top_marcas=top_marcas,
        top_modelos=top_modelos,
        top_placas=top_placas,
    )
