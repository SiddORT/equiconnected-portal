# EquiConnected Portal

A next-generation healthcare coordination platform — secure, extensible, and built for production.

## Architecture

| Layer | Technology |
|---|---|
| Frontend | React 19 + TypeScript + Vite |
| Backend | Python 3.13 + FastAPI |
| Database | PostgreSQL + SQLAlchemy 2.x ORM |
| Migrations | Alembic |
| Auth | JWT (access + refresh) + Argon2id |

## Project Structure

```
/
├── frontend/          # React + TypeScript + Vite (port 5000)
│   └── src/
│       ├── app/       # Router, AuthContext, providers
│       ├── components/
│       │   ├── ui/    # Design system primitives (Button, Input, Card, …)
│       │   └── layout/# AdminLayout, AdminSidebar, Header, Footer, …
│       ├── features/  # Feature modules (admin AuthGuard, …)
│       ├── pages/     # Page components (LoginPage, DashboardPage, …)
│       ├── api/       # Axios client + typed API functions
│       ├── types/     # TypeScript types mirroring backend schemas
│       └── styles/    # Design tokens (tokens.css) + global CSS
│
└── backend/           # FastAPI (port 8000)
    ├── app/
    │   ├── api/v1/    # Route handlers — thin, delegates to services
    │   ├── auth/      # JWT Bearer dependency + require_role factory
    │   ├── core/      # Config, logging (structlog), security, rate limiter
    │   ├── db/        # Engine, session, declarative base
    │   ├── models/    # SQLAlchemy ORM models
    │   ├── repositories/ # Data access layer — all DB queries go here
    │   ├── schemas/   # Pydantic request/response schemas
    │   └── services/  # Business logic (AuthService)
    ├── alembic/       # Database migrations
    ├── scripts/       # Operational scripts (seed_admin.py)
    └── tests/         # pytest test suites
```

---

## Environment Variables

### Required secrets (set in Replit Secrets or a `.env` file)

| Variable | Description |
|---|---|
| `SECRET_KEY` | JWT signing key. Generate with: `python -c "import secrets; print(secrets.token_hex(64))"` |
| `DATABASE_URL` | PostgreSQL connection string. **Provided automatically by Replit.** |

### Optional variables (with defaults)

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | `development`, `staging`, or `production` |
| `DEBUG` | `false` | Enable SQLAlchemy query logging |
| `ALLOWED_ORIGINS` | `http://localhost:5000,...` | Comma-separated CORS origins |
| `COOKIE_SECURE` | `false` | Set `true` in production (requires HTTPS) |
| `COOKIE_SAMESITE` | `lax` | Cookie SameSite policy |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Short-lived access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Long-lived refresh token lifetime |

Copy `backend/.env.example` to `backend/.env` and fill in values.  
**Never commit `.env` to version control.**

---

## Setup

### 1. Start PostgreSQL

Replit provisions PostgreSQL automatically.  
For local development, ensure PostgreSQL is running and `DATABASE_URL` is set.

### 2. Run migrations

```bash
cd backend
alembic upgrade head
```

This creates all tables: `roles`, `users`, `refresh_tokens`, `audit_logs`.

### 3. Bootstrap or verify the administrator

```bash
cd backend
python scripts/seed_admin.py
```

**Requirements:**
- `ADMIN_EMAIL` — bootstrap administrator email, supplied through the environment
- `ADMIN_PASSWORD` — bootstrap password, supplied through the environment (minimum 12 characters)
- `ADMIN_FIRST_NAME` / `ADMIN_LAST_NAME` — optional

Keep credentials in Replit Secrets or another secret manager; never pass them as
command-line arguments or commit them to a file. The normal command is safe to
run after migrations and during deployment. It has exactly these outcomes:

| Existing state | Normal command outcome |
|---|---|
| No account at `ADMIN_EMAIL` | Creates one active administrator account. |
| Active administrator with matching `ADMIN_PASSWORD` | Verifies it without changing the account. |
| Existing account with a different password, inactive state, or non-admin role | Reports a secret-safe diagnostic and makes no changes. |

