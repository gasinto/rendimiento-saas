"""
Boards router — Placas CRUD, notas-placa, mediciones-placa, bloques,
checklist, reorder, CSV export, backup/restore.

Replicates server.py: listar_placas, agregar_placa, actualizar_placa,
eliminar_placa, listar_notas_placa, agregar_nota_placa, actualizar_nota_placa,
eliminar_nota_placa, listar_mediciones_placa, agregar_medicion_placa,
actualizar_medicion_placa, eliminar_medicion_placa, check_medicion_placa,
reset_checklist_placa, renombrar_bloque, eliminar_bloque, listar_bloques,
crear_bloque, reordenar_medicion_placa, reordenar_nota_placa, reordenar_bloque.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.board import (
    BloquePlaca,
    MedicionPlaca,
    NotaPlaca,
    Placa,
)
from app.models.user import User

router = APIRouter(prefix="/api/boards", tags=["boards"])


# ── Schemas ──────────────────────────────────────────────────────────────


class PlacaOut(BaseModel):
    id: int
    modelo_placa: str
    tipo_equipo_id: int | None = None
    tipo_equipo_nombre: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PlacaCreate(BaseModel):
    modelo_placa: str
    tipo_equipo_id: int | None = None


class PlacaUpdate(BaseModel):
    modelo_placa: str | None = None
    tipo_equipo_id: int | None = None


class NotaPlacaOut(BaseModel):
    id: int
    modelo_placa: str
    contenido: str
    bloque: str = ""
    sort_order: int = 0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class NotaPlacaCreate(BaseModel):
    modelo_placa: str
    contenido: str
    bloque: str = ""


class NotaPlacaUpdate(BaseModel):
    contenido: str | None = None
    bloque: str | None = None


class MedicionPlacaOut(BaseModel):
    id: int
    modelo_placa: str
    punto_medicion: str
    nombre: str = ""
    valor_esperado: str = ""
    categoria: str = ""
    ic_referencia: str = ""
    notas: str = ""
    bloque: str = ""
    checked: bool = False
    sort_order: int = 0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class MedicionPlacaCreate(BaseModel):
    modelo_placa: str
    punto_medicion: str
    nombre: str = ""
    valor_esperado: str = ""
    categoria: str = ""
    ic_referencia: str = ""
    notas: str = ""
    bloque: str = ""


class MedicionPlacaUpdate(BaseModel):
    punto_medicion: str | None = None
    nombre: str | None = None
    valor_esperado: str | None = None
    categoria: str | None = None
    ic_referencia: str | None = None
    notas: str | None = None
    bloque: str | None = None


class CheckRequest(BaseModel):
    id: int
    checked: bool


class ResetChecklistRequest(BaseModel):
    modelo_placa: str


class BloqueOut(BaseModel):
    id: int
    modelo_placa: str
    nombre: str
    sort_order: int = 0


class BloqueCreate(BaseModel):
    modelo_placa: str
    nombre: str


class RenameBloqueRequest(BaseModel):
    modelo_placa: str
    old_name: str
    new_name: str


class DeleteBloqueRequest(BaseModel):
    modelo_placa: str
    name: str


class ReorderRequest(BaseModel):
    id: int
    direction: str  # "up" or "down"


class ReorderBloqueRequest(BaseModel):
    modelo_placa: str
    nombre: str
    direction: str  # "up" or "down"


# ════════════════════════════════════════════════════════════════════════
#  PLACAS
# ════════════════════════════════════════════════════════════════════════


@router.get("/placas")
async def list_placas(
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List boards (placas) with optional search by modelo. Global table."""
    if q:
        pat = f"%{q.upper()}%"
        result = await db.execute(
            text("""
                SELECT p.id, p.modelo_placa, p.tipo_equipo_id,
                       t.nombre as tipo_equipo_nombre, p.created_at
                FROM placas p LEFT JOIN tipos_equipo t ON t.id = p.tipo_equipo_id
                WHERE UPPER(p.modelo_placa) LIKE :q
                ORDER BY p.modelo_placa
            """),
            {"q": pat},
        )
    else:
        result = await db.execute(
            text("""
                SELECT p.id, p.modelo_placa, p.tipo_equipo_id,
                       t.nombre as tipo_equipo_nombre, p.created_at
                FROM placas p LEFT JOIN tipos_equipo t ON t.id = p.tipo_equipo_id
                ORDER BY p.modelo_placa
            """)
        )
    rows = result.fetchall()
    placas = [
        {
            "id": r[0],
            "modelo_placa": r[1],
            "tipo_equipo_id": r[2],
            "tipo_equipo_nombre": r[3],
            "created_at": r[4].isoformat() if r[4] else None,
        }
        for r in rows
    ]
    return {"placas": placas}


