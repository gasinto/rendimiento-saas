# Design: Convertir Rendimiento-SaaS

## Technical Approach

Rewrite the single-file Python stdlib http.server + SQLite backend to FastAPI + SQLAlchemy 2.0 async + PostgreSQL. Keep the existing vanilla JS SPA frontend with minimal changes (login page, auth token, API URL). Deploy on Railway. Fix known schema bugs (`sesiones_reparacion` missing CREATE TABLE, `reparaciones.orden` non-FK reference) during migration.

## Architecture Decisions

### Decision: Async SQLAlchemy 2.0

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Sync SQLAlchemy | Simpler, but blocks on async web server | Rejected |
| **Async SQLAlchemy 2.0** | Native `async/await` with FastAPI, session per request | **Chosen** |
| Raw asyncpg | Maximum performance, no ORM | Rejected - need migrations |

### Decision: Tenant isolation strategy

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Separate DB per tenant | Hardest ops, no global queries | Rejected |
| **Row-level `tenant_id`** | Single PG, global shared tables, simple | **Chosen** |
| Schema per tenant | PG schema search_path, complex migrations | Rejected |

### Decision: UUIDs vs integers

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Integer IDs | Keep existing sequence semantics, simpler migration | **Chosen** |
| UUIDs | Safer for multi-tenant, better for distributed | Rejected - unnecessary migration overhead |

### Decision: JWT token storage

| Option | Tradeoff | Decision |
|--------|----------|----------|
| **localStorage** | Works with SPA, XSS vulnerable but acceptable for internal tool | **Chosen** |
| httpOnly cookie | CSRF protection, more complex SPA integration | Rejected |

## Data Flow

```
Client (index.html SPA)
  │  fetch() with Bearer token
  ▼
Railway CDN ──► FastAPI/Uvicorn
  │                  │
  │  Auth:           │  Business:
  │  JWT decode      │  SQLAlchemy async session
  │  tenant_id       │  tenant_id filter injected by dependency
  ▼                  ▼
PostgreSQL ────► Pydantic response ──► JSONResponse
```

## Database Schema

All IDs remain INTEGER (auto-increment). Key new/renamed tables:

| Table | Type | Notes |
|-------|------|-------|
| `tenants` | New | Replaces `empresas`. Columns: id, name, slug (UNIQUE), config (JSONB), active, created_at |
| `users` | New | Columns: id, name, email (UNIQUE), password_hash, role, tenant_id (FK), active, created_at |
| `ordenes` | Modified | Add `tenant_id`, keep `numero` per-tenant UNIQUE. Drop `empresa_id` |
| `reparaciones` | Modified | Add `tenant_id`. Fix `orden` to FK `ordenes.id` (not `ordenes.numero`) |
| `sesiones_reparacion` | **Fix: add CREATE TABLE** | Was missing in init_db. Add `tenant_id` via `orden_id → ordenes` |
| `config` | Modified | Add `tenant_id` (composite PK: tenant_id, clave). Seed valor_punto per tenant |
| `soluciones` | Optional | Add nullable `tenant_id` for private solutions |
| `notas_placa` | Optional | Add nullable `tenant_id` for private notes |

**Global tables (no tenant_id)**: circuitos, mediciones, mediciones_placa, placas, tipos_equipo, puntajes, referencias, diagramas, ic_marcas, ic_compatibilidad, bloques_placa.

## API Design

Organized by router, prefix `/api/{domain}`. Auth endpoints public; all others require JWT.

| Router | Endpoints | Notes |
|--------|-----------|-------|
| `auth.py` | POST register, login, refresh | Public. Admin-only register. |
| `tenants.py` | GET/POST/PUT/DELETE | Admin only. Tenant CRUD. |
| `orders.py` | CRUD + list + import | Matches current `/api/ordenes*`, `/api/agregar` |
| `boards.py` | CRUD + search + blocks | Matches current `/api/placas*`, `/api/bloques*`, `/api/mediciones-placa*`, `/api/notas-placa*` |
| `ics.py` | CRUD + search | Matches `/api/circuitos*` |
| `measurements.py` | CRUD + search | Matches `/api/mediciones*` |
| `solutions.py` | CRUD + search + report | Matches `/api/soluciones*` |
| `references.py` | CRUD + categories | Matches `/api/referencias*` |
| `dashboard.py` | GET summary + stats | Matches `/api/dashboard`, `/api/informe-puntos`, `/api/meses` |
| `config.py` | GET/PUT config | Tenant-scoped config keys |
| `search.py` | GET unified search | Matches `/api/buscar` |
| `boarddoctor.py` | GET diagramas, ic-marcas, ic-compatibles, datasheet | Admin for re-import |

## Auth Design

