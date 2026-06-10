"""
Search router — Unified search across soluciones, ordenes, mediciones,
notas, referencias, circuitos.

Replicates server.py APIHandler: buscar.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_current_tenant
from app.models.user import User

router = APIRouter(prefix="/api/search", tags=["search"])


# ── Schemas ──────────────────────────────────────────────────────────────


class SearchResult(BaseModel):
    tipo: str
    id: int | None = None
    titulo: str = ""
    subtitulo: str = ""
    detalle: str = ""
    tab: str | None = None


class SearchResponse(BaseModel):
    resultados: list[SearchResult]


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/")
async def unified_search(
    q: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """Unified search across all data types."""
    if not q or len(q.strip()) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "detail": "Falta término de búsqueda"},
        )

    pat = f"%{q.strip()}%"
    results = []

    # Soluciones (global search)
    sol_result = await db.execute(
        text("""
            SELECT id, placa, falla, solucion, created_at
            FROM soluciones
            WHERE placa LIKE :q OR falla LIKE :q OR solucion LIKE :q
            ORDER BY created_at DESC LIMIT 10
        """),
        {"q": pat},
    )
    for r in sol_result.fetchall():
        results.append(
            SearchResult(
                tipo="solución",
                id=r[0],
                titulo=r[1],
                subtitulo=(r[2] or "")[:100],
                detalle=(r[3] or "")[:100],
            )
        )

    # Órdenes (tenant-scoped)
    ord_result = await db.execute(
        text("""
            SELECT id, numero, placa, falla, diagnostico, solucion, proceso
            FROM ordenes
            WHERE tenant_id = :tid
              AND (placa LIKE :q OR falla LIKE :q OR diagnostico LIKE :q
                   OR solucion LIKE :q OR proceso LIKE :q)
            ORDER BY id DESC LIMIT 10
        """),
        {"tid": tenant_id, "q": pat},
    )
    for r in ord_result.fetchall():
        results.append(
            SearchResult(
                tipo="orden",
                id=r[0],
                titulo=f"#{r[1]} — {r[2]}",
                subtitulo=(r[3] or "")[:100],
                detalle=((r[4] or r[5] or ""))[:100],
            )
        )

    # Mediciones de placa (global)
    med_result = await db.execute(
        text("""
            SELECT modelo_placa, punto_medicion, nombre, valor_esperado, categoria
            FROM mediciones_placa
            WHERE modelo_placa LIKE :q OR punto_medicion LIKE :q OR nombre LIKE :q
            ORDER BY modelo_placa, punto_medicion LIMIT 15
        """),
        {"q": pat},
    )
    seen_med = set()
    for r in med_result.fetchall():
        key = (r[0], r[1])
        if key in seen_med:
            continue
        seen_med.add(key)
        detail = f"Esperado: {r[3] or ''}" + (f" | {r[4]}" if r[4] else "")
        results.append(
            SearchResult(
                tipo="medición",
                tab="puntos-placa",
                titulo=f"{r[0]} — {r[1]}",
                subtitulo=r[2] or "",
                detalle=detail,
            )
        )

    # Notas de placa (global)
    nota_result = await db.execute(
        text("""
            SELECT modelo_placa, contenido
            FROM notas_placa
            WHERE modelo_placa LIKE :q OR contenido LIKE :q
            ORDER BY created_at DESC LIMIT 10
        """),
        {"q": pat},
    )
    seen_nota = set()
    for r in nota_result.fetchall():
        key = (r[0], (r[1] or "")[:80])
        if key in seen_nota:
            continue
        seen_nota.add(key)
        results.append(
            SearchResult(
                tipo="nota",
                tab="puntos-placa",
                titulo=r[0],
                subtitulo=((r[1] or "")[:120] + ("…" if len(r[1] or "") > 120 else "")),
                detalle="",
            )
        )

    # Referencias (global)
    ref_result = await db.execute(
        text("""
            SELECT id, categoria, titulo, substr(contenido_html, 1, 200) as preview
            FROM referencias
            WHERE titulo LIKE :q OR contenido_html LIKE :q
            ORDER BY titulo LIMIT 10
        """),
        {"q": pat},
    )
    for r in ref_result.fetchall():
        results.append(
            SearchResult(
                tipo="referencia",
                tab="referencia",
                id=r[0],
                titulo=r[2],
                subtitulo=r[1],
                detalle=(r[3] or "")[:100],
            )
        )

    # Circuitos (global)
    ic_result = await db.execute(
        text("""
            SELECT id, codigo, descripcion, placa
            FROM circuitos
            WHERE UPPER(codigo) LIKE :q OR UPPER(descripcion) LIKE :q OR UPPER(placa) LIKE :q
            ORDER BY codigo, placa LIMIT 10
        """),
        {"q": pat.upper()},
    )
    for r in ic_result.fetchall():
        results.append(
            SearchResult(
                tipo="circuito",
                id=r[0],
                titulo=r[1],
                subtitulo=r[2] or "",
                detalle=r[3],
            )
        )

    return SearchResponse(resultados=results)