@router.post("/placas", status_code=status.HTTP_201_CREATED)
async def create_placa(
    data: PlacaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new board. modelo_placa is uppercased and stripped."""
    modelo = data.modelo_placa.strip().upper()
    if not modelo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "detail": "Falta modelo_placa"},
        )

    try:
        placa = Placa(
            modelo_placa=modelo,
            tipo_equipo_id=data.tipo_equipo_id,
        )
        db.add(placa)
        await db.flush()
        await db.refresh(placa)
        return {"ok": True, "id": placa.id}
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "conflict", "detail": "Ya existe esa placa"},
        )


@router.put("/placas/{placa_id}")
async def update_placa(
    placa_id: int,
    data: PlacaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a board."""
    result = await db.execute(select(Placa).where(Placa.id == placa_id))
    placa = result.scalar_one_or_none()
    if not placa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "detail": f"Placa {placa_id} not found"},
        )

    update_data = data.model_dump(exclude_unset=True)
    if "modelo_placa" in update_data:
        update_data["modelo_placa"] = update_data["modelo_placa"].strip().upper()
    for field, value in update_data.items():
        setattr(placa, field, value)
    await db.flush()
    return {"ok": True}


@router.delete("/placas/{placa_id}")
async def delete_placa(
    placa_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a board and all associated notes/measurements."""
    result = await db.execute(select(Placa).where(Placa.id == placa_id))
    placa = result.scalar_one_or_none()
    if not placa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "detail": "Placa no encontrada"},
        )

    modelo = placa.modelo_placa
    # Delete associated data
    await db.execute(
        text("DELETE FROM notas_placa WHERE modelo_placa = :m"), {"m": modelo}
    )
    await db.execute(
        text("DELETE FROM mediciones_placa WHERE modelo_placa = :m"), {"m": modelo}
    )
    await db.delete(placa)
    await db.flush()
    return {"ok": True}


# ════════════════════════════════════════════════════════════════════════
#  NOTAS DE PLACA
# ════════════════════════════════════════════════════════════════════════


@router.get("/notas")
async def list_notas(
    modelo_placa: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List board notes, optionally filtered by modelo_placa."""
    if modelo_placa:
        modelo = modelo_placa.strip().upper()
        result = await db.execute(
            text("""
                SELECT id, modelo_placa, contenido, bloque, created_at, sort_order
                FROM notas_placa
                WHERE modelo_placa = :m
                ORDER BY sort_order, created_at DESC
            """),
            {"m": modelo},
        )
    else:
        result = await db.execute(
            text("""
                SELECT id, modelo_placa, contenido, bloque, created_at, sort_order
                FROM notas_placa
                ORDER BY sort_order, created_at DESC
            """)
        )
    rows = result.fetchall()
    notas = [
        {
            "id": r[0],
            "modelo_placa": r[1],
            "contenido": r[2],
            "bloque": r[3] or "",
            "created_at": r[4].isoformat() if r[4] else None,
            "sort_order": r[5] or 0,
        }
        for r in rows
    ]
    return {"notas": notas}


@router.post("/notas", status_code=status.HTTP_201_CREATED)
async def create_nota(
    data: NotaPlacaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a board note with auto sort_order."""
    modelo = data.modelo_placa.strip().upper()
    contenido = data.contenido.strip()
    bloque = data.bloque.strip().upper()

    if not modelo or not contenido:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "detail": "Falta modelo_placa o contenido",
            },
        )

    # Auto-assign sort_order
    result = await db.execute(
        text("""
            SELECT COALESCE(MAX(sort_order), -1) + 1 FROM notas_placa
            WHERE modelo_placa = :m AND COALESCE(bloque, '') = :b
        """),
        {"m": modelo, "b": bloque},
    )
    next_sort = result.scalar() or 0

    nota = NotaPlaca(
        modelo_placa=modelo,
        contenido=contenido,
        bloque=bloque,
        sort_order=next_sort,
    )
    db.add(nota)
    await db.flush()
    await db.refresh(nota)
    return {"ok": True, "id": nota.id}


@router.put("/notas/{nota_id}")
async def update_nota(
    nota_id: int,
    data: NotaPlacaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a board note."""
    result = await db.execute(select(NotaPlaca).where(NotaPlaca.id == nota_id))
    nota = result.scalar_one_or_none()
    if not nota:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "detail": f"Nota {nota_id} not found"},
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(nota, field, value)
    await db.flush()
    return {"ok": True}


@router.delete("/notas/{nota_id}")
async def delete_nota(
    nota_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a board note."""
    result = await db.execute(select(NotaPlaca).where(NotaPlaca.id == nota_id))
    nota = result.scalar_one_or_none()
    if not nota:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "detail": f"Nota {nota_id} not found"},
        )
    await db.delete(nota)
    await db.flush()
    return {"ok": True}


@router.post("/notas/reorder")
async def reorder_nota(
    data: ReorderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reorder a note (up/down within same block)."""
    if data.direction not in ("up", "down"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "detail": "direction must be 'up' or 'down'"},
        )

    result = await db.execute(
        text("""
            SELECT id, modelo_placa, bloque, sort_order FROM notas_placa WHERE id = :nid
        """),
        {"nid": data.id},
    )
    item = result.fetchone()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "detail": "No encontrado"},
        )

    modelo, bloque, sort_order = item[1], item[2] or "", item[3] or 0

    if data.direction == "up":
        adj_result = await db.execute(
            text("""
                SELECT id, sort_order, 'medicion' as _t FROM mediciones_placa
                WHERE modelo_placa = :m AND COALESCE(bloque, '') = :b
                  AND sort_order IS NOT NULL AND sort_order < :so
                UNION ALL
                SELECT id, sort_order, 'nota' as _t FROM notas_placa
                WHERE modelo_placa = :m AND COALESCE(bloque, '') = :b
                  AND sort_order IS NOT NULL AND sort_order < :so AND id != :nid
                ORDER BY sort_order DESC LIMIT 1
            """),
            {"m": modelo, "b": bloque, "so": sort_order, "nid": data.id},
        )
    else:
        adj_result = await db.execute(
            text("""
                SELECT id, sort_order, 'medicion' as _t FROM mediciones_placa
                WHERE modelo_placa = :m AND COALESCE(bloque, '') = :b
                  AND sort_order IS NOT NULL AND sort_order > :so
                UNION ALL
                SELECT id, sort_order, 'nota' as _t FROM notas_placa
                WHERE modelo_placa = :m AND COALESCE(bloque, '') = :b
                  AND sort_order IS NOT NULL AND sort_order > :so AND id != :nid
                ORDER BY sort_order ASC LIMIT 1
            """),
            {"m": modelo, "b": bloque, "so": sort_order, "nid": data.id},
        )

    adj = adj_result.fetchone()
    if not adj:
        return {"ok": True, "swapped": False}

    # Swap sort orders
    await db.execute(
        text(
            "UPDATE {} SET sort_order = :so1 WHERE id = :id1".format(
                "notas_placa" if adj[2] == "nota" else "mediciones_placa"
            )
        ),
        {"so1": sort_order, "id1": adj[0]},
    )
    await db.execute(
        text("UPDATE notas_placa SET sort_order = :so2 WHERE id = :id2"),
        {"so2": adj[1], "id2": data.id},
    )
    await db.flush()
    return {"ok": True, "swapped": True}


