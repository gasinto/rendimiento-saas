# Tenant Multi-Tenancy Specification

## Purpose

Convert the single-tenant SQLite database to multi-tenant PostgreSQL with row-level tenant isolation. Seed the existing "NSP Notebooks" as the first tenant.

## Requirements

### Req 1: Tenants Table
- Create `tenants` table: id, name, slug (unique), config (JSON), active, created_at
- Migrate existing `empresas` row to `tenants` with `slug = "nsp-notebooks"`
- `empresas` table may be kept for reference but all new logic targets `tenants`

#### Scenario: Seed tenant migration
- GIVEN the current database has 1 row in `empresas` ("NSP Notebooks")
- WHEN running the tenant migration
- THEN a row in `tenants` exists with `name = "NSP Notebooks"`, `slug = "nsp-notebooks"`, `active = true`

### Req 2: Tenant-ID Column Strategy
- Add `tenant_id` column to all tenant-scoped tables: ordenes, reparaciones, sesiones_reparacion, puntajes, notas_placa, mediciones_placa, config
- Shared tables (no tenant_id): diagramas, soluciones, referencias, mediciones, ic_marcas, ic_compatibilidad, circuitos, tipos_equipo, placas, bloques_placa
- Composite FK where applicable (e.g., `reparaciones(tenant_id, orden)` references `ordenes(tenant_id, numero)`)

#### Scenario: Tenant creates an order
- GIVEN tenant A and tenant B both exist, each with their own orders
- WHEN tenant A lists orders
- THEN only tenant A's orders are returned, tenant B's orders are invisible

### Req 3: Tenant Isolation in Queries
- All SELECT/INSERT/UPDATE/DELETE on scoped tables MUST filter by `tenant_id`
- Tenant ID is extracted from JWT payload (set by auth middleware)
- A `tenant_scoped` decorator or middleware applies the filter automatically
- Cross-tenant data leaks are a P0 bug

#### Scenario: Cross-tenant leak attempt
- GIVEN a user from tenant A with valid JWT
- WHEN attempting GET `/api/ordenes?tenant_id=2` (specifying other tenant)
- THEN the explicit `tenant_id` parameter is ignored — the user's own tenant_id is always used

### Req 4: Per-Tenant Configuration
- `config` table gets `tenant_id` column (composite PK with `clave`)
- Migrate existing global config rows (like `valor_punto`) to tenant-scoped rows for tenant 1
- New tenant onboarding creates default config rows (copy from template)

#### Scenario: Tenant-specific valor_punto
- GIVEN tenant A has `valor_punto = 150` and tenant B has `valor_punto = 200`
- WHEN tenant A loads dashboard
- THEN point calculations use 150, not 200

### Non-Functional Requirements
- Each tenant supports up to 25 concurrent users
- Tenant data is never accessible across tenants (zero-trust model)
- Tenant count impacts performance linearly; no shared-hotspot indexes

### Data Contract: tenants table

| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PK, auto-increment |
| name | TEXT | NOT NULL |
| slug | TEXT | UNIQUE, NOT NULL |
| config | JSONB | DEFAULT '{}'|
| active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
