# User Authentication Specification

## Purpose

Add JWT-based authentication layer to the existing SPA. Every API request must be authenticated; unauthenticated requests are rejected with 401.

## Requirements

### Req 1: Login Endpoint
- **Endpoint**: `POST /api/auth/login`
- Accepts email + password, returns access token (15 min) and refresh token (7 days)
- Password stored as bcrypt hash
- Rate-limited: max 5 attempts per IP per minute

#### Scenario: Successful login
- GIVEN a registered user with email `t@nsp.com` and password `valid123`
- WHEN POST `/api/auth/login` with `{ email: "t@nsp.com", password: "valid123" }`
- THEN response 200 with `{ access_token, refresh_token, user: { id, name, role } }`

#### Scenario: Invalid credentials
- GIVEN a registered user
- WHEN POST `/api/auth/login` with wrong password
- THEN response 401 with `{ error: "invalid_credentials" }`

### Req 2: Registration Endpoint
- **Endpoint**: `POST /api/auth/register`
- Creates user with hashed password; admin-only access
- Fields: name, email, password, tenant_id, role (default: "viewer")

#### Scenario: Admin registers a technician
- GIVEN an authenticated admin user with valid token
- WHEN POST `/api/auth/register` with `{ name: "Técnico1", email: "tec1@nsp.com", password: "pass", role: "technician", tenant_id: 1 }`
- THEN response 201 with `{ id, name, email, role }` and password NOT returned

### Req 3: Token Refresh
- **Endpoint**: `POST /api/auth/refresh`
- Accepts refresh token, returns new access token
- Refresh tokens are single-use (rotation)

#### Scenario: Token rotation
- GIVEN a valid refresh token
- WHEN POST `/api/auth/refresh` with `{ refresh_token }`
- THEN response 200 with new `{ access_token, refresh_token }`, old refresh token invalidated

### Req 4: Auth Middleware
- Every `/api/*` request (except `/api/auth/*`) requires valid `Authorization: Bearer <token>` header
- Middleware decodes JWT, attaches user payload to request context
- Returns 401 if missing, expired, or malformed

#### Scenario: Protected endpoint without token
- GIVEN no Authorization header
- WHEN GET `/api/ordenes`
- THEN response 401

### Req 5: Role-Based Access
- Three roles: `admin` (full access), `technician` (read-write on orders, repairs, boards), `viewer` (read-only)
- Admin can manage users, assign roles, delete data
- Technician cannot delete, cannot manage users
- Viewer cannot create or edit any resource

### Non-Functional Requirements
- JWT secret loaded from environment variable `JWT_SECRET`, minimum 32 chars
- All passwords hashed with bcrypt (cost factor 12)
- Tokens use `HS256` algorithm
- Frontend redirects to `/login` on 401, preserves intended URL for post-login redirect

### Data Contract: users table

| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PK, auto-increment |
| name | TEXT | NOT NULL |
| email | TEXT | UNIQUE, NOT NULL |
| password_hash | TEXT | NOT NULL |
| role | TEXT | CHECK IN ('admin','technician','viewer'), DEFAULT 'viewer' |
| tenant_id | INTEGER | FK -> tenants.id, NOT NULL |
| active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