The diagnostic shows whether the supplied credential matches, but never prints a
password or password hash. A mismatch exits with status `2` so automation can
surface it; it does **not** mean that the configured password was applied.

#### Intentional password recovery

Only an authorized operator who has confirmed the target database should run a
password recovery. Recovery is deliberately separate from normal bootstrap:

```bash
cd backend
ADMIN_RECOVERY_CONFIRM=RESET_BOOTSTRAP_PASSWORD python scripts/seed_admin.py
```

This command uses the current `ADMIN_PASSWORD` secret to replace the password
for the existing, active administrator named by `ADMIN_EMAIL`. It preserves the
account ID, profile, active state, and role assignments, then revokes all of
that account's stored refresh sessions. Existing access tokens remain usable
only until their normal short expiry (15 minutes by default). Recovery refuses
to activate or promote an account, and it refuses to create an account while
the recovery confirmation is set.

Never add `ADMIN_RECOVERY_CONFIRM` to deployment configuration or automated
scripts. Changing the `ADMIN_PASSWORD` secret alone is not a password reset:
run the normal command first to verify the state, then use the explicit
recovery command only when a rotation is intended.

Database migrations and the deployment/post-merge procedures do not reset
bootstrap credentials. Run the normal verification command separately after
confirming the deployment points at the intended database.

### 4. Start the backend

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or use the Replit **Backend API** workflow.

### 5. Start the frontend

```bash
cd frontend
npm run dev
```

Or use the Replit **Frontend** workflow.  
Vite proxies `/api` → `http://localhost:8000`.

---

## Admin Routes

| Path | Access | Description |
|---|---|---|
| `/` | Public | Landing page |
| `/admin/login` | Public | Admin login form |
| `/admin` | Auth required | Redirects → `/admin/dashboard` |
| `/admin/dashboard` | Admin role required | Admin portal |

Unauthenticated access to `/admin/dashboard` redirects to `/admin/login`.  
After login the user is redirected back to the originally requested URL.

---

## API Endpoints

All endpoints are prefixed `/api/v1`.

### Authentication

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/login` | None | Login with email + password. Returns access token; sets httpOnly refresh cookie. Rate-limited. |
| `POST` | `/auth/refresh` | Refresh cookie | Exchange refresh cookie for new access token (token rotation). |
| `POST` | `/auth/logout` | Bearer | Revoke current session; clears cookie. |
| `GET` | `/auth/me` | Bearer | Return authenticated user profile. |

### Admin

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/admin/dashboard/stats` | Bearer (admin role) | Dashboard statistics. |

### System

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Health check. |

---

## Running Tests

Tests use a dedicated PostgreSQL schema (`test_equiconnected`) for isolation.  
Each test is wrapped in a transaction that is rolled back after the test.

```bash
cd backend
pytest tests/ -v
```

To run a specific class:

```bash
pytest tests/test_auth.py::TestLogin -v
```

### Test coverage

| # | Test scenario |
|---|---|
| 1 | Admin creation (fields, password hashing) |
| 2 | Successful login (token, cookie, no hash leak) |
| 3 | Invalid password (401, generic message) |
| 4 | Invalid / missing email / password (401, 422) |
| 5 | Inactive admin blocked (401) |
| 6 | Authentication persistence (token refresh) |
| 7 | Logout (revokes session, clears cookie) |
| 8 | Protected dashboard requires auth |
| 9 | Unauthorized access (no token, bad token) |
| 10 | Non-admin role rejected (403 Forbidden) |
| 11 | Duplicate admin prevention (unique constraint + idempotent seed) |
| 12 | Bootstrap verification and explicit password recovery (preservation + session revocation) |

---

## Authentication Architecture

### Token strategy

