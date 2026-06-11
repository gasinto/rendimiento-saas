"""
Migrate data from the local SQLite database (rendimiento.db) to Railway PostgreSQL.

Reads the SQLite data, transforms it to match the SaaS schema (with tenants),
and inserts into PostgreSQL. Designed to be run ONCE from a local machine.

Usage:
    DATABASE_URL="postgresql://..." python scripts/migrate_sqlite_to_pg.py
"""

import os
import sqlite3
import sys
from datetime import datetime

from sqlalchemy import create_engine, text

# ── Config ─────────────────────────────────────────────────────────────────────
SQLITE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rendimiento.db")
PG_URL = os.environ.get("DATABASE_URL")
if not PG_URL:
    sys.exit("ERROR: Set DATABASE_URL env var to the Railway PostgreSQL URL")

# Fix URL for async → sync (migration script uses sync SQLAlchemy)
if "+asyncpg" in PG_URL:
    PG_URL = PG_URL.replace("+asyncpg", "")
elif PG_URL.startswith("postgresql://") or PG_URL.startswith("postgres://"):
    pass

# ── Connect ────────────────────────────────────────────────────────────────────
print("🤝 Connecting to SQLite...")
sqlite = sqlite3.connect(SQLITE_PATH)
sqlite.row_factory = sqlite3.Row
sc = sqlite.cursor()

print("🤝 Connecting to PostgreSQL...")
pg = create_engine(PG_URL, pool_pre_ping=True)
conn = pg.connect()
conn.execution_options(isolation_level="AUTOCOMMIT")

# Helper: shorthand for conn.execute(text(...), params)
def run(sql, params: dict | None = None):
    if isinstance(sql, str):
        return conn.execute(text(sql), params or {})
    return conn.execute(sql, params or {})

# ── Helper: run a query and return all rows as dicts ──────────────────────────
def sq(query: str) -> list[dict]:
    sc.execute(query)
    return [dict(r) for r in sc.fetchall()]


# ── Helper: get value or default ──────────────────────────────────────────────
def v(row: dict, key: str, default=None):
    return row.get(key, default)


# ═══════════════════════════════════════════════════════════════════════════════
#  1. EMPRESAS → TENANTS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating empresas → tenants ──")
empresas = sq("SELECT * FROM empresas")
print(f"  Found {len(empresas)} empresas")

# old_id → new_id mapping
empresa_to_tenant = {}
for emp in empresas:
    name = emp["nombre"]
    slug = name.lower().replace(" ", "-")
    slug = "".join(c for c in slug if c.isalnum() or c == "-")  # sanitize

    # Check if tenant already exists
    existing = run(
        text("SELECT id FROM tenants WHERE slug = :slug"), {"slug": slug}
    ).fetchone()

    if existing:
        tenant_id = existing[0]
        print(f"  ⚠️  Tenant '{name}' (slug={slug}) already exists with id={tenant_id}, reusing")
    else:
        result = run(
            text("""
                INSERT INTO tenants (name, slug, config, active, created_at)
                VALUES (:name, :slug, '{}', true, :created_at)
                RETURNING id
            """),
            {
                "name": name,
                "slug": slug,
                "created_at": v(emp, "created_at", datetime.now().isoformat()),
            },
        )
        tenant_id = result.scalar()
        print(f"  ✅ Created tenant '{name}' with id={tenant_id}")

    empresa_to_tenant[emp["id"]] = tenant_id

if not empresa_to_tenant:
    print("  ❌ No empresas found, nothing to migrate")
    sys.exit(1)

# ── Ensure the "admin" tenant exists (seed creates it on startup) ────────────
admin_tenant = run(
    text("SELECT id FROM tenants WHERE slug = 'admin'")
).fetchone()
if not admin_tenant:
    print("  ⚠️  Admin tenant not found, will be created on next app restart (seed)")


# ═══════════════════════════════════════════════════════════════════════════════
#  2. TIPOS_EQUIPO (global)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating tipos_equipo ──")
tipos = sq("SELECT * FROM tipos_equipo")
print(f"  Found {len(tipos)} tipos")
tipo_id_map = {}
for t in tipos:
    existing = run(
        text("SELECT id FROM tipos_equipo WHERE nombre = :nombre"),
        {"nombre": t["nombre"]},
    ).fetchone()
    if existing:
        tipo_id_map[t["id"]] = existing[0]
        print(f"  ⚠️  Tipo '{t['nombre']}' already exists, id={existing[0]}")
    else:
        result = run(
            text("""
                INSERT INTO tipos_equipo (nombre, created_at)
                VALUES (:nombre, :created_at)
                RETURNING id
            """),
            {
                "nombre": t["nombre"],
                "created_at": v(t, "created_at", datetime.now().isoformat()),
            },
        )
        new_id = result.scalar()
        tipo_id_map[t["id"]] = new_id
        print(f"  ✅ Inserted tipo '{t['nombre']}' → id={new_id}")


