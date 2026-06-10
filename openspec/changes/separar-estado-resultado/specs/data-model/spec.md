# Delta: Separar Estado de Resultado

Split `estado` in `ordenes` into administrative `estado` (en_curso/completado) and technical `resultado` (reparado/no_reparado/n/a).

## Requirements

### FR-001: Schema — Add `resultado` column

The `ordenes` table MUST have a `resultado TEXT DEFAULT 'n/a'` column added via ALTER TABLE in `init_db()`.

#### Scenario: Column added to new DB

- GIVEN a fresh database with no `resultado` column
- WHEN `init_db()` runs
- THEN `resultado` column is added with `DEFAULT 'n/a'`

### FR-002: Data Migration — Map existing estados

The system MUST migrate existing rows: `en_curso` → (estado=en_curso, resultado=n/a); `reparado`/`completado` → (estado=completado, resultado=reparado); `no_reparado` → (estado=completado, resultado=no_reparado).

#### Scenario: All estado values migrate

- GIVEN rows with estado values `en_curso`, `reparado`, `completado`, `no_reparado`
- WHEN migration runs in `init_db()`
- THEN each row has correct (estado, resultado) per the mapping above

#### Scenario: Empty table — no-op

- GIVEN an empty `ordenes` table
- WHEN migration runs
- THEN no rows are affected, no errors raised

### FR-003: Solutions Search — Unchanged estado filter

Solutions API (`/api/ordenes-detalle?estado=completado`) MUST continue filtering by `estado=completado` regardless of `resultado`.

#### Scenario: All completado orders appear in solutions

- GIVEN orders with estado=completado and resultado=reparado, resultado=no_reparado
- WHEN solutions view fetches with `estado=completado`
- THEN all orders with estado=completado are returned irrespective of resultado

### FR-004: Dashboard — Stats use `resultado`

Dashboard success rate queries MUST use `resultado` for reparados/no_reparados counts. `en_curso` count continues reading from `estado`.

#### Scenario: Monthly stats reflect resultado

- GIVEN orders with estado=completado, some resultado=reparado, some resultado=no_reparado
- WHEN dashboard computes monthly/yearly success rate
- THEN reparados = COUNT WHERE resultado='reparado', no_reparados = COUNT WHERE resultado='no_reparado'

### FR-005: Backwards-compat API — Legacy estado mapping

API endpoints (`agregar_orden_detalle`, `actualizar_orden_detalle`) MUST accept legacy `estado` values (`reparado`, `no_reparado`) and map internally: `estado=completado` with corresponding `resultado`. If both legacy `estado` and explicit `resultado` are sent, `resultado` MUST take precedence.

#### Scenario: Client sends legacy reparado

- GIVEN a POST with `estado=reparado` and no `resultado`
- WHEN the server processes the request
- THEN stored as estado=completado, resultado=reparado

#### Scenario: Client sends legacy no_reparado

- GIVEN a POST with `estado=no_reparado` and no `resultado`
- WHEN the server processes the request
- THEN stored as estado=completado, resultado=no_reparado

#### Scenario: Both legacy estado and explicit resultado

- GIVEN a POST with `estado=reparado` and `resultado=reparado`
- WHEN the server processes the request
- THEN stored as estado=completado, resultado=reparado (explicit wins)

### FR-006: Filter Dropdown — Split estado + resultado

Reparaciones filter UI MUST show two separate selects: `estado` (en_curso/completado/todos) and `resultado` (reparado/no_reparado/n/a/todos). Both MUST apply with AND logic.

#### Scenario: Filter by estado only

- GIVEN the reparaciones view
- WHEN user selects `completado` in estado filter and leaves resultado as todos
- THEN table shows all estado=completado orders

#### Scenario: Filter by both

- GIVEN the reparaciones view
- WHEN user selects `completado` in estado and `reparado` in resultado
- THEN table shows only orders matching both filters

### FR-007: Edit Form — Separate selects

Edit repair modal MUST show distinct `estado` (en_curso/completado) and `resultado` (reparado/no_reparado/n/a) selects. `resultado` SHOULD be disabled when `estado=en_curso`.

#### Scenario: Load existing order

- GIVEN an order with estado=completado, resultado=reparado
- WHEN the user opens the edit modal
- THEN both selects render with correct current values pre-selected

### FR-008: Table Display — Both columns

Reparaciones table MUST show both `estado` and `resultado` — either as separate columns or a combined cell (e.g. "Completado — Reparado").

#### Scenario: Table renders mixed estados

- GIVEN a mix of orders with different estado+resultado combinations
- WHEN the reparaciones table is displayed
- THEN each row shows both administrative status and technical result

## Non-Functional Requirements

### NFR-001: Migration idempotent

ALTER TABLE MUST fail silently if `resultado` column already exists (follow existing try/except pattern at server.py:146-160). The data migration UPDATE MUST skip if the column was already migrated.

### NFR-002: New orders default resultado

New orders created without explicit `resultado` MUST default to `'n/a'`.

### NFR-003: NULL resultado handling

`NULL` resultado values SHOULD be treated as `'n/a'` in display and filter logic.

## Edge Cases

| Case | Behavior |
|------|----------|
| `estado=en_curso` + `resultado=reparado` | Allowed (partial work recorded), resultado disabled by default in UI |
| Legacy client sends `reparado` in `estado` and no `resultado` | Mapped: estado=completado, resultado=reparado |
| Old API client sends `completado` + `resultado=n/a` | Stored as-is (valid admin close with no technical result) |
| Duplicate migration runs | Second run: ALTER TABLE fails silently, UPDATE finds no old `reparado`/`no_reparado` estado values to remap — no-op entirely |
| Rollback | `ALTER TABLE ordenes DROP COLUMN resultado` (SQLite 3.35+) and reverse the estado mapping |
