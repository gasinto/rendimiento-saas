"""
Global measurements router — Mediciones (IC pin measurements) CRUD with search.

Replicates server.py APIHandler: listar_mediciones, agregar_medicion,
eliminar_medicion.
Global table — no tenant isolation.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.measurement import Medicion
from app.models.user import User

router = APIRouter(prefix="/api/measurements", tags=["measurements"])


# ── Schemas ──────────────────────────────────────────────────────────────


class MedicionOut(BaseModel):
    id: int
    codigo: str
    placa: str
    pin: str
    nombre: str = ""
    valor_esperado: str = ""
    notas: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class MedicionCreate(BaseModel):
    codigo: str
    placa: str
    pin: str
    nombre: str = ""
    valor_esperado: str = ""
    notas: str = ""


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/")
async def list_mediciones(
    codigo: str | None = None,
    placa: str | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List global pin measurements with optional search or (codigo+placa) filter."""
    if codigo and placa:
        result = await db.execute(
            text("""
                SELECT id, codigo, placa, pin, nombre, valor_esperado, notas, created_at
                FROM mediciones
                WHERE codigo = :c AND placa = :p
                ORDER BY pin
            """),
            {"c": codigo.strip().upper(), "p": placa.strip().upper()},
        )
    elif q:
        pat = f"%{q.upper()}%"
        result = await db.execute(
            text("""
                SELECT id, codigo, placa, pin, nombre, valor_esperado, notas, created_at
                FROM mediciones
                WHERE UPPER(codigo) LIKE :q OR UPPER(nombre) LIKE :q OR UPPER(placa) LIKE :q
                ORDER BY codigo, placa, pin
            """),
            {"q": pat},
        )
    else:
        result = await db.execute(
            text("""
                SELECT id, codigo, placa, pin, nombre, valor_esperado, notas, created_at
                FROM mediciones
                ORDER BY codigo, placa, pin
            """)
        )

    rows = result.fetchall()
    mediciones = [
        {
            "id": r[0],
            "codigo": r[1],
            "placa": r[2],
            "pin": r[3],
            "nombre": r[4] or "",
            "valor_esperado": r[5] or "",
            "notas": r[6] or "",
            "created_at": r[7].isoformat() if r[7] else None,
        }
        for r in rows
    ]
    return {"mediciones": mediciones}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_medicion(
    data: MedicionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a global pin measurement. Upserts on duplicate (codigo, placa, pin)."""
    codigo = data.codigo.strip().upper()
    placa = data.placa.strip().upper()
    pin = data.pin.strip()

    if not codigo or not placa or not pin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "detail": "Falta codigo, placa o pin",
            },
        )

    nombre = data.nombre.strip()
    valor_esperado = data.valor_esperado.strip()
    notas = data.notas.strip()

    # Upsert on unique (codigo, placa, pin)
    existing = await db.execute(
        text("SELECT id FROM mediciones WHERE codigo = :c AND placa = :p AND pin = :pin"),
        {"c": codigo, "p": placa, "pin": pin},
    )
    if existing.fetchone():
        await db.execute(
            text("""
                UPDATE mediciones SET nombre = :nombre, valor_esperado = :ve, notas = :notas
                WHERE codigo = :c AND placa = :p AND pin = :pin
            """),
            {
                "nombre": nombre,
                "ve": valor_esperado,
                "notas": notas,
                "c": codigo,
                "p": placa,
                "pin": pin,
            },
        )
    else:
        medicion = Medicion(
            codigo=codigo,
            placa=placa,
            pin=pin,
            nombre=nombre,
            valor_esperado=valor_esperado,
            notas=notas,
        )
        db.add(medicion)

    await db.flush()
    return {"ok": True}


@router.delete("/{medicion_id}")
async def delete_medicion(
    medicion_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a global pin measurement."""
    result = await db.execute(
        select(Medicion).where(Medicion.id == medicion_id)
    )
    medicion = result.scalar_one_or_none()
    if not medicion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "detail": f"Medicion {medicion_id} not found",
            },
        )
    await db.delete(medicion)
    await db.flush()
    return {"ok": True}
