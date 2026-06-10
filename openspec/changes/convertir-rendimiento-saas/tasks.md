# Tasks: Convertir rendimiento-saas a SaaS

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~3500-4500 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Foundation+Auth) → PR 2 (Core API) → PR 3 (Frontend+Deploy) |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

```
Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High
```

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Foundation + Auth + Models + Migration | PR 1 | Project scaffold, all SQLA models, Alembic, JWT auth, tenants, users. Base = main |
| 2 | Core API + Frontend Integration | PR 2 | All CRUD routers, dashboard, search, boarddoctor, PDF. Base = PR 1 |
| 3 | Frontend Auth + Deploy | PR 3 | Login page, auth token headers in SPA, Dockerfile, railway.json, deploy. Base = PR 2 |

## Phase 1: Foundation

- [x] 1.1 Create `app/` structure: main.py, config.py, database.py, dependencies.py, middleware.py
- [x] 1.2 `requirements.txt` — FastAPI, uvicorn, SQLAlchemy 2.0, asyncpg, alembic, bcrypt, pyjwt, weasyprint, pydantic-settings
- [x] 1.3 `app/models/*.py` — SQLAlchemy 2.0 async models for all 19 tables (tenant, user, order, repair, session, board, ic, measurement, solution, reference, config, puntajes, boarddoctor tables)
- [x] 1.4 `app/schemas/*.py` — Pydantic request/response models (health, auth, tenant)
- [x] 1.5 Alembic init (async) + initial migration generating all tables
- [x] 1.6 `app/routers/health.py` — GET /health endpoint
- [x] 1.7 `app/routers/tenants.py` — Tenant CRUD (admin only)

## Phase 2: Auth

- [x] 2.1 `app/services/auth_service.py` — JWT creation/validation, bcrypt hashing, refresh rotation
- [x] 2.2 `app/routers/auth.py` — POST register (admin), login, refresh
- [x] 2.3 `app/dependencies.py` — get_current_user, get_current_tenant, role-check dependencies

## Phase 3: Core API — Orders & Repairs

- [x] 3.1 `app/models/*.py` — Fix `sesiones_reparacion` CREATE TABLE, `reparaciones.orden` FK to `ordenes.id`
- [x] 3.2 `app/routers/orders.py` — CRUD + list + import for orders (ordenes)
- [x] 3.3 `app/routers/repairs.py` — CRUD for reparaciones (month view, add, delete)
- [x] 3.4 `app/routers/sessions.py` — Session timer start/pause/finish, pendiente, stats
- [x] 3.5 `app/routers/scores.py` — Puntajes CRUD + actualizar-valor-punto (tenant-scoped config)

## Phase 4: Core API — Reference Data

- [x] 4.1 `app/routers/boards.py` — Placas CRUD, notas-placa, mediciones-placa, bloques, checklist, reorder
- [x] 4.2 `app/routers/ics.py` — Circuitos CRUD with search, info_detallada
- [x] 4.3 `app/routers/measurements.py` — Mediciones (global) CRUD with search
- [x] 4.4 `app/routers/solutions.py` — Soluciones CRUD with search + report TXT
- [x] 4.5 `app/routers/references.py` — Referencias CRUD with categories + HTML content
- [x] 4.6 `app/routers/types.py` — Tipos de equipo CRUD

## Phase 5: Core API — Advanced Features

- [x] 5.1 `app/routers/dashboard.py` — Summary, trends, top types/marcas/modelos/placas, success rate
- [x] 5.2 `app/routers/reports.py` — Informe de puntos with desglose/comparativa + PDF (weasyprint)
- [x] 5.3 `app/routers/search.py` — Unified search across soluciones, ordenes, mediciones, notas, referencias
- [x] 5.4 `app/routers/boarddoctor.py` — Diagramas, ic-marcas, ic-compatibles, datasheet search + import

## Phase 6: Frontend Integration

- [x] 6.1 `index.html` — Add login page before main app, store JWT in localStorage, redirect on 401
- [x] 6.2 `index.html` — Add Authorization header to ALL fetch() calls (via `apiFetch` wrapper with auto-refresh)
- [x] 6.3 `index.html` — Replace hardcoded `/api/*` with configurable API base URL (`API_BASE` + path translation map)
- [x] 6.4 Wire tenant config (valor_punto) per-tenant in all frontend calculations (global `VALOR_PUNTO`, fetched after login)

## Phase 7: Migration & Deployment

- [x] 7.1 `Dockerfile` — python:3.12-slim, pip install, uvicorn on $PORT, multi-stage build
- [x] 7.2 `railway.json` — DOCKERFILE builder, healthcheck, restart policy
- [x] 7.3 `scripts/migrate_sqlite_to_pg.py` — Export SQLite → PG with ID remapping (empresas→tenants, reparaciones.orden→ordenes.id), validates row counts
- [ ] 7.4 Railway deploy + env config (DATABASE_URL, JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD, CORS_ORIGIN) — **requires user to create Railway account & set up project**
- [ ] 7.5 Verify all 13 frontend views work against new Railway backend — **requires deployment to test**
