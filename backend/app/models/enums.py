"""
Shared enums for Provider domain models.
Stored as PostgreSQL-native enums (native_enum=True) so the DB enforces values.
"""
import enum


class ProviderType(str, enum.Enum):
    HOSPITAL = "HOSPITAL"
    CLINIC = "CLINIC"
    DOCTOR = "DOCTOR"


class VisitStability(str, enum.Enum):
    STABLE_VISIT = "STABLE_VISIT"
    NOT_STABLE_VISIT = "NOT_STABLE_VISIT"


class ProviderStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class PublicationStatus(str, enum.Enum):
    UNPUBLISHED = "UNPUBLISHED"
    PUBLISHED = "PUBLISHED"


class DoctorOrganizationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
