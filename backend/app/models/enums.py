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


class DoctorAvailability(str, enum.Enum):
    ONGOING = "ONGOING"
    VISITING = "VISITING"


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


class ProviderReviewStatus(str, enum.Enum):
    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"
    HIDDEN = "HIDDEN"


class MemberFeedbackStatus(str, enum.Enum):
    PENDING = "Pending"
    IN_REVIEW = "In review"
    RESOLVED = "Resolved"
    REJECTED = "Rejected"


class MemberFeedbackCategory(str, enum.Enum):
    WEBSITE_APP = "Website / App"
    SEARCH_MATCHING = "Search & Matching"
    PROVIDER_EXPERIENCE = "Provider Experience"
    ACCOUNT_PROFILE = "Account / Profile"
    TECHNICAL_ISSUE = "Technical Issue"
    SUGGESTION = "Suggestion"
    OTHER = "Other"


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
    PROVIDER_PORTAL_RECOVERY = "provider_portal_recovery"
    MEMBER_PASSWORD_RECOVERY = "member_password_recovery"
    PROVIDER_APPROVAL = "provider_approval"
    SUBSCRIBER_CONFIRMATION = "subscriber_confirmation"
    CONTACT_NOTIFICATION = "contact_notification"
    CONTACT_CONFIRMATION = "contact_confirmation"
    SMTP_TEST = "smtp_test"
    MESSAGING_MEMBER_ACKNOWLEDGEMENT = "messaging_member_acknowledgement"
    MESSAGING_PROVIDER_NEW_MESSAGE = "messaging_provider_new_message"
    MESSAGING_MEMBER_REPLY = "messaging_member_reply"


class ContactEnquiryType(str, enum.Enum):
    GENERAL = "general"
    LISTING = "listing"
    PARTNERSHIP = "partnership"
    OTHER = "other"


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
