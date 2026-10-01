"""Data access for provider invitations."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.enums import InvitationStatus, ProviderType
from app.models.invitation import ProviderInvitation
from app.models.provider import Provider
from app.repositories import matches_like_substring, page_filtered_candidates
from app.services.contact_encryption import contact_blind_index


class InvitationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, **fields) -> ProviderInvitation:
        invitation = ProviderInvitation(**fields)
        self._db.add(invitation)
        self._db.flush()
        return invitation

    def get_by_id(self, invitation_id: UUID) -> ProviderInvitation | None:
        return self._db.scalar(
            select(ProviderInvitation)
            .where(ProviderInvitation.id == invitation_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def get_by_token_hash(self, token_hash: str) -> ProviderInvitation | None:
        return self._db.scalar(
            select(ProviderInvitation)
            .where(ProviderInvitation.token_hash == token_hash)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def lock_by_id(self, invitation_id: UUID) -> ProviderInvitation | None:
        """Lock and refresh an invitation before final submission."""
        return self._db.scalar(
            select(ProviderInvitation)
            .where(ProviderInvitation.id == invitation_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def expire_due(self) -> list[ProviderInvitation]:
        """Lock and return every invitation transitioned to EXPIRED."""
        rows = list(self._db.scalars(
            select(ProviderInvitation)
            .where(
                ProviderInvitation.status.in_(
                    [InvitationStatus.PENDING, InvitationStatus.ACCEPTED]
                ),
                ProviderInvitation.expires_at <= datetime.now(timezone.utc),
            )
            .with_for_update()
        ).all())
        for invitation in rows:
            invitation.status = InvitationStatus.EXPIRED
        self._db.flush()
        return rows

    def lock_new_provider_invitation(
        self, provider_type: ProviderType, email: str
    ) -> None:
        """Serialize new-provider creation for one normalized type/email pair."""
        lock_digest = contact_blind_index(
            email,
            table="provider_invitation_advisory_lock",
            field=f"{provider_type.value}:recipient_email",
        )
        lock_key = int.from_bytes(
            bytes.fromhex(lock_digest)[:8], byteorder="big", signed=True
        )
        self._db.execute(select(func.pg_advisory_xact_lock(lock_key)))

    def has_active_for_provider_email(
        self, provider_id: UUID, email: str, *, except_id: UUID | None = None
    ) -> bool:
        stmt = select(ProviderInvitation.id).where(
                ProviderInvitation.provider_id == provider_id,
                ProviderInvitation.recipient_email == email,
                ProviderInvitation.status.in_([InvitationStatus.PENDING, InvitationStatus.ACCEPTED]),
                ProviderInvitation.expires_at > datetime.now(timezone.utc),
            )
        if except_id is not None:
            stmt = stmt.where(ProviderInvitation.id != except_id)
        return self._db.scalar(stmt) is not None

    def has_active_for_new_provider(self, provider_type: ProviderType, email: str) -> bool:
        """Prevent repeated 'new provider' requests from creating duplicate drafts."""
        return self._db.scalar(
            select(ProviderInvitation.id).where(
                ProviderInvitation.provider_type == provider_type,
                ProviderInvitation.recipient_email == email,
                ProviderInvitation.status.in_([InvitationStatus.PENDING, InvitationStatus.ACCEPTED]),
                ProviderInvitation.expires_at > datetime.now(timezone.utc),
            )
        ) is not None

    def update_status(
        self, invitation: ProviderInvitation, status: InvitationStatus
    ) -> ProviderInvitation:
        invitation.status = status
        self._db.flush()
        return invitation

    def invalidate_old_tokens_for_provider_email(
        self, provider_id: UUID, email: str, *, except_id: UUID | None = None
    ) -> None:
        stmt = (
            update(ProviderInvitation)
            .where(
                ProviderInvitation.provider_id == provider_id,
                ProviderInvitation.recipient_email == email,
                ProviderInvitation.status.in_(
                    [InvitationStatus.PENDING, InvitationStatus.ACCEPTED]
                ),
            )
            .values(status=InvitationStatus.CANCELLED)
        )
        if except_id is not None:
            stmt = stmt.where(ProviderInvitation.id != except_id)
        self._db.execute(stmt)
        self._db.flush()

    def list(
        self, *, search: str | None = None, status: InvitationStatus | None = None,
        provider_type: ProviderType | None = None, date_from: datetime | None = None,
        date_to: datetime | None = None, page: int = 1, page_size: int = 20,
    ) -> tuple[list[tuple[ProviderInvitation, str | None, object]], int]:
        stmt = select(ProviderInvitation, Provider.name, Provider.status).outerjoin(
            Provider, Provider.id == ProviderInvitation.provider_id
        )
        count_stmt = (
            select(func.count())
            .select_from(ProviderInvitation)
            .outerjoin(Provider, Provider.id == ProviderInvitation.provider_id)
        )
        conditions = []
        search_term = search.strip().lower() if search else ""
        if status:
            conditions.append(ProviderInvitation.status == status)
        if provider_type:
            conditions.append(ProviderInvitation.provider_type == provider_type)
        if date_from:
            conditions.append(ProviderInvitation.sent_at >= date_from)
        if date_to:
            conditions.append(ProviderInvitation.sent_at < date_to)
        for condition in conditions:
            stmt, count_stmt = stmt.where(condition), count_stmt.where(condition)
        if search_term:
            candidates = self._db.execute(
                stmt.order_by(
                    ProviderInvitation.created_at.desc(), ProviderInvitation.id.desc()
                ).execution_options(yield_per=250)
            )
            return page_filtered_candidates(
                candidates,
                lambda row: (
                    matches_like_substring(row[0].recipient_email, search_term)
                    or matches_like_substring(row[1], search_term)
                ),
                page=page,
                page_size=page_size,
            )
        total = self._db.scalar(count_stmt) or 0
        items = [
            (row[0], row[1], row[2])
            for row in self._db.execute(
                stmt.order_by(
                    ProviderInvitation.created_at.desc(), ProviderInvitation.id.desc()
                ).offset((page - 1) * page_size).limit(page_size)
            )
        ]
        return items, total

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()