# ═══════════════════════════════════════════════════════════════════════════════
#  3. PLACAS (global)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating placas ──")
placas = sq("SELECT * FROM placas")
print(f"  Found {len(placas)} placas")
placa_id_map = {}
for p in placas:
    existing = run(
        text("SELECT id FROM placas WHERE modelo_placa = :modelo"),
        {"modelo": p["modelo_placa"]},
    ).fetchone()
    if existing:
        placa_id_map[p["id"]] = existing[0]
    else:
        tipo_id = tipo_id_map.get(v(p, "tipo_equipo_id")) if v(p, "tipo_equipo_id") else None
        result = run(
            text("""
                INSERT INTO placas (modelo_placa, tipo_equipo_id, created_at)
                VALUES (:modelo, :tipo_id, :created_at)
                RETURNING id
            """),
            {
                "modelo": p["modelo_placa"],
                "tipo_id": tipo_id,
                "created_at": v(p, "created_at", datetime.now().isoformat()),
            },
        )
        placa_id_map[p["id"]] = result.scalar()
print(f"  ✅ Inserted/mapped {len(placa_id_map)} placas")


# ═══════════════════════════════════════════════════════════════════════════════
#  4. CIRCUITOS (global)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating circuitos ──")
circuitos = sq("SELECT * FROM circuitos")
print(f"  Found {len(circuitos)} circuitos")
inserted = 0
for c in circuitos:
    existing = run(
        text("SELECT id FROM circuitos WHERE codigo = :codigo AND placa = :placa"),
        {"codigo": c["codigo"], "placa": c["placa"]},
    ).fetchone()
    if not existing:
        run(
            text("""
                INSERT INTO circuitos (codigo, descripcion, placa, cantidad, info_detallada, created_at)
                VALUES (:codigo, :descripcion, :placa, :cantidad, :info, :created_at)
            """),
            {
                "codigo": c["codigo"],
                "descripcion": v(c, "descripcion", ""),
                "placa": c["placa"],
                "cantidad": v(c, "cantidad", 1),
                "info": v(c, "info_detallada", ""),
                "created_at": v(c, "created_at", datetime.now().isoformat()),
            },
        )
        inserted += 1
print(f"  ✅ Inserted {inserted} circuitos, skipped {len(circuitos) - inserted}")


# ═══════════════════════════════════════════════════════════════════════════════
#  5. MEDICIONES (global)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating mediciones ──")
mediciones = sq("SELECT * FROM mediciones")
print(f"  Found {len(mediciones)} mediciones")
inserted = 0
for m in mediciones:
    existing = run(
        text("SELECT id FROM mediciones WHERE codigo = :codigo AND placa = :placa AND pin = :pin"),
        {"codigo": m["codigo"], "placa": m["placa"], "pin": m["pin"]},
    ).fetchone()
    if not existing:
        run(
            text("""
                INSERT INTO mediciones (codigo, placa, pin, nombre, valor_esperado, notas, created_at)
                VALUES (:codigo, :placa, :pin, :nombre, :valor, :notas, :created_at)
            """),
            {
                "codigo": m["codigo"],
                "placa": m["placa"],
                "pin": m["pin"],
                "nombre": v(m, "nombre", ""),
                "valor": v(m, "valor_esperado", ""),
                "notas": v(m, "notas", ""),
                "created_at": v(m, "created_at", datetime.now().isoformat()),
            },
        )
        inserted += 1
print(f"  ✅ Inserted {inserted} mediciones, skipped {len(mediciones) - inserted}")


# ═══════════════════════════════════════════════════════════════════════════════
#  6. SOLUCIONES (global — tenant_id is optional in PG)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating soluciones ──")
soluciones = sq("SELECT * FROM soluciones")
print(f"  Found {len(soluciones)} soluciones")
inserted = 0
for s in soluciones:
    existing = run(
        text("SELECT id FROM soluciones WHERE placa = :placa AND falla = :falla"),
        {"placa": s["placa"], "falla": v(s, "falla", "")},
    ).fetchone()
    if not existing:
        run(
            text("""
                INSERT INTO soluciones (placa, falla, solucion, ics, created_at)
                VALUES (:placa, :falla, :solucion, :ics, :created_at)
            """),
            {
                "placa": s["placa"],
                "falla": v(s, "falla", ""),
                "solucion": v(s, "solucion", ""),
                "ics": v(s, "ics", "[]"),
                "created_at": v(s, "created_at", datetime.now().isoformat()),
            },
        )
        inserted += 1
