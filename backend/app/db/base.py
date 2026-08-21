"""
Alembic aggregator — imports all models so autogenerate picks them up.
Do NOT import this file from application code. Models and sessions
should import from app.db.base_class and app.db.session respectively.
"""
from app.db.base_class import Base  # noqa: F401

# Register all models for Alembic autogenerate
from app.models.role import Role  # noqa: F401, E402
from app.models.user import EmailVerificationToken, User, UserRole  # noqa: F401, E402
from app.models.refresh_token import RefreshToken  # noqa: F401, E402
from app.models.audit_log import AuditLog  # noqa: F401, E402
from app.models.specialization import Specialization  # noqa: F401, E402
from app.models.provider import (  # noqa: F401, E402
    Provider,
    ProviderEmail,
    ProviderLocation,
    ProviderPhone,
    ProviderPhoto,
    ProviderSpecialization,
)
from app.models.doctor import DoctorOrganization, DoctorProfile, DoctorQualification  # noqa: F401, E402
from app.models.invitation import ProviderInvitation  # noqa: F401, E402
from app.models.organization_request import OrganizationRequest  # noqa: F401, E402
from app.models.public_visit import PublicVisitDaily  # noqa: F401, E402
