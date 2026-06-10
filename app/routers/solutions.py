"""
Solutions router — Soluciones CRUD with search + report TXT generation.

Replicates server.py APIHandler: listar_soluciones, agregar_solucion,
actualizar_solucion, eliminar_solucion, generar_reporte_solucion.
View count tracking included.
"""

import json
import textwrap
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.solution import Solucion
from app.models.user import User

router = APIRouter(prefix="/api/solutions", tags=["solutions"])


# ── Schemas ──────────────────────────────────────────────────────────────


class SolucionOut(BaseModel):
    id: int
    placa: str
    falla: str = ""
    solucion: str = ""
    ics: str = "[]"
    views: int = 0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class SolucionCreate(BaseModel):
    placa: str
    falla: str = ""
    solucion: str = ""
    ics: list[str] = []


class SolucionUpdate(BaseModel):
    placa: str | None = None
    falla: str | None = None
    solucion: str | None = None
    ics: list[str] | None = None


class ReporteResponse(BaseModel):
    contenido: str
    nombre_archivo: str


# ── Helpers for TXT report ──────────────────────────────────────────────


def _r_line(c: str = "─", w: int = 62) -> str:
    return "  " + c * w + "\n"


def _r_title(text: str, sep: str = "═", w: int = 62) -> str:
    pad = w - len(text) - 2
    if pad < 2:
        pad = 2
    left = pad // 2
    right = pad - left
    return "  " + sep * left + " " + text + " " + sep * right + "\n"


def _r_section(title: str, body_lines: list[str], w: int = 60) -> str:
    if not body_lines:
        return ""
    top = "  ┌─ " + title + " " + "─" * (w - 4 - len(title)) + "┐\n"
    mid = ""
    for line in body_lines:
        mid += "  │ " + str(line).ljust(w - 2) + "│\n"
    bot = "  └" + "─" * w + "┘\n\n"
    return top + mid + bot


def _r_wrap(text: str | None, w: int = 58) -> list[str]:
    if not text:
        return []
    lines = []
    for p in str(text).split("\n"):
        if not p.strip():
            lines.append("")
            continue
        lines.extend(textwrap.wrap(p.strip(), width=w))
    return lines


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/")
async def list_soluciones(
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List solutions with optional full-text search."""
    if q:
        pat = f"%{q.upper()}%"
        result = await db.execute(
            text("""
                SELECT id, placa, falla, solucion, ics, views, created_at
                FROM soluciones
                WHERE UPPER(placa) LIKE :q
                   OR UPPER(falla) LIKE :q
                   OR UPPER(solucion) LIKE :q
                   OR UPPER(ics) LIKE :q
                ORDER BY created_at DESC
            """),
            {"q": pat},
        )
    else:
        result = await db.execute(
            text("""
                SELECT id, placa, falla, solucion, ics, views, created_at
                FROM soluciones
                ORDER BY created_at DESC
            """)
        )

    rows = result.fetchall()
    soluciones = [
        {
            "id": r[0],
            "placa": r[1],
            "falla": r[2] or "",
            "solucion": r[3] or "",
            "ics": r[4] or "[]",
            "views": r[5] or 0,
            "created_at": r[6].isoformat() if r[6] else None,
        }
        for r in rows
    ]
    return {"soluciones": soluciones}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_solucion(
    data: SolucionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new solution."""
    placa = data.placa.strip().upper()
    if not placa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "detail": "Falta placa"},
        )

    solucion = Solucion(
        placa=placa,
        falla=data.falla.strip(),
        solucion=data.solucion.strip(),
        ics=json.dumps(data.ics),
    )
    db.add(solucion)
    await db.flush()
    await db.refresh(solucion)
    return {"ok": True, "id": solucion.id}


@router.put("/{solucion_id}")
async def update_solucion(
    solucion_id: int,
    data: SolucionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a solution."""
    result = await db.execute(
        select(Solucion).where(Solucion.id == solucion_id)
    )
    solucion = result.scalar_one_or_none()
    if not solucion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "detail": f"Solucion {solucion_id} not found",
            },
        )

    update_data = data.model_dump(exclude_unset=True)
    if "placa" in update_data:
        update_data["placa"] = update_data["placa"].strip().upper()
    if "ics" in update_data:
        update_data["ics"] = json.dumps(update_data["ics"])
    if "falla" in update_data:
        update_data["falla"] = update_data["falla"].strip()
    if "solucion" in update_data:
        update_data["solucion"] = update_data["solucion"].strip()

    for field, value in update_data.items():
        setattr(solucion, field, value)
    await db.flush()
    return {"ok": True}


@router.delete("/{solucion_id}")
async def delete_solucion(
    solucion_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a solution."""
    result = await db.execute(
        select(Solucion).where(Solucion.id == solucion_id)
    )
    solucion = result.scalar_one_or_none()
    if not solucion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "detail": f"Solucion {solucion_id} not found",
            },
        )
    await db.delete(solucion)
    await db.flush()
    return {"ok": True}


