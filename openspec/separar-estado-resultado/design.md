# Design: Separar estado de resultado en órdenes

## Technical Approach

Add a `resultado TEXT DEFAULT 'n/a'` column to the `ordenes` table via ALTER TABLE migration, splitting the current overloaded `estado` field into two separate concerns: administrative flow (`estado`) and technical outcome (`resultado`). Server API normalizes incoming data (backwards-compat with legacy estado values), dashboard queries switch to `resultado` for stats, and UI splits filter/display/edit into two independent fields.

## Architecture Decisions

### Decision: Schema migration strategy

| Option | Tradeoff | Decision |
|--------|----------|----------|
| New table + JOIN | Cleaner normalization, but breaks all existing queries | ❌ |
| ALTER TABLE + column | Follows existing pattern (bloque, tipo_equipo, checklist migrations), zero query changes | ✅ |

**Rationale**: The codebase has a well-established migration pattern — `ALTER TABLE ADD COLUMN` in `init_db()` wrapped in try/except. This minimizes risk and keeps all queries backward-compatible. Adding a new column to existing rows is a single UPDATE.

### Decision: Backwards compatibility at API layer

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Reject old estado values | Breaks existing clients/scripts on upgrade | ❌ |
| Normalize at API entry | Transparent migration, no breakage | ✅ |

**Rationale**: Existing clients send `reparado`/`no_reparado` as estado values. The API layer maps them: `reparado` → `{estado: completado, resultado: reparado}`, `no_reparado` → `{estado: completado, resultado: no_reparado}`. The `estado` field stores only `en_curso` or `completado`.

### Decision: Dashboard stats switch to resultado

**Rationale**: The dashboard success rate queries currently use `estado IN ('reparado','completado')` for "reparados" and `estado = 'no_reparado'` for "no reparados". After migration, these become `resultado = 'reparado'` and `resultado = 'no_reparado'`. The `estado = 'en_curso'` filter remains unchanged since `resultado = 'n/a'` is semantically equivalent.

## Data Flow

```
POST/PUT /api/ordenes-detalle
       │
       ▼
API handler: normalize_estado_resultado(data)
  │  - If estado is 'reparado' → estado=completado, resultado=reparado
  │  - If estado is 'no_reparado' → estado=completado, resultado=no_reparado
  │  - If resultado is provided, keep as-is
  │  - Default: resultado='n/a' for new orders
  │
  ▼
SQL: INSERT/UPDATE ordenes SET estado=?, resultado=?
       │
       ▼
GET /api/ordenes-detalle → returns both estado AND resultado
       │
       ▼
UI renders:
  - Filter: estado dropdown + resultado dropdown
  - Table: estado tag + resultado tag
  - Edit form: separate selects

GET /api/dashboard → uses resultado for stats
  - reparados: COUNT WHERE resultado='reparado'
  - no_reparados: COUNT WHERE resultado='no_reparado'
  - en_curso: COUNT WHERE estado='en_curso' (unchanged)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `server.py:44-49` | Modify | Add `resultado TEXT DEFAULT 'n/a'` to CREATE TABLE |
| `server.py:151-160` | Modify | Add ALTER TABLE migration for resultado column |
| `server.py:161-170` | Insert | Data migration: map old estado to new estado+resultado |
| `server.py:570-595` | Modify | `listar_ordenes_detalle` — include `resultado` in SELECT/response |
| `server.py:605-635` | Modify | `agregar_orden_detalle` — accept `resultado`, default `n/a`, normalize estado |
| `server.py:647-670` | Modify | `actualizar_orden_detalle` — include `resultado` in updatable fields |
| `server.py:1512-1548` | Modify | Dashboard queries — use `resultado` instead of `estado` for repair stats |
| `index.html:644-652` | Modify | Filter dropdown — add `resultado` filter, simplify `estado` filter |
| `index.html:3295-3316` | Modify | Reparaciones table — show both `estado` and `resultado` with tags |
| `index.html:3329-3345` | Modify | Edit form — separate `estado` select (en_curso/completado) + `resultado` select (reparado/no_reparado/n/a) |
| `index.html:3436-3441` | Modify | `guardarReparacion` — include `resultado` in PUT body |

## Interfaces / Contracts

```python
# Normalization helper
def _normalize_estado_resultado(data: dict) -> dict:
    """Map legacy estado values to new estado+resultado."""
    estado = data.get("estado", "en_curso")
    resultado = data.get("resultado")  # may be absent
    
    if resultado is None:
        if estado == "reparado":
            estado = "completado"
            resultado = "reparado"
        elif estado == "no_reparado":
            estado = "completado"
            resultado = "no_reparado"
        elif estado == "completado":
            resultado = "n/a"
        else:  # en_curso or unknown
            resultado = "n/a"
    
    data["estado"] = estado
    data["resultado"] = resultado
    return data
```

```python
# Dashboard query (after migration)
"SUM(CASE WHEN resultado = 'reparado' THEN 1 ELSE 0 END) as reparados"  # was estado IN ('reparado','completado')
"SUM(CASE WHEN resultado = 'no_reparado' THEN 1 ELSE 0 END) as no_reparados"  # was estado = 'no_reparado'
"SUM(CASE WHEN estado = 'en_curso' THEN 1 ELSE 0 END) as en_curso"  # unchanged
```

```python
# API response shape (listar_ordenes_detalle)
{
  "ordenes": [{
    ...,  
    "estado": "en_curso|completado",
    "resultado": "reparado|no_reparado|n/a",
    ...
  }]
}
```

## Migration Strategy

1. **Schema**: `ALTER TABLE ordenes ADD COLUMN resultado TEXT DEFAULT 'n/a'` — runs in `init_db()` before data migration, wrapped in try/except per existing pattern.
2. **Data**: Single atomic UPDATE after schema:
   - `UPDATE ordenes SET resultado='n/a', estado='en_curso' WHERE estado='en_curso'`
   - `UPDATE ordenes SET resultado='reparado', estado='completado' WHERE estado='reparado'`
   - `UPDATE ordenes SET resultado='no_reparado', estado='completado' WHERE estado='no_reparado'`
   - `UPDATE ordenes SET resultado='n/a' WHERE estado='completado' AND resultado IS NULL`
3. **Atomicity**: Migration runs inside a single connection with `conn.commit()` — avoids partial state.
4. **Rollback**: `ALTER TABLE ordenes DROP COLUMN resultado` (SQLite 3.35+). Original estado values are preserved in the migration: `en_curso` stays `en_curso`, `reparado`→`completado` (lossy — reverse migration needs a lookup table or backup).

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Migration | Existing rows map correctly | Insert rows with old estado values, restart DB, verify new fields |
| API | POST/PUT accepts both old and new format | Send `{estado: "reparado"}` → verify `{estado: "completado", resultado: "reparado"}` |
| Dashboard | Stats use resultado | Verify counts match before and after migration |
| UI | Filter, display, edit all show both fields | Manual verification of each view |

## Open Questions

- [ ] None — proposal and spec cover all cases; implementation is straightforward.

## Delivery Risk Forecast

- **400-line budget risk**: Medium — server.py changes are ~30 lines, index.html changes are ~40 lines; well within budget.
- **Decision needed before apply**: No.
- **Chained PRs recommended**: No.