```
Browser                      FastAPI
  │                             │
  │── POST /auth/login ─────────▶│
  │◀─ { access_token } ─────────│  (body)
  │◀─ Set-Cookie: refresh_token ─│  (httpOnly, path=/api/v1/auth)
  │                             │
  │── GET /api/* ───────────────▶│  Authorization: Bearer <access_token>
  │                             │
  │   (access token expires)    │
  │── POST /auth/refresh ───────▶│  sends cookie automatically
  │◀─ { access_token (new) } ───│  (old refresh token revoked)
  │◀─ Set-Cookie: refresh_token ─│  (new token)
  │                             │
  │── POST /auth/logout ────────▶│
  │◀─ 200 OK ───────────────────│
  │◀─ Set-Cookie: (cleared) ────│
```

- **Access token** — short-lived JWT (15 min). In-memory only on the client; never `localStorage`.
- **Refresh token** — long-lived JWT (7 days). Stored hashed (SHA-256) in the database. Sent via `httpOnly` cookie scoped to `/api/v1/auth`. Never accessible from JavaScript.
- **Token rotation** — each `/auth/refresh` call revokes the old refresh token and issues a new pair.

### Password security

- Passwords are hashed with **Argon2id** using OWASP-recommended parameters:
  - `time_cost=3`, `memory_cost=65536` (64 MB), `parallelism=4`
- Passwords are **never** logged, stored in plaintext, returned via API, or sent to the frontend.
- Automatic rehash on login if Argon2 parameters have been upgraded.

### Role-based authorization

- Roles are stored in the `roles` table (not as strings).
- The `require_role("admin")` FastAPI dependency factory enforces role membership at the route level.
- Adding new roles (hospital_admin, visitor, etc.) requires no changes to the auth infrastructure.

### Rate limiting

- Login endpoint is rate-limited to **10 attempts per 5-minute window per IP**.
- Implemented as an in-memory sliding-window counter (resets on restart).
- Returns `HTTP 429` with `Retry-After` header on breach.
- For multi-process production deployments, replace with Redis-backed rate limiting.

### Brute-force resistance

- The login service always runs Argon2 verification even when the email is not found (constant-time dummy hash check) to prevent timing-based user enumeration.
- Login failure messages are generic: "Invalid email or password" — the same message for both unknown email and wrong password.

### Audit logging

- Successful and failed logins are recorded in `audit_logs`.
- Logout is recorded.
- Logs include IP address and User-Agent.
- The audit log is append-only; rows are never updated.

---

## Security Decisions

| Decision | Reason |
|---|---|
| Argon2id for password hashing | OWASP recommended; resistant to GPU/ASIC attacks |
| Refresh token stored as SHA-256 hash | Raw JWT never persisted; compromise of DB does not expose tokens |
| httpOnly cookie for refresh token | Prevents XSS from stealing the long-lived credential |
| Access token in body (not cookie) | Avoids CSRF on API endpoints; client stores in memory only |
| Generic login error messages | Prevents user enumeration |
| Constant-time dummy hash on unknown email | Prevents timing attacks for user enumeration |
| Role as FK not string column | Referential integrity; future roles don't require schema changes |
| Alembic for all schema changes | Reproducible, reviewable, reversible migrations |
| No public admin registration | Admin accounts are created only via the secure seed script |

---

## Phase 1 Scope

✅ Project structure  
✅ React 19 frontend + TypeScript  
✅ FastAPI backend  
✅ PostgreSQL + SQLAlchemy 2.x  
✅ Alembic migrations (roles, users, refresh_tokens, audit_logs)  
✅ EquiConnected design system (centralized CSS tokens)  
✅ Public website at `/`  
✅ Admin login at `/admin/login`  
✅ Protected admin dashboard at `/admin/dashboard`  
✅ Safe admin bootstrap verification with explicit credential recovery
✅ JWT authentication (access token + rotating refresh token)  
✅ Argon2id password hashing  
✅ Role-based access control foundation  
✅ Rate limiting on login  
✅ Full audit logging  
✅ Error / loading / empty states  
✅ Comprehensive authentication tests  

## Upcoming (Phase 2+)

- Hospital portal (`/hospital`)
- Hospital invitations
- Visitor portal (`/visitor`)
- Patient functionality
- Messaging, notifications, documents