print(f"  ✅ Inserted {inserted} soluciones, skipped {len(soluciones) - inserted}")


# ═══════════════════════════════════════════════════════════════════════════════
#  7. REFERENCIAS (global)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating referencias ──")
referencias = sq("SELECT * FROM referencias")
print(f"  Found {len(referencias)} referencias")
inserted = 0
for r in referencias:
    existing = run(
        text("SELECT id FROM referencias WHERE titulo = :titulo"),
        {"titulo": r["titulo"]},
    ).fetchone()
    if not existing:
        run(
            text("""
                INSERT INTO referencias (categoria, titulo, contenido_html, created_at)
                VALUES (:categoria, :titulo, :contenido, :created_at)
            """),
            {
                "categoria": v(r, "categoria", "Electronica General"),
                "titulo": r["titulo"],
                "contenido": v(r, "contenido_html", ""),
                "created_at": v(r, "created_at", datetime.now().isoformat()),
            },
        )
        inserted += 1
print(f"  ✅ Inserted {inserted} referencias, skipped {len(referencias) - inserted}")


# ═══════════════════════════════════════════════════════════════════════════════
#  8. BLOQUES_PLACA (global)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating bloques_placa ──")
bloques = sq("SELECT * FROM bloques_placa")
print(f"  Found {len(bloques)} bloques")
inserted = 0
for b in bloques:
    existing = run(
        text("SELECT id FROM bloques_placa WHERE modelo_placa = :modelo AND nombre = :nombre"),
        {"modelo": b["modelo_placa"], "nombre": b["nombre"]},
    ).fetchone()
    if not existing:
        run(
            text("""
                INSERT INTO bloques_placa (modelo_placa, nombre, sort_order)
                VALUES (:modelo, :nombre, :sort)
            """),
            {
                "modelo": b["modelo_placa"],
                "nombre": b["nombre"],
                "sort": v(b, "sort_order", 0),
            },
        )
        inserted += 1
print(f"  ✅ Inserted {inserted} bloques, skipped {len(bloques) - inserted}")


# ═══════════════════════════════════════════════════════════════════════════════
#  9. NOTAS_PLACA (tenant_id = null → global or first tenant)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating notas_placa ──")
notas = sq("SELECT * FROM notas_placa")
print(f"  Found {len(notas)} notas")
inserted = 0
for n in notas:
    existing = run(
        text("SELECT id FROM notas_placa WHERE modelo_placa = :modelo AND contenido = :contenido"),
        {"modelo": n["modelo_placa"], "contenido": n["contenido"]},
    ).fetchone()
    if not existing:
        run(
            text("""
                INSERT INTO notas_placa (modelo_placa, contenido, bloque, sort_order, created_at)
                VALUES (:modelo, :contenido, :bloque, :sort, :created_at)
            """),
            {
                "modelo": n["modelo_placa"],
                "contenido": n["contenido"],
                "bloque": v(n, "bloque", ""),
                "sort": v(n, "sort_order", 0),
                "created_at": v(n, "created_at", datetime.now().isoformat()),
            },
        )
        inserted += 1
print(f"  ✅ Inserted {inserted} notas, skipped {len(notas) - inserted}")


# ═══════════════════════════════════════════════════════════════════════════════
#  10. MEDICIONES_PLACA (tenant_id = null → global or first tenant)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating mediciones_placa ──")
mps = sq("SELECT * FROM mediciones_placa")
print(f"  Found {len(mps)} mediciones_placa")
inserted = 0
for m in mps:
    existing = run(
        text("SELECT id FROM mediciones_placa WHERE modelo_placa = :modelo AND punto_medicion = :punto"),
        {"modelo": m["modelo_placa"], "punto": m["punto_medicion"]},
    ).fetchone()
    if not existing:
        run(
            text("""
                INSERT INTO mediciones_placa
                    (modelo_placa, punto_medicion, nombre, valor_esperado, categoria,
                     ic_referencia, notas, bloque, checked, sort_order, created_at)
                VALUES (:modelo, :punto, :nombre, :valor, :categoria,
                        :ic_ref, :notas, :bloque, :checked, :sort, :created_at)
            """),
            {
                "modelo": m["modelo_placa"],
                "punto": m["punto_medicion"],
                "nombre": v(m, "nombre", ""),
                "valor": v(m, "valor_esperado", ""),
                "categoria": v(m, "categoria", ""),
                "ic_ref": v(m, "ic_referencia", ""),
                "notas": v(m, "notas", ""),
                "bloque": v(m, "bloque", ""),
                "checked": bool(v(m, "checked", 0)),
                "sort": v(m, "sort_order", 0),
                "created_at": v(m, "created_at", datetime.now().isoformat()),
            },
        )
        inserted += 1
