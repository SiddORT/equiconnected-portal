"""Business rules for secure provider invitations.

The _emit_event seam intentionally centralizes future audit-log integration.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.models.enums import InvitationStatus, ProviderStatus, ProviderType, PublicationStatus
from app.models.doctor import DoctorProfile, DoctorQualification
from app.models.invitation import ProviderInvitation
from app.models.provider import (
    ProviderEmail,
    ProviderLocation,
    ProviderPhone,
    ProviderPhoto,
    ProviderSpecialization,
)
from app.repositories.invitation_repository import InvitationRepository
from app.repositories.provider_repository import ProviderRepository
from app.repositories.audit_repository import AuditContext, AuditRepository
from app.repositories.email_delivery_repository import (
    EmailDeliveryRepository,
    safe_failure_message,
)
from app.services.email_service import EmailService
from app.models.enums import EmailDeliveryStatus, EmailPurpose
from app.services.provider_service import ProviderNotFoundError


class InvitationError(Exception):
    """Base invitation domain exception."""


class InvitationNotFoundError(InvitationError):
    pass


class InvitationExpiredError(InvitationError):
    pass


class InvitationCompletedError(InvitationError):
    pass


class InvitationCancelledError(InvitationError):
    pass


class DuplicateInvitationError(InvitationError):
    pass


class InvalidInvitationStateError(InvitationError):
    pass


class ProviderTypeMismatchError(InvitationError):
    pass


class InvalidProviderDataError(InvitationError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InvitationService:
    def __init__(self, repo: InvitationRepository, provider_repo: ProviderRepository, email: EmailService | None = None) -> None:
        self._repo, self._providers, self._email = repo, provider_repo, email or EmailService()
        self._audit = AuditRepository(repo._db)
        self._email_logs = EmailDeliveryRepository(repo._db)

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _new_token() -> str:
        return secrets.token_urlsafe(48)

    def _emit_event(
        self,
        event: str,
        invitation: ProviderInvitation,
        *,
        context: AuditContext | None = None,
        summary: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Record a safe invitation event; raw tokens and URLs never enter metadata."""
        labels = {
            "provider_invitation.created": "Created a provider invitation.",
            "provider_invitation.resent": "Resent a provider invitation.",
            "provider_invitation.delivered": "Delivered a provider invitation email.",
            "provider_invitation.delivery_failed": "Provider invitation email delivery failed.",
            "provider_invitation.cancelled": "Cancelled a provider invitation.",
            "provider_invitation.accepted": "Opened and accepted a provider invitation.",
            "provider_invitation.expired": "Provider invitation expired.",
            "provider_invitation.draft_saved": "Saved an invitation draft.",
            "provider_invitation.submitted": "Submitted an invitation response.",
            "provider_invitation.viewed": "Viewed a provider invitation.",
            "provider_invitation.list_viewed": "Viewed provider invitations.",
        }
        self._audit.record(
            event,
            context=context or AuditContext(actor_type="public_invitation"),
            resource_type="provider_invitation",
            resource_id=str(invitation.id),
            summary=summary or labels.get(event, event.replace("_", " ").replace(".", " ").title()),
            metadata={
                "provider_id": str(invitation.provider_id) if invitation.provider_id else None,
                "provider_type": invitation.provider_type.value,
                "status": invitation.status.value,
                **(metadata or {}),
            },
        )

    def _url(self, token: str) -> str:
        return f"{get_settings().PUBLIC_APP_URL.rstrip('/')}/provider/invitations/{token}"

    @staticmethod
    def _expires_at(sent_at: datetime) -> datetime:
        return sent_at + timedelta(days=get_settings().INVITATION_EXPIRE_DAYS)

    def _expire_due(self) -> None:
        expired = self._repo.expire_due()
        for invitation in expired:
            self._emit_event(
                "provider_invitation.expired",
                invitation,
                context=AuditContext(actor_type="system"),
            )
        self._repo.commit()

    def create_invitation(
        self, *, fields: dict, created_by: UUID, audit_context: AuditContext | None = None
    ) -> ProviderInvitation:
        self._expire_due()
        recipient = str(fields["recipient_email"]).strip().lower()
        provider_id = fields.get("provider_id")
        if not provider_id:
            self._repo.lock_new_provider_invitation(
                fields["provider_type"], recipient
            )
            if self._repo.has_active_for_new_provider(
                fields["provider_type"], recipient
            ):
                self._repo.rollback()
                raise DuplicateInvitationError(
                    "An active invitation already exists for this provider type and email."
                )
        if provider_id:
            provider = self._providers.get_by_id(provider_id)
            if not provider:
                raise ProviderNotFoundError(str(provider_id))
            if provider.provider_type != fields["provider_type"]:
                raise ProviderTypeMismatchError("Provider type does not match the selected provider.")
        else:
            provider = self._providers.create(
                provider_type=fields["provider_type"], name=fields.get("provider_name") or recipient,
                visit_stability=fields["visit_stability"], status=ProviderStatus.DRAFT,
                publication_status=PublicationStatus.UNPUBLISHED, email=recipient,
            )
        if self._repo.has_active_for_provider_email(provider.id, recipient):
            self._repo.rollback()
            raise DuplicateInvitationError("An active invitation already exists for this provider and email.")
        token, sent_at = self._new_token(), _now()
        try:
            invitation = self._repo.create(
                provider_id=provider.id,
                provider_type=fields["provider_type"],
                recipient_email=recipient,
                token_hash=self._hash(token),
                status=InvitationStatus.PENDING,
                expires_at=self._expires_at(sent_at),
                sent_at=sent_at,
                created_by=created_by,
            )
            self._emit_event("provider_invitation.created", invitation, context=audit_context)
            self._repo.commit()
        except IntegrityError as exc:
            self._repo.rollback()
            raise DuplicateInvitationError(
                "An active invitation already exists for this provider and email."
            ) from exc
        except Exception:
            self._repo.rollback()
            raise
        attempt_id = self._email_logs.record_durable_attempt(
            recipient_email=recipient,
            purpose=EmailPurpose.PROVIDER_INVITATION,
        )
        try:
            self._email.send_invitation_email(
                recipient,
                invitation.provider_type,
                self._url(token),
                invitation.expires_at,
            )
        except Exception as exc:
            # The committed PENDING record is deliberately retained so the
            # administrator sees the error and can retry with resend.
            self._emit_event("provider_invitation.delivery_failed", invitation, context=audit_context)
            self._email_logs.complete_durable_attempt(
                attempt_id,
                status=EmailDeliveryStatus.FAILED,
                failure_message=safe_failure_message(exc),
            )
            self._repo.commit()
            raise
        self._email_logs.complete_durable_attempt(
            attempt_id,
            status=EmailDeliveryStatus.SUCCESS,
        )
        self._emit_event("provider_invitation.delivered", invitation, context=audit_context)
        self._repo.commit()
        # Transient, non-persisted convenience for the admin UI: the raw link
        # is only known here, immediately after generation.
        invitation.invitation_url = self._url(token)
        return invitation

    def list(self, **filters) -> tuple[list[ProviderInvitation], int]:
        self._expire_due()
        return self._repo.list(**filters)

    def resend_invitation(
        self, invitation_id: UUID, *, audit_context: AuditContext | None = None
    ) -> ProviderInvitation:
        invitation = self._require_id(invitation_id)
        self._refresh_expiry(invitation)
        if invitation.status not in (InvitationStatus.PENDING, InvitationStatus.EXPIRED):
            raise InvalidInvitationStateError("Only pending or expired invitations can be resent.")
        if self._repo.has_active_for_provider_email(
            invitation.provider_id,
            invitation.recipient_email,
            except_id=invitation.id,
        ):
            raise DuplicateInvitationError(
                "Another active invitation already exists for this provider and email."
            )
        token, sent_at = self._new_token(), _now()
        invitation.token_hash, invitation.status = self._hash(token), InvitationStatus.PENDING
        invitation.expires_at, invitation.sent_at, invitation.accepted_at = self._expires_at(sent_at), sent_at, None
        try:
            self._emit_event("provider_invitation.resent", invitation, context=audit_context)
            self._repo.commit()
        except Exception:
            self._repo.rollback()
            raise
        attempt_id = self._email_logs.record_durable_attempt(
            recipient_email=invitation.recipient_email,
            purpose=EmailPurpose.PROVIDER_INVITATION,
        )
        try:
            self._email.send_invitation_email(
                invitation.recipient_email,
                invitation.provider_type,
                self._url(token),
                invitation.expires_at,
            )
        except Exception as exc:
            self._emit_event("provider_invitation.delivery_failed", invitation, context=audit_context)
            self._email_logs.complete_durable_attempt(
                attempt_id,
                status=EmailDeliveryStatus.FAILED,
                failure_message=safe_failure_message(exc),
            )
            self._repo.commit()
            raise
        self._email_logs.complete_durable_attempt(
            attempt_id,
            status=EmailDeliveryStatus.SUCCESS,
        )
        self._emit_event("provider_invitation.delivered", invitation, context=audit_context)
        self._repo.commit()
        # Transient, non-persisted convenience for the admin UI (see create).
        invitation.invitation_url = self._url(token)
        return invitation

    def cancel_invitation(
        self, invitation_id: UUID, *, audit_context: AuditContext | None = None
    ) -> ProviderInvitation:
        invitation = self._require_id(invitation_id)
        self._refresh_expiry(invitation)
        if invitation.status in (InvitationStatus.CANCELLED, InvitationStatus.COMPLETED):
            raise InvalidInvitationStateError("This invitation can no longer be cancelled.")
        invitation.status = InvitationStatus.CANCELLED
        self._emit_event("provider_invitation.cancelled", invitation, context=audit_context)
        self._repo.commit()
        return invitation

    def _require_id(self, invitation_id: UUID) -> ProviderInvitation:
        invitation = self._repo.get_by_id(invitation_id)
        if not invitation:
            raise InvitationNotFoundError()
        return invitation

    def _refresh_expiry(self, invitation: ProviderInvitation) -> None:
        if invitation.status in (InvitationStatus.PENDING, InvitationStatus.ACCEPTED) and invitation.expires_at <= _now():
            invitation.status = InvitationStatus.EXPIRED

    def validate_token(self, token: str, *, accept: bool = True) -> ProviderInvitation:
        invitation = self._repo.get_by_token_hash(self._hash(token))
        if not invitation:
            raise InvitationNotFoundError()
        self._refresh_expiry(invitation)
        if invitation.status == InvitationStatus.EXPIRED:
            self._emit_event(
                "provider_invitation.expired",
                invitation,
                context=AuditContext(actor_type="system"),
            )
            self._repo.commit()
            raise InvitationExpiredError()
        if invitation.status == InvitationStatus.COMPLETED:
            raise InvitationCompletedError()
        if invitation.status == InvitationStatus.CANCELLED:
            raise InvitationCancelledError()
        if accept and invitation.status == InvitationStatus.PENDING:
            invitation.status, invitation.accepted_at = InvitationStatus.ACCEPTED, _now()
            self._emit_event("provider_invitation.accepted", invitation)
            self._repo.commit()
        return invitation

    def _apply_provider_fields(
        self, invitation: ProviderInvitation, fields: dict
    ):
        provider = self._providers.get_by_id(invitation.provider_id)
        if not provider:
            raise InvitationNotFoundError()
        collection_fields = {
            "specialization_ids",
            "locations",
            "phones",
            "emails",
            "photos",
            "qualifications",
        }
        profile_fields = {
            "professional_title",
            "biography",
            "years_experience",
            "experience_description",
        }
        doctor_data = profile_fields.intersection(fields) | (
            {"qualifications"} if "qualifications" in fields else set()
        )
        if doctor_data and provider.provider_type != ProviderType.DOCTOR:
            raise InvalidProviderDataError(
                "Doctor-specific fields can only be saved for Doctor invitations."
            )
        for required_field in ("name", "visit_stability"):
            if required_field in fields and fields[required_field] is None:
                raise InvalidProviderDataError(
                    f"{required_field.replace('_', ' ').title()} cannot be empty."
                )

        specialization_ids = fields.get("specialization_ids")
        if specialization_ids is not None:
            specialization_ids = list(dict.fromkeys(specialization_ids))
            for specialization_id in specialization_ids:
                specialization = self._providers.get_specialization(specialization_id)
                if specialization is None or not specialization.is_active:
                    raise InvalidProviderDataError(
                        f"Specialization not found or inactive: {specialization_id}"
                    )

        for field_name, unique_flag in (
            ("locations", "is_primary"),
            ("phones", "is_primary"),
            ("emails", "is_primary"),
            ("photos", "is_thumbnail"),
        ):
            records = fields.get(field_name)
            if records is not None and sum(
                bool(record.get(unique_flag)) for record in records
            ) > 1:
                raise InvalidProviderDataError(
                    f"Only one {field_name.rstrip('s')} may be marked as {unique_flag}."
                )

        for name, value in fields.items():
            if name in collection_fields or name in profile_fields:
                continue
            if isinstance(value, Enum):
                value = value.value
            elif isinstance(value, str):
                value = value.strip()
            setattr(provider, name, value)

        if specialization_ids is not None:
            provider.provider_specializations.clear()
            self._providers.flush()
            provider.provider_specializations = [
                ProviderSpecialization(
                    provider_id=provider.id, specialization_id=specialization_id
                )
                for specialization_id in specialization_ids
            ]
        for field_name, model, relationship_name in (
            ("locations", ProviderLocation, "locations"),
            ("phones", ProviderPhone, "phones"),
            ("emails", ProviderEmail, "emails"),
            ("photos", ProviderPhoto, "photos"),
        ):
            records = fields.get(field_name)
            if records is not None:
                relationship = getattr(provider, relationship_name)
                relationship.clear()
                self._providers.flush()
                relationship.extend(
                    model(provider_id=provider.id, **record) for record in records
                )

        if provider.provider_type == ProviderType.DOCTOR:
            supplied_profile = {key: fields[key] for key in profile_fields if key in fields}
            if supplied_profile:
                if provider.doctor_profile is None:
                    provider.doctor_profile = DoctorProfile(
                        provider_id=provider.id, **supplied_profile
                    )
                else:
                    for key, value in supplied_profile.items():
                        setattr(provider.doctor_profile, key, value)
            qualifications = fields.get("qualifications")
            if qualifications is not None:
                provider.qualifications.clear()
                self._providers.flush()
                provider.qualifications.extend(
                    DoctorQualification(provider_id=provider.id, **record)
                    for record in qualifications
                )
        return provider

    def save_draft(self, token: str, fields: dict) -> ProviderInvitation:
        invitation = self.validate_token(token)
        provider = self._apply_provider_fields(invitation, fields)
        provider.status, provider.publication_status = ProviderStatus.DRAFT, PublicationStatus.UNPUBLISHED
        self._emit_event(
            "provider_invitation.draft_saved",
            invitation,
            metadata={"updated_fields": sorted(fields.keys())},
        )
        self._repo.commit()
        return invitation

    def token_payload(self, invitation: ProviderInvitation) -> dict:
        provider = self._providers.get_by_id(invitation.provider_id)
        if not provider:
            raise InvitationNotFoundError()
        return {
            "id": invitation.id,
            "provider_type": invitation.provider_type,
            "provider": {
                "name": provider.name,
                "description": provider.description,
                "email": provider.email,
                "phone": provider.phone,
                "website": provider.website,
                "visit_stability": provider.visit_stability.value,
                "status": provider.status.value,
                "specialization_ids": [
                    str(link.specialization_id)
                    for link in provider.provider_specializations
                ],
                "locations": [
                    {
                        "name": location.name,
                        "address_line_1": location.address_line_1,
                        "address_line_2": location.address_line_2,
                        "city": location.city,
                        "state_province": location.state_province,
                        "country": location.country,
                        "postal_code": location.postal_code,
                        "latitude": location.latitude,
                        "longitude": location.longitude,
                        "is_primary": location.is_primary,
                    }
                    for location in provider.locations
                ],
                "phones": [
                    {
                        "country_code": phone.country_code,
                        "number": phone.number,
                        "is_primary": phone.is_primary,
                    }
                    for phone in provider.phones
                ],
                "emails": [
                    {"email": email.email, "is_primary": email.is_primary}
                    for email in provider.emails
                ],
                "photos": [
                    {
                        "storage_reference": photo.storage_reference,
                        "alt_text": photo.alt_text,
                        "caption": photo.caption,
                        "display_order": photo.display_order,
                        "is_thumbnail": photo.is_thumbnail,
                    }
                    for photo in provider.photos
                ],
                **(
                    {
                        "professional_title": (
                            provider.doctor_profile.professional_title
                            if provider.doctor_profile
                            else None
                        ),
                        "biography": (
                            provider.doctor_profile.biography
                            if provider.doctor_profile
                            else None
                        ),
                        "years_experience": (
                            provider.doctor_profile.years_experience
                            if provider.doctor_profile
                            else None
                        ),
                        "experience_description": (
                            provider.doctor_profile.experience_description
                            if provider.doctor_profile
                            else None
                        ),
                        "qualifications": [
                            {
                                "title": qualification.title,
                                "institution": qualification.institution,
                                "year_obtained": qualification.year_obtained,
                                "description": qualification.description,
                                "display_order": qualification.display_order,
                            }
                            for qualification in provider.qualifications
                        ],
                    }
                    if provider.provider_type == ProviderType.DOCTOR
                    else {}
                ),
            },
        }

    def submit_invitation(self, token: str, fields: dict) -> ProviderInvitation:
        invitation = self.validate_token(token)
        fields = dict(fields)
        organization_ids = fields.pop("organization_ids", None)
        provider = self._apply_provider_fields(invitation, fields)
        if not provider or not provider.name.strip() or not provider.visit_stability:
            raise InvalidInvitationStateError("Provider name and visit stability are required.")
        if organization_ids is not None:
            self._reconcile_organizations(invitation, organization_ids)
        provider.status, provider.publication_status = ProviderStatus.UNDER_REVIEW, PublicationStatus.UNPUBLISHED
        invitation.status, invitation.completed_at = InvitationStatus.COMPLETED, _now()
        self._emit_event(
            "provider_invitation.submitted",
            invitation,
            metadata={"updated_fields": sorted(fields.keys())},
        )
        self._repo.commit()
        return invitation

    def record_view(self, invitation: ProviderInvitation) -> None:
        self._emit_event("provider_invitation.viewed", invitation)
        self._repo.commit()

    def record_list_view(self, *, context: AuditContext) -> None:
        self._audit.record(
            "provider_invitation.list_viewed",
            context=context,
            resource_type="provider_invitation",
            summary="Viewed provider invitations.",
        )
        self._repo.commit()

    def _reconcile_organizations(self, invitation: ProviderInvitation, organization_ids: list) -> None:
        """Sync the doctor's PENDING organization relationships to `organization_ids`.

        Runs in the submit transaction (flush only, no commit) so a failed
        submit leaves no stray relationships behind. Non-PENDING relationships
        (e.g. admin-approved) are never touched.
        """
        from app.models.doctor import DoctorOrganization
        from app.models.enums import DoctorOrganizationStatus
        from app.models.provider import Provider

        if invitation.provider_type != ProviderType.DOCTOR:
            raise InvalidProviderDataError("Organization associations require a Doctor invitation.")
        db = self._repo._db  # same session as the rest of the submit
        wanted = list(dict.fromkeys(UUID(str(oid)) for oid in organization_ids))
        existing = (
            db.query(DoctorOrganization)
            .filter(DoctorOrganization.doctor_id == invitation.provider_id)
            .all()
        )
        existing_by_org = {rel.organization_id: rel for rel in existing}
        for organization_id in wanted:
            if organization_id in existing_by_org:
                continue
            target = db.get(Provider, organization_id)
            if not target or target.provider_type not in (ProviderType.HOSPITAL, ProviderType.CLINIC):
                raise InvalidProviderDataError(f"Organization not found or not a Hospital/Clinic: {organization_id}")
            db.add(DoctorOrganization(
                doctor_id=invitation.provider_id,
                organization_id=organization_id,
                status=DoctorOrganizationStatus.PENDING,
            ))
        wanted_set = set(wanted)
        for rel in existing:
            if rel.organization_id not in wanted_set and rel.status == DoctorOrganizationStatus.PENDING:
                db.delete(rel)
        db.flush()