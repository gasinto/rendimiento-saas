# REST API Specification

## Purpose

Migrate the monolithic `APIHandler` static-method routing to FastAPI with Pydantic validation, OpenAPI docs, and structured error responses. The existing ~80 endpoints are preserved but restructured.

## Requirements

### Req 1: FastAPI Router Structure
- One router per domain: auth, orders, repairs, boards, catalog, config, search, export
- Router prefix: `/api/{domain}`
- All routes behind auth middleware (except `/api/auth/*`)
- OpenAPI `/docs` and `/redoc` enabled in staging, disabled in production

#### Scenario: Domain router registration
- GIVEN the FastAPI app starts
- WHEN inspecting the OpenAPI schema at `/openapi.json`
- THEN all endpoint paths are listed under `/api/*`, with request/response schemas

### Req 2: Pydantic Models
- One model file per domain: `models/{domain}.py`
- Request models for POST/PUT bodies, Response models for all endpoints
- Query parameter models for GET endpoints with filters
- All models inherit from `pydantic.BaseModel` with `orm_mode = True`

#### Scenario: Create order validation
- GIVEN a POST `/api/orders` with body `{ "cliente": "", "equipo": null }`
- WHEN FastAPI validates the request
- THEN response 422 with field-level errors: `cliente` (must not be empty), `equipo` (must not be null)

### Req 3: Standard Error Handling
- Single exception handler mapping all exceptions to `{ "error": { "code": "...", "detail": "..." } }`
- HTTP codes: 400 (validation), 401 (auth), 403 (forbidden), 404 (not found), 409 (conflict), 500 (server error)
- Stack traces logged server-side only, never returned to client

#### Scenario: Not found error
- GIVEN a non-existent order ID
- WHEN GET `/api/orders/99999`
- THEN response 404 with `{ "error": { "code": "not_found", "detail": "Order 99999 not found" } }`

### Req 4: Export Endpoints
- Export endpoints (boards CSV, IC catalog CSV) use `StreamingResponse` with `text/csv`
- Export respects tenant isolation (only current tenant's data)

#### Scenario: CSV export
- GIVEN an authenticated user
- WHEN GET `/api/export/boards?format=csv`
- THEN response 200 with `Content-Type: text/csv` and file download headers

### Req 5: Migration Phases
- **Phase 1** (spec scope): Port all read endpoints to FastAPI, add auth middleware in parallel
- **Phase 2** (future): Migrate write endpoints, replace SQLite with PostgreSQL
- **Phase 3** (future): Extract BoardDoctor as background Celery task, replace fpdf2 with weasyprint

### Non-Functional Requirements
- Response time P95 under 200ms for read queries, 500ms for writes
- OpenAPI schema covers 100% of endpoints by phase 1 completion
- CORS configured for single origin (production domain)
- Rate limiting: 100 req/min per user, 1000 req/min per tenant