print(f"  ✅ Inserted {inserted} mediciones_placa, skipped {len(mps) - inserted}")


# ═══════════════════════════════════════════════════════════════════════════════
#  11. PUNTAJES (per tenant — insert for every empresa tenant)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating puntajes ──")
puntajes = sq("SELECT * FROM puntajes")
print(f"  Found {len(puntajes)} puntaje types")

for tid in set(empresa_to_tenant.values()):
    tenant_name = next(
        (k for k, v in empresa_to_tenant.items() if v == tid), "unknown"
    )
    inserted = 0
    for p in puntajes:
        existing = run(
            text("SELECT id FROM puntajes WHERE tenant_id = :tid AND tipo = :tipo"),
            {"tid": tid, "tipo": p["tipo"]},
        ).fetchone()
        if not existing:
            run(
                text("""
                    INSERT INTO puntajes (tenant_id, tipo, puntaje, created_at)
                    VALUES (:tid, :tipo, :puntaje, :created_at)
                """),
                {
                    "tid": tid,
                    "tipo": p["tipo"],
                    "puntaje": p["puntaje"],
                    "created_at": datetime.now().isoformat(),
                },
            )
            inserted += 1
    print(f"  ✅ Tenant {tid}: inserted {inserted} puntajes")


# ═══════════════════════════════════════════════════════════════════════════════
#  12. CONFIG (per tenant — insert for every empresa tenant)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating config ──")
configs = sq("SELECT * FROM config")
print(f"  Found {len(configs)} config keys")

for tid in set(empresa_to_tenant.values()):
    inserted = 0
    for cfg in configs:
        existing = run(
            text("SELECT 1 FROM config WHERE tenant_id = :tid AND clave = :clave"),
            {"tid": tid, "clave": cfg["clave"]},
        ).fetchone()
        if not existing:
            run(
                text("""
                    INSERT INTO config (tenant_id, clave, valor)
                    VALUES (:tid, :clave, :valor)
                """),
                {"tid": tid, "clave": cfg["clave"], "valor": cfg["valor"]},
            )
            inserted += 1
    print(f"  ✅ Tenant {tid}: inserted {inserted} config keys")


# ═══════════════════════════════════════════════════════════════════════════════
#  13. ORDENES (per tenant — map empresa_id → tenant_id)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating ordenes ──")
ordenes = sq("SELECT * FROM ordenes")
print(f"  Found {len(ordenes)} ordenes")

# old_id → new_id mapping for ordenes (needed for sesiones_reparacion)
orden_id_map = {}

for o in ordenes:
    tid = empresa_to_tenant.get(o["empresa_id"])
    if not tid:
        print(f"  ⚠️  Skipping orden {o['id']}: no tenant for empresa_id={o['empresa_id']}")
        continue

    existing = run(
        text("SELECT id FROM ordenes WHERE tenant_id = :tid AND numero = :numero"),
        {"tid": tid, "numero": o["numero"]},
    ).fetchone()

    if existing:
        orden_id_map[o["id"]] = existing[0]
        print(f"  ⚠️  Orden num={o['numero']} already exists, id={existing[0]}")
    else:
        result = run(
            text("""
                INSERT INTO ordenes (tenant_id, numero, fecha, placa, falla, diagnostico,
                    proceso, solucion, estado, resultado, tipo, puntaje, tipo_equipo,
                    marca, modelo, checklist, created_at)
                VALUES (:tid, :numero, :fecha, :placa, :falla, :diagnostico,
                    :proceso, :solucion, :estado, :resultado, :tipo, :puntaje, :tipo_equipo,
                    :marca, :modelo, :checklist, :created_at)
                RETURNING id
            """),
            {
                "tid": tid,
                "numero": o["numero"],
                "fecha": o["fecha"],
                "placa": v(o, "placa", ""),
                "falla": v(o, "falla", ""),
                "diagnostico": v(o, "diagnostico", ""),
                "proceso": v(o, "proceso", ""),
                "solucion": v(o, "solucion", ""),
                "estado": v(o, "estado", "en_curso"),
                "resultado": v(o, "resultado", "n/a"),
                "tipo": v(o, "tipo", ""),
                "puntaje": v(o, "puntaje", 0),
                "tipo_equipo": v(o, "tipo_equipo", ""),
                "marca": v(o, "marca", ""),
                "modelo": v(o, "modelo", ""),
                "checklist": v(o, "checklist", "{}"),
                "created_at": v(o, "created_at", datetime.now().isoformat()),
            },
        )
        new_id = result.scalar()
        orden_id_map[o["id"]] = new_id
        print(f"  ✅ Inserted orden num={o['numero']} → id={new_id} (tenant={tid})")

