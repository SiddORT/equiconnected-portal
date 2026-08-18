# EquiConnected Portal

A next-generation healthcare coordination platform — secure, extensible, and built for production.

## Architecture

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Vite |
| Backend | Python 3 + FastAPI |
| Database | PostgreSQL + SQLAlchemy ORM |
| Migrations | Alembic |
| Auth | JWT (access + refresh) + Argon2id |

## Project Structure

```
/
├── frontend/          # React + TypeScript + Vite (port 5000)
│   └── src/
│       ├── app/       # Router, AuthContext, providers
│       ├── components/
│       │   ├── ui/    # Design system primitives
│       │   └── layout/# Header, Footer, Sidebar, etc.
│       ├── features/  # Feature modules (admin, ...)
│       ├── pages/     # Page components
│       ├── api/       # Axios client + typed API functions
│       ├── types/     # TypeScript types
│       └── styles/    # Design tokens + global CSS
│
└── backend/           # FastAPI (port 8000)
    ├── app/
    │   ├── api/v1/    # Route handlers
    │   ├── auth/      # JWT dependencies
    │   ├── core/      # Config, logging, security
    │   ├── db/        # Engine, session
    │   ├── models/    # SQLAlchemy models
    │   ├── repositories/ # Data access layer
    │   ├── schemas/   # Pydantic schemas
    │   └── services/  # Business logic
    ├── alembic/       # Database migrations
    ├── scripts/       # Seed scripts
    └── tests/         # pytest suites
```

## Environment Setup

Copy `.env.example` and fill in values — **never commit `.env`**.

Required secrets (set in Replit Secrets):
- `SECRET_KEY` — JWT signing key (generate: `python -c "import secrets; print(secrets.token_hex(64))"`)

Auto-provided by Replit (do not set manually):
- `DATABASE_URL` — PostgreSQL connection string

## Development

### Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm run dev
```

Vite proxies `/api` → `http://localhost:8000`.

## Database Migrations

```bash
cd backend

# Generate a migration after changing models
alembic revision --autogenerate -m "describe the change"

# Apply pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## Admin Setup

Run once to create the initial admin account:

```bash
cd backend
ADMIN_EMAIL=admin@yourdomain.com \
ADMIN_PASSWORD=YourStrongPassword \
python scripts/seed_admin.py
```

**Never hard-code credentials in source code.**

## Security Notes

- Passwords hashed with **Argon2id** (OWASP recommended parameters)
- Access tokens expire in **15 minutes**; refresh tokens in **7 days**
- Refresh tokens stored as **SHA-256 hashes** — never plaintext
- Refresh token rotation: each use invalidates the old token
- httpOnly cookie for refresh token — not accessible via JavaScript
- Full audit log for admin login, logout, and future actions

## Phase 1 Scope

✅ Project structure  
✅ React frontend + TypeScript  
✅ FastAPI backend  
✅ PostgreSQL + SQLAlchemy  
✅ Alembic migrations  
✅ Design system (centralized tokens)  
✅ Public website at `/`  
✅ Admin login at `/admin/login`  
✅ Protected admin dashboard at `/admin/dashboard`  
✅ Secure admin seed mechanism  
✅ JWT authentication (access + refresh tokens)  
✅ Role-based access control foundation  
✅ Error / loading / empty states  
✅ Audit logging  
✅ Basic tests  

## Upcoming (Phase 2+)

- Hospital portal (`/hospital`)
- Hospital invitations
- Visitor portal (`/visitor`)
- Patient functionality
- Messaging, notifications, documents