@router.get("/{solucion_id}/report", response_model=ReporteResponse)
async def generate_report(
    solucion_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a TXT report for a solution. Includes board measurements and notes."""
    result = await db.execute(
        select(Solucion).where(Solucion.id == solucion_id)
    )
    solucion = result.scalar_one_or_none()
    if not solucion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "detail": f"Solucion {solucion_id} not found",
            },
        )

    # Increment view count
    await db.execute(
        text("UPDATE soluciones SET views = COALESCE(views, 0) + 1 WHERE id = :sid"),
        {"sid": solucion_id},
    )
    await db.flush()

    w = 62
    wr = 58

    try:
        ics_list = json.loads(solucion.ics) if solucion.ics else []
    except (json.JSONDecodeError, TypeError):
        ics_list = []

    ics_str = ", ".join(ics_list) if ics_list else "—"
    fecha = (
        solucion.created_at.strftime("%Y-%m-%d")
        if solucion.created_at
        else datetime.now().strftime("%Y-%m-%d")
    )
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    placa = solucion.placa

    lines = []
    lines.append(_r_line("█", w))
    lines.append(_r_title("INFORME TÉCNICO — SOLUCIÓN", "█", w))
    lines.append(_r_line("█", w))
    lines.append("")
    lines.append("  Fecha del informe :  " + now_str)
    lines.append("")

    lines.append(
        _r_section("PLACA", ["Modelo          :  " + placa], w)
    )
    lines.append(
        _r_section("FALLA REPORTADA", _r_wrap(solucion.falla, wr), w)
    )
    lines.append(
        _r_section("SOLUCIÓN APLICADA", _r_wrap(solucion.solucion, wr), w)
    )
    if ics_list:
        lines.append(
            _r_section("CIRCUITOS INTEGRADOS", [ics_str], w)
        )
    lines.append(_r_section("FECHA DE CARGA", [fecha], w))

    # Board measurements
    result = await db.execute(
        text("""
            SELECT punto_medicion, nombre, valor_esperado, categoria,
                   ic_referencia, notas, bloque
            FROM mediciones_placa
            WHERE modelo_placa = :m
            ORDER BY sort_order, punto_medicion
        """),
        {"m": placa},
    )
    meds = result.fetchall()
    if meds:
        lines.append(_r_title("MEDICIONES DE LA PLACA", "─", w))
        lines.append("")
        current_block = None
        for m in meds:
            bloque = m[6] or "—"
            if bloque != current_block:
                if current_block is not None:
                    lines.append("")
                lines.append("  ▸ Bloque: " + bloque)
                lines.append(_r_line("·", w - 2))
                current_block = bloque
            punto = m[0] or ""
            nombre = m[1] or ""
            esperado = m[2] or ""
            cat = m[3] or ""
            ic = m[4] or ""
            nts = m[5] or ""
            lines.append("    " + punto + (" – " + nombre if nombre else ""))
            if esperado or cat:
                lines.append(
                    "      Valor: " + esperado + ("  |  " + cat if cat else "")
                )
            if ic:
                lines.append("      IC: " + ic)
            if nts:
                for wrapped in _r_wrap(nts, wr - 4):
                    lines.append("      " + wrapped)
        lines.append("")

    # Board notes
    result = await db.execute(
        text("""
            SELECT contenido, bloque, created_at
            FROM notas_placa
            WHERE modelo_placa = :m
            ORDER BY sort_order, created_at DESC
        """),
        {"m": placa},
    )
    notas = result.fetchall()
    if notas:
        lines.append(_r_title("NOTAS DE LA PLACA", "─", w))
        lines.append("")
        current_block = None
        for nt in notas:
            bloque = nt[1] or "—"
            if bloque != current_block:
                if current_block is not None:
                    lines.append("")
                lines.append("  ▸ Bloque: " + bloque)
                lines.append(_r_line("·", w - 2))
                current_block = bloque
            for wrapped in _r_wrap(nt[0], wr):
                lines.append("    " + wrapped)
        lines.append("")

    lines.append(_r_line("═", w))
    lines.append("  Generado por :  Sistema de Rendimiento — NSP Notebooks")
    lines.append(_r_line("═", w))

    return ReporteResponse(
        contenido="\n".join(lines),
        nombre_archivo=f"informe_{placa.replace('/', '_')}.txt",
    )