print(f"  📊 Created {len(orden_id_map)} orden mappings")


# ═══════════════════════════════════════════════════════════════════════════════
#  14. REPARACIONES (per tenant — map orden number → ordenes.id)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating reparaciones ──")
reparaciones = sq("SELECT * FROM reparaciones")
print(f"  Found {len(reparaciones)} reparaciones")

# Build a lookup: (tenant_id, numero) → orden_id
# This is more reliable since reparaciones doesn't have empresa_id
orden_num_lookup = {}
for o in ordenes:
    tid = empresa_to_tenant.get(o["empresa_id"])
    if tid:
        orden_num_lookup[(tid, o["numero"])] = orden_id_map.get(o["id"])

inserted = 0
skipped = 0
for r in reparaciones:
    # Find which tenant this repair belongs to by looking up the order number
    # across all tenants
    matched = False
    for (tid, num), ord_id in orden_num_lookup.items():
        if num == r["orden"]:
            # Found a matching order — check if repair already exists
            existing = run(
                text("SELECT id FROM reparaciones WHERE tenant_id = :tid AND orden_id = :oid AND tipo = :tipo AND puntaje = :puntaje"),
                {"tid": tid, "oid": ord_id, "tipo": r["tipo"], "puntaje": r["puntaje"]},
            ).fetchone()
            if not existing:
                run(
                    text("""
                        INSERT INTO reparaciones (tenant_id, orden_id, fecha, tipo, puntaje, created_at)
                        VALUES (:tid, :oid, :fecha, :tipo, :puntaje, :created_at)
                    """),
                    {
                        "tid": tid,
                        "oid": ord_id,
                        "fecha": r["fecha"],
                        "tipo": r["tipo"],
                        "puntaje": r["puntaje"],
                        "created_at": v(r, "created_at", datetime.now().isoformat()),
                    },
                )
                inserted += 1
            else:
                skipped += 1
            matched = True
            break

    if not matched:
        print(f"  ⚠️  Could not match reparacion id={r['id']} (orden num={r['orden']}) — skipping")

print(f"  ✅ Inserted {inserted} reparaciones, skipped {skipped}")


# ═══════════════════════════════════════════════════════════════════════════════
#  15. SESIONES_REPARACION (per tenant — map old orden_id → new orden_id)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating sesiones_reparacion ──")
sesiones = sq("SELECT * FROM sesiones_reparacion")
print(f"  Found {len(sesiones)} sesiones")

inserted = 0
skipped = 0
for s in sesiones:
    new_orden_id = orden_id_map.get(s["orden_id"])
    if not new_orden_id:
        print(f"  ⚠️  Could not map orden_id={s['orden_id']} for sesion id={s['id']}")
        skipped += 1
        continue

    # Find tenant for this orden
    tid = None
    for o in ordenes:
        if o["id"] == s["orden_id"]:
            tid = empresa_to_tenant.get(o["empresa_id"])
            break
    if not tid:
        print(f"  ⚠️  Could not determine tenant for sesion id={s['id']}")
        skipped += 1
        continue

    existing = run(
        text("SELECT id FROM sesiones_reparacion WHERE orden_id = :oid AND inicio = :inicio"),
        {"oid": new_orden_id, "inicio": s["inicio"]},
    ).fetchone()
    if not existing:
        run(
            text("""
                INSERT INTO sesiones_reparacion (orden_id, tenant_id, inicio, fin, duracion_segundos,
                    notas, estado, created_at)
                VALUES (:oid, :tid, :inicio, :fin, :duracion,
                    :notas, :estado, :created_at)
            """),
            {
                "oid": new_orden_id,
                "tid": tid,
                "inicio": s["inicio"],
                "fin": v(s, "fin"),
                "duracion": v(s, "duracion_segundos", 0),
                "notas": v(s, "notas", ""),
                "estado": v(s, "estado", "finalizada"),
                "created_at": v(s, "created_at", datetime.now().isoformat()),
            },
        )
        inserted += 1
    else:
        skipped += 1

