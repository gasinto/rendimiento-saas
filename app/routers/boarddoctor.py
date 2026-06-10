"""
BoardDoctor router — Diagramas, ic-marcas, ic-compatibles, datasheet search + CSV import.

Replicates server.py APIHandler: buscar_diagramas, buscar_ic_marca,
buscar_ic_compatibles, buscar_datasheet_externo, importar_boarddoctor_api.
"""

import csv
import os
import urllib.parse
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.user import User

router = APIRouter(prefix="/api/boarddoctor", tags=["boarddoctor"])


# ── Schemas ──────────────────────────────────────────────────────────────


class DiagramaOut(BaseModel):
    id: int
    marca: str = ""
    modelo: str = ""
    tipo: str = ""
    gdrive_id: str = ""
    nombre_archivo: str = ""
    tamaño_mb: float = 0
    ultima_sync: str = ""
    url_descarga: str = ""


class IcMarcaOut(BaseModel):
    marking: str = ""
    modelo: str = ""
    fabricante: str = ""
    funcion: str = ""


class IcCompatibilidadOut(BaseModel):
    fabricante: str = ""
    modelo_original: str = ""
    compatibles: str = ""


class DatasheetResult(BaseModel):
    titulo: str
    url: str
    fuente: str = ""


class ImportResponse(BaseModel):
    ok: bool = True
    diagramas: int = 0
    ic_marcas: int = 0
    ic_compatibilidad: int = 0


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/diagramas")
async def search_diagramas(
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search board diagrams by modelo, marca, or filename."""
    if not q or len(q.strip()) < 2:
        return {"diagramas": []}

    pat = f"%{q.strip()}%"
    result = await db.execute(
        text("""
            SELECT id, marca, modelo, tipo, gdrive_id, nombre_archivo, tamaño_mb, ultima_sync
            FROM diagramas
            WHERE modelo LIKE :q OR marca LIKE :q OR nombre_archivo LIKE :q
            ORDER BY modelo ASC LIMIT 50
        """),
        {"q": pat},
    )
    rows = result.fetchall()
    diagramas = []
    for r in rows:
        gdrive_id = r[4] or ""
        diagramas.append(
            {
                "id": r[0],
                "marca": r[1] or "",
                "modelo": r[2] or "",
                "tipo": r[3] or "",
                "gdrive_id": gdrive_id,
                "nombre_archivo": r[5] or "",
                "tamaño_mb": float(r[6]) if r[6] else 0,
                "ultima_sync": r[7] or "",
                "url_descarga": f"https://drive.google.com/uc?export=download&id={gdrive_id}"
                if gdrive_id
                else "",
            }
        )
    return {"diagramas": diagramas}


@router.get("/ic-marcas")
async def search_ic_marcas(
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search IC markings by marking code or model."""
    if not q or len(q.strip()) < 1:
        return {"resultados": []}

    pat = f"%{q.strip()}%"
    result = await db.execute(
        text("""
            SELECT marking, modelo, fabricante, funcion
            FROM ic_marcas
            WHERE marking LIKE :q OR modelo LIKE :q
            ORDER BY marking ASC LIMIT 30
        """),
        {"q": pat},
    )
    resultados = [
        {
            "marking": r[0],
            "modelo": r[1],
            "fabricante": r[2] or "",
            "funcion": r[3] or "",
        }
        for r in result.fetchall()
    ]
    return {"resultados": resultados}


@router.get("/ic-compatibles")
async def search_ic_compatibles(
    modelo: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search IC compatibility replacements by model."""
    if not modelo or len(modelo.strip()) < 2:
        return {"resultados": []}

    pat = f"%{modelo.strip()}%"
    result = await db.execute(
        text("""
            SELECT fabricante, modelo as modelo_original, compatibles
            FROM ic_compatibilidad
            WHERE modelo LIKE :q OR fabricante LIKE :q
            ORDER BY modelo ASC LIMIT 20
        """),
        {"q": pat},
    )
    resultados = [
        {
            "fabricante": r[0],
            "modelo_original": r[1],
            "compatibles": r[2] or "",
        }
        for r in result.fetchall()
    ]
    return {"resultados": resultados}


@router.get("/datasheet")
async def search_datasheet(
    componente: str | None = None,
    current_user: User = Depends(get_current_user),
):
    """Search external datasheets from alldatasheet.com (scrape)."""
    if not componente or len(componente.strip()) < 2:
        return {"resultados": []}

    resultados: list[dict[str, str]] = []

    try:
        import requests
        from bs4 import BeautifulSoup

        # Try alldatasheet.com
        try:
            url_ad = (
                f"https://www.alldatasheet.com/view.jsp?SearchWord={urllib.parse.quote(componente.strip())}"
            )
            resp = requests.get(
                url_ad, timeout=10, headers={"User-Agent": "Mozilla/5.0"}
            )
            if resp.ok:
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.select("a[href*='datasheet']"):
                    href = a.get("href", "")
                    txt = a.get_text(strip=True)
                    if href and txt and componente.lower() in txt.lower():
                        if not href.startswith("http"):
                            href = "https://www.alldatasheet.com" + href
                        resultados.append(
                            {
                                "titulo": txt[:120],
                                "url": href,
                                "fuente": "alldatasheet.com",
                            }
                        )
                        if len(resultados) >= 5:
                            break
        except Exception:
            pass

        # Fallback to datasheet4u.com
        if not resultados:
            try:
                url_d4u = (
                    f"https://www.datasheet4u.com/search?q={urllib.parse.quote(componente.strip())}"
                )
                resp = requests.get(
                    url_d4u, timeout=10, headers={"User-Agent": "Mozilla/5.0"}
                )
                if resp.ok:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a in soup.select("a[href*='datasheet']"):
                        href = a.get("href", "")
                        txt = a.get_text(strip=True)
                        if href and txt and componente.lower() in txt.lower():
                            if not href.startswith("http"):
                                href = "https://www.datasheet4u.com" + href
                            resultados.append(
                                {
                                    "titulo": txt[:120],
                                    "url": href,
                                    "fuente": "datasheet4u.com",
                                }
                            )
                            if len(resultados) >= 5:
                                break
            except Exception:
                pass
    except ImportError:
        pass

    if not resultados:
        resultados.append(
            {
                "titulo": f"No se encontraron datasheets para '{componente}'",
                "url": "",
                "fuente": "",
            }
        )

    return {"resultados": resultados}


@router.post("/import", response_model=ImportResponse)
async def import_boarddoctor(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """Re-import BoardDoctor data from CSV files in ../boarddoctor_backup/."""
    import csv
    import os

    backup_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..",
        "boarddoctor_backup",
    )

    if not os.path.isdir(backup_dir):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "not_found",
                "detail": f"BoardDoctor backup dir not found: {backup_dir}",
            },
        )

    stats = {"diagramas": 0, "ic_marcas": 0, "ic_compatibilidad": 0}

    # diagramas from cloud_catalog.csv
    csv_path = os.path.join(backup_dir, "cloud_catalog.csv")
    if os.path.isfile(csv_path):
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                marca = (row.get("brand") or "").strip()
                modelo = (row.get("model") or "").strip()
                res_type = (row.get("res_type") or "").strip().lower()
                gdrive_id = (row.get("gdrive_id") or "").strip()
                nombre = (row.get("cloud_filename") or "").strip()
                last_sync = (row.get("last_sync") or "").strip()
                size_str = (
                    (row.get("file_size") or "0")
                    .strip()
                    .replace("MB", "")
                    .replace(" ", "")
                    .replace(",", ".")
                )
                try:
                    size_mb = round(float(size_str), 2)
                except (ValueError, TypeError):
                    size_mb = 0
                tipo = (
                    "schematic"
                    if "schematic" in res_type or "sch" in res_type
                    else "boardview"
                )

                await db.execute(
                    text("""
                        INSERT OR IGNORE INTO diagramas
                            (marca, modelo, tipo, gdrive_id, nombre_archivo, tamaño_mb, ultima_sync)
                        VALUES (:marca, :modelo, :tipo, :gid, :nombre, :size, :sync)
                    """),
                    {
                        "marca": marca,
                        "modelo": modelo,
                        "tipo": tipo,
                        "gid": gdrive_id,
                        "nombre": nombre,
                        "size": size_mb,
                        "sync": last_sync,
                    },
                )
                count += 1
            stats["diagramas"] = count

    # ic_marcas from ic_catalog.csv
    csv_path = os.path.join(backup_dir, "ic_catalog.csv")
    if os.path.isfile(csv_path):
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                marking = (row.get("marking") or "").strip()
                modelo = (row.get("model") or "").strip()
                fabricante = (row.get("brand") or "").strip()
                funcion = (row.get("function") or "").strip()
                compat = (row.get("compatibility") or "").strip()

                await db.execute(
                    text("""
                        INSERT OR IGNORE INTO ic_marcas
                            (marking, modelo, fabricante, funcion, compatibilidad)
                        VALUES (:marking, :modelo, :fab, :func, :compat)
                    """),
                    {
                        "marking": marking,
                        "modelo": modelo,
                        "fab": fabricante,
                        "func": funcion,
                        "compat": compat,
                    },
                )
                count += 1
            stats["ic_marcas"] = count

    # ic_compatibilidad from ic_compatibility.csv
    csv_path = os.path.join(backup_dir, "ic_compatibility.csv")
    if os.path.isfile(csv_path):
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                fabricante = (row.get("brand") or "").strip()
                modelo = (row.get("model") or "").strip()
                compatibles = (row.get("compatibles") or "").strip()

                await db.execute(
                    text("""
                        INSERT OR IGNORE INTO ic_compatibilidad
                            (fabricante, modelo, compatibles)
                        VALUES (:fab, :modelo, :compat)
                    """),
                    {
                        "fab": fabricante,
                        "modelo": modelo,
                        "compat": compatibles,
                    },
                )
                count += 1
            stats["ic_compatibilidad"] = count

    await db.flush()

    # Count inserted rows
    result = await db.execute(text("SELECT COUNT(*) FROM diagramas"))
    diagrams_count = result.scalar() or 0
    result = await db.execute(text("SELECT COUNT(*) FROM ic_marcas"))
    ic_count = result.scalar() or 0
    result = await db.execute(text("SELECT COUNT(*) FROM ic_compatibilidad"))
    comp_count = result.scalar() or 0

    return ImportResponse(
        ok=True,
        diagramas=diagrams_count,
        ic_marcas=ic_count,
        ic_compatibilidad=comp_count,
    )
