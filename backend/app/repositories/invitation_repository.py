"""Data access for provider invitations."""
import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.models.enums import InvitationStatus, ProviderType
from app.models.invitation import ProviderInvitation
from app.models.provider import Provider


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
        )

    def get_by_token_hash(self, token_hash: str) -> ProviderInvitation | None:
        return self._db.scalar(
            select(ProviderInvitation)
            .where(ProviderInvitation.token_hash == token_hash)
            .with_for_update()
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
        lock_input = f"{provider_type.value}:{email}".encode("utf-8")
        lock_key = int.from_bytes(
            hashlib.sha256(lock_input).digest()[:8], byteorder="big", signed=True
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
        if search:
            term = f"%{search.strip()}%"
            conditions.append(
                or_(
                    ProviderInvitation.recipient_email.ilike(term),
                    Provider.name.ilike(term),
                )
            )
        if status:
            conditions.append(ProviderInvitation.status == status)
        if provider_type:
            conditions.append(ProviderInvitation.provider_type == provider_type)
        if date_from:
            conditions.append(ProviderInvitation.sent_at >= date_from)
        if date_to:
            conditions.append(ProviderInvitation.sent_at <= date_to)
        for condition in conditions:
            stmt, count_stmt = stmt.where(condition), count_stmt.where(condition)
        total = self._db.scalar(count_stmt) or 0
        items = [
            (row[0], row[1], row[2])
            for row in self._db.execute(
                stmt.order_by(ProviderInvitation.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        ]
        return items, total

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()