- **JWT**: HS256, access token 15min, refresh token 7 days
- **bcrypt**: cost factor 12 for password hashing
- **Dependencies**: `get_current_user()` (decodes JWT, returns user), `get_current_tenant()` (returns tenant from user)
- **Roles**: `admin` (full), `technician` (read-write, no delete/user mgmt), `viewer` (read-only)
- **Refresh token rotation**: old refresh token invalidated on use

## Multi-Tenancy Design

- `tenant_id` extracted from JWT (set at login, embedded in token)
- Services receive `tenant_id` via FastAPI `Depends()` — never from user query params
- **Query pattern**: `db.execute(select(Model).where(Model.tenant_id == tenant_id))`
- **Global tables**: queried without tenant filter; read-only for all tenants
- **Tenant seed**: current `empresas` → `tenants` with slug `nsp-notebooks`, tenant_id=1
- **Config isolation**: `config` table becomes composite PK `(tenant_id, clave)`. Migration copies global `valor_punto` to tenant 1.

## Data Migration

1. Export SQLite: `scripts/export_sqlite.py` dumps each table to JSON/CSV
2. Alembic migration creates all PG tables, fixes schema bugs
3. Import script: reads exported data, maps `empresas.id → tenants.id`, `reparaciones.orden → ordenes.id`
4. Validation: row count per table matches between source and target
5. Rollback: SQLite DB untouched during migration; revert by re-pointing frontend to old server.py

## Deployment Design

- **Dockerfile**: python:3.11-slim, uv (or pip), uvicorn
- **railway.json**: health check `/health`, port from `$PORT`
- **Env vars**: `DATABASE_URL`, `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `CORS_ORIGIN`, `LOG_LEVEL`
- **Static files**: FastAPI `StaticFiles` mount for `/static/` during migration; CDN later
- **Health endpoint**: `GET /health` → `{ "status": "ok", "db": "connected" }`

## Error Handling

Single format across all endpoints:
```json
{ "error": { "code": "not_found", "detail": "Order 99999 not found" } }
```
HTTP codes: 400 (validation), 401 (auth), 403 (forbidden), 404 (not found), 409 (conflict), 500 (server error). No stack traces in responses.

## Project Structure

```
rendimiento-saas/
├── app/
│   ├── main.py               # FastAPI app factory, startup/shutdown
│   ├── config.py             # pydantic-settings BaseSettings
│   ├── database.py           # async engine, sessionmaker, get_db
│   ├── dependencies.py       # get_current_user, get_current_tenant
│   ├── middleware.py          # CORS, request logging
│   ├── models/               # SQLAlchemy declarative models
│   │   ├── __init__.py
│   │   ├── tenant.py, user.py, order.py, board.py
│   │   ├── ic.py, measurement.py, solution.py
│   │   ├── reference.py, boarddoctor.py
│   ├── schemas/              # Pydantic request/response
│   ├── routers/              # FastAPI APIRouter modules
│   │   ├── auth.py, tenants.py, orders.py, boards.py
│   │   ├── ics.py, measurements.py, solutions.py
│   │   ├── references.py, dashboard.py, config.py
│   │   ├── search.py, boarddoctor.py
│   ├── services/             # Business logic
│   │   ├── auth_service.py, tenant_service.py
│   │   ├── order_service.py, search_service.py
│   │   ├── dashboard_service.py, pdf_service.py
│   └── alembic/              # Migrations
├── static/                   # Frontend files (unchanged)
├── data/                     # BoardDoctor CSVs, temp files
├── scripts/
│   └── migrate_sqlite_to_pg.py
├── Dockerfile
├── railway.json
├── pyproject.toml
└── requirements.txt
```

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Unit | Auth, validation, services | pytest + pytest-asyncio, mocked DB |
| Integration | CRUD endpoints, tenant isolation | Testcontainers PostgreSQL |
| E2E | Full login → CRUD flow | httpx AsyncClient against test app |

**First priority**: auth endpoints (register, login, refresh, token validation), then critical CRUD (orders, reparaciones), then search.

## Migration / Rollout

1. **Phase 0**: Setup Railway project, PostgreSQL, environment variables
2. **Phase 1**: Migrate backend to FastAPI with SQLite (same server.py DB file for now)
3. **Phase 2**: Add auth layer, JWT, login page
4. **Phase 3**: Switch to PostgreSQL via Alembic migration
5. **Phase 4**: Deploy to Railway, cut over traffic
6. **Rollback**: Old server.py + SQLite DB untouched. Revert `API` variable in frontend to empty string.

## Open Questions

- [ ] Redis for refresh token blacklist or DB-only?
- [ ] Handle session timer continuity during migration (sesiones_reparacion active sessions)?
- [ ] Rate limiting: middleware or reverse proxy level?
