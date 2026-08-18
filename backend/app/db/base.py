"""
Alembic aggregator — imports all models so autogenerate picks them up.
Do NOT import this file from application code. Models and sessions
should import from app.db.base_class and app.db.session respectively.
"""
from app.db.base_class import Base  # noqa: F401

# Register all models for Alembic autogenerate
from app.models.role import Role  # noqa: F401, E402
from app.models.user import User  # noqa: F401, E402
from app.models.refresh_token import RefreshToken  # noqa: F401, E402
from app.models.audit_log import AuditLog  # noqa: F401, E402
from app.models.specialization import Specialization  # noqa: F401, E402
from app.models.provider import (  # noqa: F401, E402
    Provider,
    ProviderLocation,
    ProviderPhoto,
    ProviderSpecialization,
)
