# Proposal: Convertir Rendimiento-SaaS

## Intent

Convert the local single-tenant repair workshop app to a multi-tenant SaaS. Backend rewritten to FastAPI + PostgreSQL, deployed on Railway. Existing SPA frontend kept with login layer added. The shared knowledge base (ICs, diagrams, measurements, solutions) becomes a cross-tenant network effect.

## Scope

### In Scope
- Backend rewrite: Python stdlib http.server → FastAPI + SQLAlchemy 2.0 + Alembic
- Database: SQLite → PostgreSQL (managed by Railway)
- Auth: JWT + bcrypt, roles (admin, technician, viewer)
- Multi-tenancy: tenant_id row isolation, shared global reference tables
- Deployment: Railway (auto-deploy, SSL, custom domain)
- Frontend: Login page, auth token, API URL switch to Railway
- BoardDoctor: extract to admin-only background endpoint
- PDF: fpdf2 → weasyprint

### Out of Scope
- Frontend framework migration (Vue/Svelte/React)
- Mobile app or native clients
- Real-time features (WebSockets, SSE)
- Payment/subscription system
- Rate limiting or API key management
- CI/CD beyond Railway auto-deploy

## Capabilities

### New Capabilities
- `user-auth`: JWT login/register, 3 roles, token refresh
- `tenant-multi-tenancy`: tenant isolation via tenant_id, seed tenant (NSP Notebooks), global shared tables
- `api-rest`: FastAPI REST layer replacing http.server, OpenAPI docs
- `deployment-railway`: Railway provisioning, PostgreSQL, SSL, custom domain

### Modified Capabilities
None — existing spec-level behavior preserved; implementation only.

## Approach

FastAPI rewrite with incremental migration. Keep existing frontend unchanged, add login page, deploy new backend to Railway. Shared PostgreSQL with tenant_id isolation. Reference tables (circuitos, mediciones, diagramas, soluciones, fichas) stay global. Fix the missing `sesiones_reparacion` CREATE TABLE bug.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `server.py` | Rewrite | Replaced by FastAPI app |
| `index.html` | Modified | Login page, auth token handling |
| `placas-data.js` | Modified | API calls → Railway URL |
| DB schema | Migration | SQLite → PostgreSQL + Alembic |
| `requirements.txt` | New | FastAPI, SQLAlchemy, Alembic, asyncpg, weasyprint |
| `Dockerfile` / `railway.json` | New | Deployment config |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| SQLite → PostgreSQL type mismatches | Medium | Stage migration first |
| BoardDoctor CSV paths break | Medium | Keep local import fallback |
| Frontend API timeout on Railway cold start | Low | Health ping keep-warm |
| Data loss during migration | Low | Full SQLite backup, rollback script |

## Rollback Plan

Keep current `server.py` + SQLite DB untouched during development. Deploy new backend to Railway staging first. If migration fails: restore SQLite backup, revert to old server.py. Frontend uses env var to toggle API URL between old and new.

## Dependencies

- Railway account
- GitHub repo connected to Railway

## Success Criteria

- [ ] All 15+ tables migrated to PostgreSQL with data intact
- [ ] Auth system works: register, login, 3 roles, token refresh
- [ ] Every existing frontend feature works via FastAPI endpoints
- [ ] Tenant isolation verified: Tenant A cannot see Tenant B data
- [ ] BoardDoctor importable as admin-only background endpoint
- [ ] Deployment live on Railway with custom domain + SSL
- [ ] Rollback plan tested and documented
