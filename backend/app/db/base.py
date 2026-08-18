"""
SQLAlchemy declarative base.
Import all models here so Alembic autogenerate picks them up.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Alembic autogenerate imports — add new models here as they are created
from app.models.role import Role  # noqa: F401, E402
from app.models.user import User  # noqa: F401, E402
from app.models.refresh_token import RefreshToken  # noqa: F401, E402
from app.models.audit_log import AuditLog  # noqa: F401, E402
