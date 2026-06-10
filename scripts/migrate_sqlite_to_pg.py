#!/usr/bin/env python3
"""
Migrate SQLite database to PostgreSQL for rendimiento-saas.

Usage:
    python scripts/migrate_sqlite_to_pg.py

Environment variables:
    SQLITE_PATH   — path to SQLite DB file (default: rendimiento.db)
    DATABASE_URL  — PostgreSQL connection string
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg


# ── Config ────────────────────────────────────────────────────────────────

SQLITE_PATH = os.environ.get("SQLITE_PATH", "rendimiento.db")
PG_DSN = os.environ.get("DATABASE_URL", "")

# Tables in order (respecting FK constraints)
TABLES = [
    "tenants",
    "users",
    "config",
    "ordenes",
    "reparaciones",
    "sesiones_reparacion",
    "puntajes",
    "tipos_equipo",
    "placas",
    "notas_placa",
    "mediciones_placa",
    "bloques_placa",
    "circuitos",
    "mediciones",
    "soluciones",
    "referencias",
    "diagramas",
    "ic_marcas",
    "ic_compatibilidad",
]

# Map old empresas to new tenants
EMPRESA_MAP = {}


# ── SQLite helpers ────────────────────────────────────────────────────────

def get_sqlite_conn(path: str) -> sqlite3.Connection:
    """Open SQLite connection with row factory."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def fetch_table(conn: sqlite3.Connection, table: str) -> list[dict]:
    """Fetch all rows from a SQLite table as dicts."""
    try:
        cursor = conn.execute(f"SELECT * FROM [{table}]")
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError as e:
        print(f"  ⚠  Table '{table}' not found in SQLite: {e}")
        return []


# ── Data transformation ──────────────────────────────────────────────────

def transform_tenants(rows: list[dict]) -> list[dict]:
    """Map empresas → tenants with seeded config."""
    result = []
    for r in rows:
        tid = r["id"]
        EMPRESA_MAP[tid] = tid  # Preserve ID (1:1 mapping)
        result.append({
            "id": tid,
            "name": r.get("nombre", f"Tenant {tid}"),
            "slug": (r.get("nombre", f"tenant{tid}").lower()
                     .replace(" ", "-")),
            "active": True,
        })
    # Ensure at least one tenant
    if not result:
        result.append({"id": 1, "name": "NSP Notebooks",
                       "slug": "nsp-notebooks", "active": True})
        EMPRESA_MAP[1] = 1
    return result


def transform_users(rows: list[dict]) -> list[dict]:
    """Ensure at least one admin user exists."""
    if rows:
        return [
            {
                "id": r["id"],
                "tenant_id": EMPRESA_MAP.get(r.get("tenant_id", 1), 1),
                "email": r["email"],
                "password_hash": r["password_hash"],
                "display_name": r.get("name", r.get("display_name", "")),
                "role": r.get("role", "admin"),
                "active": r.get("active", True),
            }
            for r in rows
        ]
    # No users yet — will be seeded by app startup
    return []


def transform_ordenes(rows: list[dict]) -> list[dict]:
    return [
        {
            "id": r["id"],
            "tenant_id": EMPRESA_MAP.get(1, 1),
            "numero": r["numero"],
            "fecha": r.get("fecha", ""),
            "placa": r.get("placa", ""),
            "falla": r.get("falla", ""),
            "diagnostico": r.get("diagnostico", ""),
            "proceso": r.get("proceso", ""),
            "solucion": r.get("solucion", ""),
            "estado": r.get("estado", "pendiente"),
            "resultado": r.get("resultado", "n/a"),
            "tipo": r.get("tipo", ""),
            "puntaje": r.get("puntaje", 0),
            "tipo_equipo": r.get("tipo_equipo", ""),
            "marca": r.get("marca", ""),
            "modelo": r.get("modelo", ""),
            "checklist": r.get("checklist", ""),
        }
        for r in rows
    ]


def transform_reparaciones(rows: list[dict], ordenes_map: dict) -> list[dict]:
    """Reparaciones with FK orden → ordenes.id remapping."""
    result = []
    for r in rows:
        orden_numero = r.get("orden")
        orden_id = ordenes_map.get(orden_numero)
        if orden_id is None:
            print(f"  ⚠  Reparacion id={r['id']}: orden #{orden_numero} "
                  f"not found, skipping")
            continue
        result.append({
            "id": r["id"],
            "tenant_id": EMPRESA_MAP.get(1, 1),
            "orden_id": orden_id,
            "placa": r.get("placa", ""),
            "falla": r.get("falla", ""),
            "diagnostico": r.get("diagnostico", ""),
            "proceso": r.get("proceso", ""),
            "solucion": r.get("solucion", ""),
            "estado": r.get("estado", "en_curso"),
            "resultado": r.get("resultado", "n/a"),
            "tipo": r.get("tipo", ""),
            "tipo_equipo": r.get("tipo_equipo", ""),
            "marca": r.get("marca", ""),
            "modelo": r.get("modelo", ""),
        })
    return result


