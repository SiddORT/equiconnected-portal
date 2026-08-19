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
python -m pytest tests/test_auth.py -v                    # auth suite (32 tests)
python -m pytest tests/test_specializations.py -v         # specializations suite (38 tests)
```

## Seeding admin

```bash
cd backend
# ADMIN_EMAIL and ADMIN_PASSWORD must be set as Replit Secrets
python scripts/seed_admin.py
```

## Seeding demo data (development)

```bash
cd backend
python scripts/seed_demo_data.py   # rerunnable; creates specializations + geocoded hospitals/clinics/doctors
```

## API routes

| Prefix | Description |
|---|---|
| `POST /api/v1/auth/login` | Admin login |
| `POST /api/v1/auth/refresh` | Rotate access token using httpOnly cookie |
| `POST /api/v1/auth/logout` | Revoke refresh token |
| `GET  /api/v1/auth/me` | Current user profile |
| `GET  /api/v1/admin/dashboard/stats` | Dashboard stats: user total, provider counts, map markers, audit |
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
