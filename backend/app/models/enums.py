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
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class PublicationStatus(str, enum.Enum):
    UNPUBLISHED = "UNPUBLISHED"
    PUBLISHED = "PUBLISHED"


class ProviderApplicationStatus(str, enum.Enum):
    AWAITING_EMAIL_VERIFICATION = "AWAITING_EMAIL_VERIFICATION"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ProviderProfileUpdateStatus(str, enum.Enum):
    """Review lifecycle for a provider-owned edit to a published listing."""

    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DoctorOrganizationStatus(str, enum.Enum):
    PENDING = "PENDING"
    REJECTED = "REJECTED"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class InvitationStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class OrganizationRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class EmailPurpose(str, enum.Enum):
    PROVIDER_INVITATION = "provider_invitation"
    ACCOUNT_VERIFICATION = "account_verification"
    PROVIDER_PORTAL_ACCESS = "provider_portal_access"
    SUBSCRIBER_CONFIRMATION = "subscriber_confirmation"


class EmailDeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class SubscriberRegistrationType(str, enum.Enum):
    VET = "VET"
    HORSE_OWNER = "HORSE_OWNER"
    HOSPITAL = "HOSPITAL"
    CLINIC = "CLINIC"
    STABLE_MANAGER = "STABLE_MANAGER"
    OTHER = "OTHER"