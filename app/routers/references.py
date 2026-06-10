"""
References router — Referencias CRUD with categories + HTML content.

Replicates server.py APIHandler: listar_referencias, obtener_referencia,
agregar_referencia, eliminar_referencia.
Global table — no tenant isolation.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.reference import Referencia
from app.models.user import User

router = APIRouter(prefix="/api/references", tags=["references"])


# ── Schemas ──────────────────────────────────────────────────────────────


class ReferenciaOut(BaseModel):
    id: int
    categoria: str = "Electronica General"
    titulo: str
    contenido_html: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReferenciaCreate(BaseModel):
    categoria: str = "Electronica General"
    titulo: str
    contenido_html: str = ""


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/")
async def list_referencias(
    categoria: str | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List references with optional category filter and full-text search."""
    if q:
        pat = f"%{q}%"
        if categoria:
            result = await db.execute(
                text("""
                    SELECT id, categoria, titulo, contenido_html, created_at
                    FROM referencias
                    WHERE categoria = :cat AND (titulo LIKE :q OR contenido_html LIKE :q)
                    ORDER BY titulo
                """),
                {"cat": categoria, "q": pat},
            )
        else:
            result = await db.execute(
                text("""
                    SELECT id, categoria, titulo, contenido_html, created_at
                    FROM referencias
                    WHERE titulo LIKE :q OR contenido_html LIKE :q
                    ORDER BY categoria, titulo
                """),
                {"q": pat},
            )
    elif categoria:
        result = await db.execute(
            text("""
                SELECT id, categoria, titulo, contenido_html, created_at
                FROM referencias
                WHERE categoria = :cat
                ORDER BY titulo
            """),
            {"cat": categoria},
        )
    else:
        result = await db.execute(
            text("""
                SELECT id, categoria, titulo, contenido_html, created_at
                FROM referencias
                ORDER BY categoria, titulo
            """)
        )

    rows = result.fetchall()
    referencias = [
        {
            "id": r[0],
            "categoria": r[1],
            "titulo": r[2],
            "contenido_html": r[3] or "",
            "created_at": r[4].isoformat() if r[4] else None,
        }
        for r in rows
    ]

    # Also return available categories
    cat_result = await db.execute(
        text("SELECT DISTINCT categoria FROM referencias ORDER BY categoria")
    )
    categorias = [r[0] for r in cat_result.fetchall()]

    return {"referencias": referencias, "categorias": categorias}


@router.get("/{ref_id}")
async def get_referencia(
    ref_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single reference by ID."""
    result = await db.execute(
        select(Referencia).where(Referencia.id == ref_id)
    )
    ref = result.scalar_one_or_none()
    if not ref:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "detail": f"Referencia {ref_id} not found",
            },
        )
    return {"referencia": ref}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_referencia(
    data: ReferenciaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new reference."""
    categoria = data.categoria.strip() or "Electronica General"
    titulo = data.titulo.strip()
    if not titulo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "detail": "Falta titulo"},
        )

    ref = Referencia(
        categoria=categoria,
        titulo=titulo,
        contenido_html=data.contenido_html.strip(),
    )
    db.add(ref)
    await db.flush()
    await db.refresh(ref)
    return {"ok": True, "id": ref.id}


@router.delete("/{ref_id}")
async def delete_referencia(
    ref_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a reference."""
    result = await db.execute(
        select(Referencia).where(Referencia.id == ref_id)
    )
    ref = result.scalar_one_or_none()
    if not ref:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "detail": f"Referencia {ref_id} not found",
            },
        )
    await db.delete(ref)
    await db.flush()
    return {"ok": True}