def transform_sesiones(rows: list[dict], ordenes_map: dict) -> list[dict]:
    """Sesiones_reparacion with FK remapping."""
    result = []
    for r in rows:
        orden_numero = r.get("orden_id") or r.get("numero")
        orden_id = ordenes_map.get(orden_numero)
        if orden_id is None:
            print(f"  ⚠  Sesion id={r['id']}: orden #{orden_numero} "
                  f"not found, skipping")
            continue
        result.append({
            "id": r["id"],
            "orden_id": orden_id,
            "inicio": r.get("inicio", ""),
            "fin": r.get("fin"),
            "duracion_segundos": r.get("duracion_segundos", 0),
            "notas": r.get("notas", ""),
            "estado": r.get("estado", "finalizada"),
        })
    return result


def transform_puntajes(rows: list[dict]) -> list[dict]:
    return [
        {
            "id": r["id"],
            "tenant_id": EMPRESA_MAP.get(1, 1),
            "tipo": r["tipo"],
            "puntaje": r["puntaje"],
        }
        for r in rows
    ]


def noop(rows: list[dict]) -> list[dict]:
    """Pass-through for global tables (no tenant_id)."""
    return rows


# ── Table config ─────────────────────────────────────────────────────────

TABLE_CONFIG = {
    "tenants": {
        "sqlite_table": "empresas",
        "transform": transform_tenants,
        "pg_table": "tenants",
    },
    "users": {
        "sqlite_table": "users",
        "transform": transform_users,
        "pg_table": "users",
    },
    "config": {
        "sqlite_table": "config",
        "transform": noop,
        "pg_table": "config",
    },
    "ordenes": {
        "sqlite_table": "ordenes",
        "transform": transform_ordenes,
        "pg_table": "ordenes",
    },
    "reparaciones": {
        "sqlite_table": "reparaciones",
        "transform": transform_reparaciones,
        "pg_table": "reparaciones",
    },
    "sesiones_reparacion": {
        "sqlite_table": "sesiones_reparacion",
        "transform": transform_sesiones,
        "pg_table": "sesiones_reparacion",
    },
    "puntajes": {
        "sqlite_table": "puntajes",
        "transform": transform_puntajes,
        "pg_table": "puntajes",
    },
    "tipos_equipo": {
        "sqlite_table": "tipos_equipo",
        "transform": noop,
        "pg_table": "tipos_equipo",
    },
    "placas": {
        "sqlite_table": "placas",
        "transform": noop,
        "pg_table": "placas",
    },
    "notas_placa": {
        "sqlite_table": "notas_placa",
        "transform": noop,
        "pg_table": "notas_placa",
    },
    "mediciones_placa": {
        "sqlite_table": "mediciones_placa",
        "transform": noop,
        "pg_table": "mediciones_placa",
    },
    "bloques_placa": {
        "sqlite_table": "bloques_placa",
        "transform": noop,
        "pg_table": "bloques_placa",
    },
    "circuitos": {
        "sqlite_table": "circuitos",
        "transform": noop,
        "pg_table": "circuitos",
    },
    "mediciones": {
        "sqlite_table": "mediciones",
        "transform": noop,
        "pg_table": "mediciones",
    },
    "soluciones": {
        "sqlite_table": "soluciones",
        "transform": noop,
        "pg_table": "soluciones",
    },
    "referencias": {
        "sqlite_table": "referencias",
        "transform": noop,
        "pg_table": "referencias",
    },
    "diagramas": {
        "sqlite_table": "diagramas",
        "transform": noop,
        "pg_table": "diagramas",
    },
    "ic_marcas": {
        "sqlite_table": "ic_marcas",
        "transform": noop,
        "pg_table": "ic_marcas",
    },
    "ic_compatibilidad": {
        "sqlite_table": "ic_compatibilidad",
        "transform": noop,
        "pg_table": "ic_compatibilidad",
    },
}


# ── PostgreSQL helpers ────────────────────────────────────────────────────

async def get_pg_conn(dsn: str):
    """Create asyncpg connection."""
    return await asyncpg.connect(dsn)