# ════════════════════════════════════════════════════════════════════════
#  MEDICIONES DE PLACA
# ════════════════════════════════════════════════════════════════════════


@router.get("/measurements")
async def list_board_measurements(
    modelo: str | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List board measurements, filtered by modelo or search query."""
    if modelo:
        modelo_up = modelo.strip().upper()
        result = await db.execute(
            text("""
                SELECT id, modelo_placa, punto_medicion, nombre, valor_esperado,
                       categoria, ic_referencia, notas, bloque, checked,
                       created_at, sort_order
                FROM mediciones_placa
                WHERE UPPER(modelo_placa) = :m
                ORDER BY sort_order, punto_medicion
            """),
            {"m": modelo_up},
        )
    elif q:
        pat = f"%{q.upper()}%"
        result = await db.execute(
            text("""
                SELECT id, modelo_placa, punto_medicion, nombre, valor_esperado,
                       categoria, ic_referencia, notas, bloque, checked,
                       created_at, sort_order
                FROM mediciones_placa
                WHERE UPPER(modelo_placa) LIKE :q
                   OR UPPER(nombre) LIKE :q
                   OR UPPER(punto_medicion) LIKE :q
                   OR UPPER(ic_referencia) LIKE :q
                ORDER BY modelo_placa, sort_order, punto_medicion
            """),
            {"q": pat},
        )
    else:
        result = await db.execute(
            text("""
                SELECT id, modelo_placa, punto_medicion, nombre, valor_esperado,
                       categoria, ic_referencia, notas, bloque, checked,
                       created_at, sort_order
                FROM mediciones_placa
                ORDER BY modelo_placa, sort_order, punto_medicion
            """)
        )
    rows = result.fetchall()
    mediciones = [
        {
            "id": r[0],
            "modelo_placa": r[1],
            "punto_medicion": r[2],
            "nombre": r[3],
            "valor_esperado": r[4],
            "categoria": r[5],
            "ic_referencia": r[6],
            "notas": r[7],
            "bloque": r[8] or "",
            "checked": bool(r[9]),
            "created_at": r[10].isoformat() if r[10] else None,
            "sort_order": r[11] or 0,
        }
        for r in rows
    ]
    return {"mediciones": mediciones}


@router.post("/measurements", status_code=status.HTTP_201_CREATED)
async def create_board_measurement(
    data: MedicionPlacaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a board measurement point, with auto sort_order + upsert on duplicate."""
    modelo = data.modelo_placa.strip().upper()
    punto = data.punto_medicion.strip()
    bloque = data.bloque.strip().upper()

    if not modelo or not punto:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "detail": "Falta modelo_placa o punto_medicion",
            },
        )

    # Auto-assign sort_order
    result = await db.execute(
        text("""
            SELECT COALESCE(MAX(sort_order), -1) + 1 FROM mediciones_placa
            WHERE modelo_placa = :m AND COALESCE(bloque, '') = :b
        """),
        {"m": modelo, "b": bloque},
    )
    next_sort = result.scalar() or 0

    # Upsert on duplicate (modelo_placa, punto_medicion)
    existing = await db.execute(
        text("""
            SELECT id FROM mediciones_placa
            WHERE modelo_placa = :m AND punto_medicion = :p
        """),
        {"m": modelo, "p": punto},
    )
    if existing.fetchone():
        await db.execute(
            text("""
                UPDATE mediciones_placa SET
                    nombre = :nombre, valor_esperado = :ve,
                    categoria = :cat, ic_referencia = :ic,
                    notas = :notas, bloque = :bloque
                WHERE modelo_placa = :m AND punto_medicion = :p
            """),
            {
                "nombre": data.nombre.strip(),
                "ve": data.valor_esperado.strip(),
                "cat": data.categoria.strip(),
                "ic": data.ic_referencia.strip(),
                "notas": data.notas.strip(),
                "bloque": bloque,
                "m": modelo,
                "p": punto,
            },
        )
    else:
        medicion = MedicionPlaca(
            modelo_placa=modelo,
            punto_medicion=punto,
            nombre=data.nombre.strip(),
            valor_esperado=data.valor_esperado.strip(),
            categoria=data.categoria.strip(),
            ic_referencia=data.ic_referencia.strip(),
            notas=data.notas.strip(),
            bloque=bloque,
            sort_order=next_sort,
        )
        db.add(medicion)
    await db.flush()
    return {"ok": True}


