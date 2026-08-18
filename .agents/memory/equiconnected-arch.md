---
name: EquiConnected Portal architecture
description: Key decisions, conventions, and pitfalls for the EquiConnected Portal project.
---

# EquiConnected Portal — Architecture Notes

## Critical: Circular Import Pattern
SQLAlchemy models must import `Base` from `app.db.base_class`, NOT `app.db.base`.
`app.db.base` is the Alembic-only aggregator (imports all models) — importing it from models causes circular imports.
**How to apply:** Any new model file: `from app.db.base_class import Base`

## Login Flow — Token Issuance
`AuthService.login()` returns a `LoginResult` dataclass containing both `access_token` and `refresh_token`.
The endpoint must NOT call `_issue_token_pair` again — doing so causes a unique constraint violation
(same-second JWT → same SHA-256 hash stored twice).
**Why:** JWT `iat` granularity is seconds; within the same second the hash is identical.

## ALLOWED_ORIGINS Env Var
Must be stored as a JSON array string for pydantic-settings list parsing:
`["http://localhost:5000","http://127.0.0.1:5000"]`
A comma-separated string causes a SettingsError.

## SQLAlchemy Reserved Attribute
The column name `metadata` is reserved by SQLAlchemy's DeclarativeBase.
`AuditLog` uses `event_metadata` as the Python attr with `mapped_column("metadata", ...)` for the DB column name.

## Seed Script
`backend/scripts/seed_admin.py` must import `app.db.base` (the aggregator) before any repositories
to ensure all models are registered in SQLAlchemy's mapper registry before relationship resolution.

## Auth Architecture
- Access token: JWT, 15 min, returned in response body
- Refresh token: JWT, 7 days, stored as SHA-256 hash in `refresh_tokens` table, sent as httpOnly cookie on path `/api/v1/auth`
- On 401, Axios interceptor calls `/auth/refresh` once and retries — deduplicates concurrent refresh calls
- `AuthContext` tries refresh on mount to restore sessions; 401 on mount is normal (no cookie = not logged in)

## RBAC
Roles are seeded (not hardcoded). New roles added via `UserRepository.create_role()`.
Admin dependency: `Depends(require_role("admin"))`. Future roles: `hospital_admin`, `visitor`.

## Frontend Path Aliases
`@/` maps to `src/` via `vite.config.ts` + `tsconfig.json` paths. All imports should use `@/`.

## Alembic
Initial migration file exists at `backend/alembic/versions/c4c2e0b50e3d_initial_schema.py`.
Tables were also created directly via `Base.metadata.create_all()` for development convenience.
Future schema changes: `alembic revision --autogenerate -m "description"` then `alembic upgrade head`.
