"""
ICs (Circuitos) router — CRUD with search, info_detallada.

Replicates server.py APIHandler: listar_circuitos, agregar_circuito,
actualizar_circuito, eliminar_circuito.
Global table — no tenant isolation.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.ic import Circuito
from app.models.user import User

router = APIRouter(prefix="/api/ics", tags=["ics"])


# ── Schemas ──────────────────────────────────────────────────────────────


class CircuitoOut(BaseModel):
    id: int
    codigo: str
    descripcion: str = ""
    placa: str
    cantidad: int = 1
    info_detallada: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CircuitoCreate(BaseModel):
    codigo: str
    placa: str
    descripcion: str = ""
    cantidad: int = 1
    info_detallada: str = ""


class CircuitoUpdate(BaseModel):
    codigo: str | None = None
    descripcion: str | None = None
    placa: str | None = None
    cantidad: int | None = None
    info_detallada: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/")
async def list_circuitos(
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List ICs (circuitos) with optional full-text search."""
    if q:
        pat = f"%{q.upper()}%"
        result = await db.execute(
            text("""
                SELECT id, codigo, descripcion, placa, cantidad, created_at, info_detallada
                FROM circuitos
                WHERE UPPER(codigo) LIKE :q OR UPPER(descripcion) LIKE :q OR UPPER(placa) LIKE :q
                ORDER BY codigo, placa
            """),
            {"q": pat},
        )
    else:
        result = await db.execute(
            text("""
                SELECT id, codigo, descripcion, placa, cantidad, created_at, info_detallada
                FROM circuitos
                ORDER BY codigo, placa
            """)
        )

    rows = result.fetchall()
    circuitos = [
        {
            "id": r[0],
            "codigo": r[1],
            "descripcion": r[2] or "",
            "placa": r[3],
            "cantidad": r[4] or 1,
            "created_at": r[5].isoformat() if r[5] else None,
            "info_detallada": r[6] or "",
        }
        for r in rows
    ]
    return {"circuitos": circuitos}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_circuito(
    data: CircuitoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an IC reference. Auto-increment quantity on duplicate (codigo, placa)."""
    codigo = data.codigo.strip().upper()
    placa = data.placa.strip().upper()

    if not codigo or not placa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "detail": "Falta codigo o placa"},
        )

    # Check for existing
    result = await db.execute(
        text("SELECT id, cantidad FROM circuitos WHERE codigo = :c AND placa = :p"),
        {"c": codigo, "p": placa},
    )
    existing = result.fetchone()

    if existing:
        # Increment quantity, update descripcion/info_detallada if provided
        await db.execute(
            text("""
                UPDATE circuitos SET
                    cantidad = cantidad + :cant,
                    descripcion = COALESCE(NULLIF(:desc, ''), descripcion),
                    info_detallada = COALESCE(NULLIF(:info, ''), info_detallada)
                WHERE id = :eid
            """),
            {
                "cant": data.cantidad,
                "desc": data.descripcion.strip(),
                "info": data.info_detallada,
                "eid": existing[0],
            },
        )
    else:
        circuito = Circuito(
            codigo=codigo,
            placa=placa,
            descripcion=data.descripcion.strip(),
            cantidad=data.cantidad,
            info_detallada=data.info_detallada,
        )
        db.add(circuito)

    await db.flush()
    return {"ok": True}


@router.put("/{circuito_id}")
async def update_circuito(
    circuito_id: int,
    data: CircuitoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an IC reference."""
    result = await db.execute(select(Circuito).where(Circuito.id == circuito_id))
    circuito = result.scalar_one_or_none()
    if not circuito:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "detail": f"Circuito {circuito_id} not found",
            },
        )

    update_data = data.model_dump(exclude_unset=True)
    if "codigo" in update_data:
        update_data["codigo"] = update_data["codigo"].strip().upper()
    for field, value in update_data.items():
        setattr(circuito, field, value)
    await db.flush()
    return {"ok": True}


@router.delete("/{circuito_id}")
async def delete_circuito(
    circuito_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an IC reference."""
    result = await db.execute(select(Circuito).where(Circuito.id == circuito_id))
    circuito = result.scalar_one_or_none()
    if not circuito:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "detail": f"Circuito {circuito_id} not found",
            },
        )
    await db.delete(circuito)
    await db.flush()
    return {"ok": True}