@router.put("/measurements/{med_id}")
async def update_board_measurement(
    med_id: int,
    data: MedicionPlacaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a board measurement point."""
    result = await db.execute(
        select(MedicionPlaca).where(MedicionPlaca.id == med_id)
    )
    med = result.scalar_one_or_none()
    if not med:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "detail": f"Medicion {med_id} not found"},
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(med, field, value)
    await db.flush()
    return {"ok": True}


@router.delete("/measurements/{med_id}")
async def delete_board_measurement(
    med_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a board measurement point."""
    result = await db.execute(
        select(MedicionPlaca).where(MedicionPlaca.id == med_id)
    )
    med = result.scalar_one_or_none()
    if not med:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "detail": f"Medicion {med_id} not found"},
        )
    await db.delete(med)
    await db.flush()
    return {"ok": True}


@router.post("/measurements/check")
async def check_measurement(
    data: CheckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle checked status on a board measurement."""
    result = await db.execute(
        select(MedicionPlaca).where(MedicionPlaca.id == data.id)
    )
    med = result.scalar_one_or_none()
    if not med:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "detail": f"Medicion {data.id} not found"},
        )
    med.checked = data.checked
    await db.flush()
    return {"ok": True, "checked": data.checked}


@router.post("/measurements/reset-checklist")
async def reset_checklist(
    data: ResetChecklistRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reset all checked statuses for a board model."""
    modelo = data.modelo_placa.strip().upper()
    if not modelo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "detail": "Falta modelo_placa",
            },
        )
    await db.execute(
        text("UPDATE mediciones_placa SET checked = false WHERE modelo_placa = :m"),
        {"m": modelo},
    )
    await db.flush()
    return {"ok": True}


