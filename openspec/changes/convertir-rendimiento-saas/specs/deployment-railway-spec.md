# Railway Deployment Specification

## Purpose

Deploy the application to Railway with PostgreSQL, environment-based configuration, SSL, custom domain, and zero-downtime deploys.

## Requirements

### Req 1: Environment Configuration
- All secrets and config via environment variables:
  | Variable | Purpose | Default |
  |---|---|---|
  | `DATABASE_URL` | PostgreSQL connection string | required |
  | `JWT_SECRET` | JWT signing key (32+ chars) | required |
  | `ADMIN_EMAIL` | Initial admin account | required |
  | `ADMIN_PASSWORD` | Initial admin password | required |
  | `CORS_ORIGIN` | Allowed CORS origin | `https://custom.domain` |
  | `LOG_LEVEL` | Python logging level | `INFO` |
- No secrets in code, no `.env` committed

#### Scenario: Staging vs Production config
- GIVEN a Railway PR preview deployment
- WHEN the app starts
- THEN it reads `DATABASE_URL` from Railway environment, uses `LOG_LEVEL=DEBUG` for staging

### Req 2: PostgreSQL Migration
- SQLite-to-PostgreSQL migration script: `scripts/migrate_sqlite_to_pg.py`
- Migrates schema, then data, then validates row counts match
- Script is idempotent (safe to re-run)
- Alembic for future schema migrations

#### Scenario: Migration run
- GIVEN an existing SQLite database with data
- WHEN `scripts/migrate_sqlite_to_pg.py` runs
- THEN all tables and rows exist in PostgreSQL with correct FKs and no data loss

### Req 3: Build & Start
- `Dockerfile` or `railway.json` build config:
  - Python 3.11+ base image
  - `pip install -r requirements.txt`
  - `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Health check endpoint: `GET /health` returns `{ "status": "ok", "db": "connected" }`

#### Scenario: Build succeeds
- GIVEN a commit to main branch
- WHEN Railway builds the container
- THEN `/health` responds 200 within 30 seconds of container start

### Req 4: Custom Domain & SSL
- Custom domain (e.g., `app.nspservice.com`) configured via Railway domain settings
- SSL/TLS auto-provisioned via Railway + Let's Encrypt
- Strict-Transport-Security header in responses

#### Scenario: HTTPS redirect
- GIVEN a request to `http://custom.domain/health`
- WHEN the app processes it
- THEN it responds 301 redirect to `https://custom.domain/health`

### Req 5: Database Backups
- Railway PostgreSQL automatic daily backups enabled
- Retention: 7 daily, 4 weekly
- Manual backup trigger available before destructive migrations

### Non-Functional Requirements
- 99.5% uptime SLA target
- Cold start under 10 seconds
- PostgreSQL volume: 1 GB minimum, auto-scaling as needed
- Deploy rollback: support Railway automatic rollback on health check failure
