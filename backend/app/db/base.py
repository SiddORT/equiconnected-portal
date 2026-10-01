"""
Alembic aggregator — imports all models so autogenerate picks them up.
Do NOT import this file from application code. Models and sessions
should import from app.db.base_class and app.db.session respectively.
"""
from app.db.base_class import Base  # noqa: F401
from app.models.postal_lookup_rate_limit import PostalLookupRateLimit  # noqa: F401, E402

# Register all models for Alembic autogenerate
from app.models.role import Role  # noqa: F401, E402
from app.models.user import EmailVerificationToken, User, UserRole  # noqa: F401, E402
from app.models.profile import Horse, StableProfile  # noqa: F401, E402
from app.models.refresh_token import RefreshToken  # noqa: F401, E402
from app.models.audit_log import AuditLog  # noqa: F401, E402
from app.models.email_delivery_log import EmailDeliveryLog  # noqa: F401, E402
from app.models.specialization import Specialization  # noqa: F401, E402
from app.models.provider import (  # noqa: F401, E402
    Provider,
    DirectProviderPortalAccess,
    DoctorVisit,
    ProviderEmail,
    ProviderLocation,
    ProviderPhone,
    ProviderPhoto,
    ProviderProfileUpdate,
    ProviderReview,
    ProviderSpecialization,
)
from app.models.provider_review_action import ProviderReviewAction  # noqa: F401, E402
from app.models.member_feedback import MemberFeedback, MemberFeedbackAction  # noqa: F401, E402
from app.models.member_history import MemberBrowsingHistory  # noqa: F401, E402
from app.models.provider_registration import ProviderRegistrationApplication  # noqa: F401, E402
from app.models.doctor import DoctorOrganization, DoctorProfile, DoctorQualification  # noqa: F401, E402
from app.models.invitation import ProviderInvitation, ProviderPortalSetupToken  # noqa: F401, E402
from app.models.organization_request import OrganizationRequest  # noqa: F401, E402
from app.models.public_visit import PublicVisitDaily  # noqa: F401, E402
from app.models.provider_favorite import ProviderFavorite  # noqa: F401, E402
from app.models.subscriber import Subscriber  # noqa: F401, E402
from app.models.contact_enquiry import ContactEnquiry  # noqa: F401, E402
from app.models.system_settings import SystemSettings  # noqa: F401, E402
from app.models.language import Language, ProviderLanguage, ProviderRegistrationLanguage  # noqa: F401, E402
from app.models.analytics_traffic import (  # noqa: F401, E402
    TrafficPageCategoryDaily,
    TrafficProviderProfileDaily,
    TrafficTrackingMetadata,
    TrafficTrackingReceipt,
    TrafficVisitorDaily,
)