print(f"  ✅ Inserted {inserted} sesiones, skipped {skipped}")


# ═══════════════════════════════════════════════════════════════════════════════
#  16. DIAGRAMAS (global)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating diagramas ──")
diagramas = sq("SELECT * FROM diagramas")
print(f"  Found {len(diagramas)} diagramas")
# This is the biggest table (15003 rows). Use batch insert for performance.

BATCH_SIZE = 500
inserted = 0
# Build param batches and use executemany for speed
stmt = text("""
    INSERT INTO diagramas (marca, modelo, tipo, gdrive_id, nombre_archivo, tamaño_mb, ultima_sync)
    VALUES (:marca, :modelo, :tipo, :gdrive_id, :nombre, :tamano, :ultima_sync)
    ON CONFLICT DO NOTHING
""")
for i in range(0, len(diagramas), BATCH_SIZE):
    batch = diagramas[i : i + BATCH_SIZE]
    params = [
        {
            "marca": v(d, "marca", ""),
            "modelo": v(d, "modelo", ""),
            "tipo": v(d, "tipo", ""),
            "gdrive_id": v(d, "gdrive_id", ""),
            "nombre": v(d, "nombre_archivo", ""),
            "tamano": v(d, "tamaño_mb", 0),
            "ultima_sync": v(d, "ultima_sync", ""),
        }
        for d in batch
    ]
    conn.execute(stmt, params)
    inserted += len(batch)
    print(f"    ... {inserted}/{len(diagramas)}")

print(f"  ✅ Inserted {inserted} diagramas")


# ═══════════════════════════════════════════════════════════════════════════════
#  17. IC_MARCAS (global)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating ic_marcas ──")
ic_marcas = sq("SELECT * FROM ic_marcas")
print(f"  Found {len(ic_marcas)} ic_marcas")
inserted = 0
for m in ic_marcas:
    existing = run(
        text("SELECT id FROM ic_marcas WHERE marking = :marking AND modelo = :modelo AND fabricante = :fabricante"),
        {"marking": v(m, "marking", ""), "modelo": v(m, "modelo", ""), "fabricante": v(m, "fabricante", "")},
    ).fetchone()
    if not existing:
        run(
            text("""
                INSERT INTO ic_marcas (marking, modelo, fabricante, funcion, compatibilidad)
                VALUES (:marking, :modelo, :fabricante, :funcion, :compatibilidad)
            """),
            {
                "marking": v(m, "marking", ""),
                "modelo": v(m, "modelo", ""),
                "fabricante": v(m, "fabricante", ""),
                "funcion": v(m, "funcion", ""),
                "compatibilidad": v(m, "compatibilidad", ""),
            },
        )
        inserted += 1
print(f"  ✅ Inserted {inserted} ic_marcas, skipped {len(ic_marcas) - inserted}")


# ═══════════════════════════════════════════════════════════════════════════════
#  18. IC_COMPATIBILIDAD (global)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n── Migrating ic_compatibilidad ──")
compat = sq("SELECT * FROM ic_compatibilidad")
print(f"  Found {len(compat)} ic_compatibilidad")
inserted = 0
for c in compat:
    existing = run(
        text("SELECT id FROM ic_compatibilidad WHERE fabricante = :fab AND modelo = :mod AND compatibles = :comp"),
        {"fab": v(c, "fabricante", ""), "mod": v(c, "modelo", ""), "comp": v(c, "compatibles", "")},
    ).fetchone()
    if not existing:
        run(
            text("""
                INSERT INTO ic_compatibilidad (fabricante, modelo, compatibles)
                VALUES (:fab, :mod, :comp)
            """),
            {
                "fab": v(c, "fabricante", ""),
                "mod": v(c, "modelo", ""),
                "comp": v(c, "compatibles", ""),
            },
        )
        inserted += 1
print(f"  ✅ Inserted {inserted} ic_compatibilidad, skipped {len(compat) - inserted}")


# ═══════════════════════════════════════════════════════════════════════════════
#  DONE
# ═══════════════════════════════════════════════════════════════════════════════
sqlite.close()
pg.dispose()
print("\n✅🎉 Migration complete!")
