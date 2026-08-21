# EquiConnected Portal

Admin portal for the EquiConnected equestrian healthcare platform.

## Architecture

- **Frontend**: React 19 + Vite (port 5000) — TypeScript, CSS Modules, EquiConnected design system
- **Backend**: FastAPI + Python 3.13 (port 8000) — SQLAlchemy 2.x, Alembic, Argon2id auth
- **Database**: PostgreSQL — schema `equiconnected` (dev), `test_equiconnected` (tests)

## Running the app

Workflows are configured and start automatically:
- `Frontend` — `cd frontend && npm run dev`
- `Backend API` — `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

## Database migrations

```bash
cd backend
alembic upgrade head                                       # apply pending migrations
alembic revision --autogenerate -m "description"           # generate new migration after model change
```

## Running tests

```bash
cd backend
python -m pytest tests/ -v                                 # all tests
python -m pytest tests/test_auth.py -v                    # auth suite (36 tests)
python -m pytest tests/test_specializations.py -v         # specializations suite (38 tests)
```

## Seeding admin

```bash
cd backend
# ADMIN_EMAIL and ADMIN_PASSWORD must be set as Replit Secrets
python scripts/seed_admin.py
```

The normal command is non-destructive: it creates a missing account or verifies
an existing one, reporting a credential mismatch without changing the password,
role, or active state. It exits `2` when operator attention is needed.

For an intentional recovery after confirming the target database, run:

```bash
ADMIN_RECOVERY_CONFIRM=RESET_BOOTSTRAP_PASSWORD python scripts/seed_admin.py
```

This rotates only the existing active administrator's password and revokes that
account's refresh sessions. Never configure the recovery confirmation in
automated deployment or post-merge environments; changing `ADMIN_PASSWORD`
alone never resets an existing account.

## Resetting non-admin accounts

This is a destructive, operator-only maintenance action against the database
selected by `DATABASE_URL`. It is preview-first and must never be added to
deployment, startup, or demo-seeding automation.

```bash
cd backend

# Preview only — lists retained administrators, targeted users, and dependent records.
python scripts/reset_non_admin_users.py

# Re-check the current scope transactionally, then delete the targeted accounts.
python scripts/reset_non_admin_users.py --confirm DELETE_NON_ADMIN_USERS
```

The command preserves every account with the `admin` role, whether that role is
the account's primary role or a relational role assignment. It refuses the
confirmed run if no active administrator would remain. It removes every other
user and their database-cascaded sessions, role assignments, verification
tokens, stable profiles, horses, and provider reviews. Audit history remains,
with references to deleted users cleared. Providers, locations, specializations,
roles, and other master data are not removed.

The reset also stops before making changes if a targeted user created provider
invitations, because that reference is intentionally restrictive. Resolve those
invitation records first, rerun the preview, and only then repeat the confirmed
command. The confirmed command locks the user, role, and invitation boundary
while it re-checks its scope, so treat the preview as an audit aid rather than a
guarantee that a changing database will have the identical account list at
confirmation time. After a successful reset, sign in with a retained active administrator.
If that administrator needs credential recovery, use the explicitly guarded
bootstrap recovery command documented above.

## Seeding demo data (development)

```bash
cd backend
python scripts/seed_demo_data.py   # rerunnable; creates fictional, geocoded Dubai hospitals, clinics, and doctors
```

## API routes

| Prefix | Description |
|---|---|
| `POST /api/v1/auth/login` | Admin login |
| `POST /api/v1/auth/refresh` | Rotate access token using httpOnly cookie |
| `POST /api/v1/auth/logout` | Revoke refresh token |
| `GET  /api/v1/auth/me` | Current user profile |
| `GET  /api/v1/admin/dashboard/stats` | Dashboard stats: user total, provider counts, map markers, and analytics |
| `GET  /api/v1/admin/activity-logs` | Paginated, date-filtered administrator activity history |
| `GET/POST /api/v1/admin/specializations` | List / create specializations |
| `GET/PATCH /api/v1/admin/specializations/{id}` | Get / update specialization |
| `PATCH /api/v1/admin/specializations/{id}/status` | Activate / deactivate |

## Key conventions

- All admin endpoints require `Authorization: Bearer <access_token>` + `role=admin`
- Refresh token is an httpOnly cookie (`Path=/api/v1/auth`)
- Passwords hashed with Argon2id; access tokens are short-lived JWTs (15 min)
- Specialization names are case-insensitively unique at the DB level (unique constraint)
- Deactivating a specialization sets `is_active=false` — records are never deleted

## Phases completed

- **Phase 1** — Admin authentication (login, refresh, logout, JWT, Argon2id, audit log)
- **Phase 2** — Dashboard + top navigation
- **Phase 3** — Specializations master-data CRUD (list, create, edit, activate/deactivate, search, filter, pagination)

## User preferences

- No hardcoded/fake data — database is always the source of truth
- Backend validation is mandatory; frontend validation is UX only
- Deactivation over deletion for master data