@router.post("/measurements/reorder")
async def reorder_measurement(
    data: ReorderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reorder a measurement (up/down within same block, mixed with notes)."""
    if data.direction not in ("up", "down"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "detail": "direction must be 'up' or 'down'",
            },
        )

    result = await db.execute(
        text("""
            SELECT id, modelo_placa, bloque, sort_order FROM mediciones_placa WHERE id = :mid
        """),
        {"mid": data.id},
    )
    item = result.fetchone()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "detail": "No encontrado"},
        )

    modelo, bloque, sort_order = item[1], item[2] or "", item[3] or 0

    if data.direction == "up":
        adj_result = await db.execute(
            text("""
                SELECT id, sort_order, 'medicion' as _t FROM mediciones_placa
                WHERE modelo_placa = :m AND COALESCE(bloque, '') = :b
                  AND sort_order IS NOT NULL AND sort_order < :so
                UNION ALL
                SELECT id, sort_order, 'nota' as _t FROM notas_placa
                WHERE modelo_placa = :m AND COALESCE(bloque, '') = :b
                  AND sort_order IS NOT NULL AND sort_order < :so
                ORDER BY sort_order DESC LIMIT 1
            """),
            {"m": modelo, "b": bloque, "so": sort_order},
        )
    else:
        adj_result = await db.execute(
            text("""
                SELECT id, sort_order, 'medicion' as _t FROM mediciones_placa
                WHERE modelo_placa = :m AND COALESCE(bloque, '') = :b
                  AND sort_order IS NOT NULL AND sort_order > :so
                UNION ALL
                SELECT id, sort_order, 'nota' as _t FROM notas_placa
                WHERE modelo_placa = :m AND COALESCE(bloque, '') = :b
                  AND sort_order IS NOT NULL AND sort_order > :so
                ORDER BY sort_order ASC LIMIT 1
            """),
            {"m": modelo, "b": bloque, "so": sort_order},
        )

    adj = adj_result.fetchone()
    if not adj:
        return {"ok": True, "swapped": False}

    # Swap sort orders
    adj_table = "notas_placa" if adj[2] == "nota" else "mediciones_placa"
    await db.execute(
        text(f"UPDATE {adj_table} SET sort_order = :so1 WHERE id = :id1"),
        {"so1": sort_order, "id1": adj[0]},
    )
    await db.execute(
        text("UPDATE mediciones_placa SET sort_order = :so2 WHERE id = :id2"),
        {"so2": adj[1], "id2": data.id},
    )
    await db.flush()
    return {"ok": True, "swapped": True}


# ════════════════════════════════════════════════════════════════════════
#  BLOQUES
# ════════════════════════════════════════════════════════════════════════


@router.get("/blocks")
async def list_blocks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all block groupings for boards."""
    result = await db.execute(
        text("""
            SELECT id, modelo_placa, nombre, sort_order
            FROM bloques_placa
            ORDER BY modelo_placa, sort_order, nombre
        """)
    )
    rows = result.fetchall()
    bloques = [
        {
            "id": r[0],
            "modelo_placa": r[1],
            "nombre": r[2],
            "sort_order": r[3] or 0,
        }
        for r in rows
    ]
    return {"bloques": bloques}


@router.post("/blocks")
async def create_block(
    data: BloqueCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new block for a board model."""
    modelo = data.modelo_placa.strip().upper()
    nombre = data.nombre.strip().upper()

    if not modelo or not nombre:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "detail": "Falta modelo_placa o nombre",
            },
        )

    # Auto-assign sort_order
    result = await db.execute(
        text("""
            SELECT COALESCE(MAX(sort_order), -1) + 1 FROM bloques_placa
            WHERE modelo_placa = :m
        """),
        {"m": modelo},
    )
    max_order = result.scalar() or 0

    try:
        bloque = BloquePlaca(
            modelo_placa=modelo, nombre=nombre, sort_order=max_order
        )
        db.add(bloque)
        await db.flush()
    except Exception:
        await db.rollback()
    return {"ok": True}


@router.post("/blocks/rename")
async def rename_block(
    data: RenameBloqueRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rename a block across all associated tables."""
    modelo = data.modelo_placa.strip().upper()
    old = data.old_name.strip().upper()
    new = data.new_name.strip().upper()

    if not modelo or not old or not new:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "detail": "Faltan datos"},
        )

    await db.execute(
        text(
            "UPDATE mediciones_placa SET bloque = :new WHERE modelo_placa = :m AND bloque = :old"
        ),
        {"new": new, "m": modelo, "old": old},
    )
    await db.execute(
        text(
            "UPDATE notas_placa SET bloque = :new WHERE modelo_placa = :m AND bloque = :old"
        ),
        {"new": new, "m": modelo, "old": old},
    )
    await db.execute(
        text(
            "UPDATE bloques_placa SET nombre = :new WHERE modelo_placa = :m AND nombre = :old"
        ),
        {"new": new, "m": modelo, "old": old},
    )
    await db.flush()
    return {"ok": True}