async def truncate_tables(conn):
    """Truncate all tables in reverse order (FK-safe)."""
    for table in reversed(TABLES):
        try:
            await conn.execute(f"TRUNCATE TABLE \"{table}\" CASCADE")
        except Exception as e:
            print(f"  ⚠  Could not truncate {table}: {e}")


async def insert_rows(conn, table: str, rows: list[dict]):
    """Batch insert rows into PostgreSQL table."""
    if not rows:
        print(f"  → {table}: 0 rows (empty)")
        return 0

    # Get column names from first row
    columns = list(rows[0].keys())
    col_list = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
    stmt = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})'

    # Convert rows to tuple list
    values = [tuple(r[c] for c in columns) for r in rows]

    try:
        await conn.executemany(stmt, values)
        print(f"  ✓ {table}: {len(rows)} rows")
        return len(rows)
    except Exception as e:
        print(f"  ✗ {table}: ERROR — {e}")
        # Try row by row for better error reporting
        count = 0
        for row in rows:
            try:
                await conn.execute(
                    stmt, *[row[c] for c in columns]
                )
                count += 1
            except Exception as e2:
                print(f"    ✗ {table} row {row.get('id', '?')}: {e2}")
        print(f"  → {table}: {count}/{len(rows)} rows inserted")
        return count


# ── Main ──────────────────────────────────────────────────────────────────

async def main():
    if not PG_DSN:
        print("❌ DATABASE_URL environment variable not set")
        sys.exit(1)

    if not os.path.exists(SQLITE_PATH):
        print(f"❌ SQLite DB not found: {SQLITE_PATH}")
        sys.exit(1)

    # ── Step 1: Read SQLite ──────────────────────────────────────
    print(f"📂 Reading SQLite: {SQLITE_PATH}")
    sqlite_conn = get_sqlite_conn(SQLITE_PATH)

    # ── Step 2: Transform & prepare data ─────────────────────────
    print("🔄 Transforming data...")

    # Read empresas first (needed for ID mapping)
    empresas = fetch_table(sqlite_conn, "empresas")
    transform_tenants(empresas)

    # Read ordenes for FK mapping
    ordenes_raw = fetch_table(sqlite_conn, "ordenes")
    ordenes_map = {r["numero"]: r["id"] for r in ordenes_raw}

    all_data = {}
    row_counts = {}

    for table_key, cfg in TABLE_CONFIG.items():
        raw = fetch_table(sqlite_conn, cfg["sqlite_table"])
        transform_fn = cfg["transform"]

        if table_key == "reparaciones":
            transformed = transform_reparaciones(raw, ordenes_map)
        elif table_key == "sesiones_reparacion":
            transformed = transform_sesiones(raw, ordenes_map)
        else:
            transformed = transform_fn(raw)

        all_data[table_key] = transformed
        row_counts[table_key] = {"sqlite": len(raw), "pg": 0}

    sqlite_conn.close()
    print(f"   → {sum(rc['sqlite'] for rc in row_counts.values())} "
          f"total rows from SQLite")

    # ── Step 3: Connect to PostgreSQL ───────────────────────────
    print(f"🐘 Connecting to PostgreSQL...")
    pg_conn = await get_pg_conn(PG_DSN)

    try:
        # Truncate existing data
        print("🧹 Truncating existing data...")
        await truncate_tables(pg_conn)

        # Insert data in dependency order
        print("📥 Inserting data...")
        total = 0
        for table_key in TABLES:
            cfg = TABLE_CONFIG.get(table_key)
            if not cfg:
                continue
            rows = all_data.get(table_key, [])
            inserted = await insert_rows(pg_conn, cfg["pg_table"], rows)
            # Hack for sesiones_reparacion ID sequence (if PK is serial)
            try:
                await pg_conn.execute(
                    f"SELECT setval(pg_get_serial_sequence("
                    f"'{cfg[\"pg_table\"]}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM "
                    f"\"{cfg['pg_table']}\"), 0) + 1)"
                )
            except Exception:
                pass
            row_counts[table_key]["pg"] = inserted
            total += inserted

        # ── Step 4: Validate ────────────────────────────────────
        print("\n📊 Validation:")
        all_ok = True
        for table_key, rc in row_counts.items():
            s = rc["sqlite"]
            p = rc["pg"]
            status = "✓" if s == p else "⚠"
            if s != p:
                all_ok = False
            print(f"  {status} {table_key}: SQLite={s} PG={p}")

        if all_ok:
            print(f"\n✅ Migration complete! {total} rows migrated.")
        else:
            print(f"\n⚠ Migration finished with mismatches. "
                  f"Review warnings above.")

    finally:
        await pg_conn.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