@router.post("/blocks/delete")
async def delete_block(
    data: DeleteBloqueRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a block (unlinks from measurements and notes)."""
    modelo = data.modelo_placa.strip().upper()
    name = data.name.strip().upper()

    if not modelo or not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "detail": "Faltan datos"},
        )

    await db.execute(
        text(
            "UPDATE mediciones_placa SET bloque = '' WHERE modelo_placa = :m AND bloque = :name"
        ),
        {"m": modelo, "name": name},
    )
    await db.execute(
        text(
            "UPDATE notas_placa SET bloque = '' WHERE modelo_placa = :m AND bloque = :name"
        ),
        {"m": modelo, "name": name},
    )
    await db.execute(
        text("DELETE FROM bloques_placa WHERE modelo_placa = :m AND nombre = :name"),
        {"m": modelo, "name": name},
    )
    await db.flush()
    return {"ok": True}


@router.post("/blocks/reorder")
async def reorder_block(
    data: ReorderBloqueRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reorder a block (up/down)."""
    if data.direction not in ("up", "down"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "detail": "direction must be 'up' or 'down'",
            },
        )

    modelo = data.modelo_placa.strip().upper()
    nombre = data.nombre.strip().upper()

    result = await db.execute(
        text("""
            SELECT id, sort_order FROM bloques_placa
            WHERE modelo_placa = :m AND nombre = :n
        """),
        {"m": modelo, "n": nombre},
    )
    item = result.fetchone()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "detail": "Bloque no encontrado"},
        )

    sort_order = item[1] or 0

    if data.direction == "up":
        adj_result = await db.execute(
            text("""
                SELECT id, sort_order FROM bloques_placa
                WHERE modelo_placa = :m AND sort_order IS NOT NULL AND sort_order < :so
                ORDER BY sort_order DESC LIMIT 1
            """),
            {"m": modelo, "so": sort_order},
        )
    else:
        adj_result = await db.execute(
            text("""
                SELECT id, sort_order FROM bloques_placa
                WHERE modelo_placa = :m AND sort_order IS NOT NULL AND sort_order > :so
                ORDER BY sort_order ASC LIMIT 1
            """),
            {"m": modelo, "so": sort_order},
        )

    adj = adj_result.fetchone()
    if not adj:
        return {"ok": True, "swapped": False}

    # Swap
    await db.execute(
        text("UPDATE bloques_placa SET sort_order = :so1 WHERE id = :id1"),
        {"so1": adj[1], "id1": item[0]},
    )
    await db.execute(
        text("UPDATE bloques_placa SET sort_order = :so2 WHERE id = :id2"),
        {"so2": sort_order, "id2": adj[0]},
    )
    await db.flush()
    return {"ok": True, "swapped": True}
