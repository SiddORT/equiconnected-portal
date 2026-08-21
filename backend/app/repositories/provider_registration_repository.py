"""Persistence operations for provider-account registration applications."""
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import ProviderApplicationStatus, ProviderType
from app.models.provider_registration import ProviderRegistrationApplication
from app.models.user import User


class ProviderRegistrationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, **fields) -> ProviderRegistrationApplication:
        application = ProviderRegistrationApplication(**fields)
        self._db.add(application)
        self._db.flush()
        return application

    def get_for_update(self, application_id: UUID) -> ProviderRegistrationApplication | None:
        return self._db.scalar(
            select(ProviderRegistrationApplication)
            .options(
                joinedload(ProviderRegistrationApplication.user),
                joinedload(ProviderRegistrationApplication.provider),
            )
            .where(ProviderRegistrationApplication.id == application_id)
            .with_for_update(of=ProviderRegistrationApplication)
        )

    def get_for_user_for_update(self, user_id: UUID) -> ProviderRegistrationApplication | None:
        return self._db.scalar(
            select(ProviderRegistrationApplication)
            .where(ProviderRegistrationApplication.user_id == user_id)
            .with_for_update()
        )

    def list(
        self,
        *,
        search: str | None = None,
        provider_type: ProviderType | None = None,
        email_verified: bool | None = None,
        review_status: ProviderApplicationStatus | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[ProviderRegistrationApplication], int]:
        conditions = []
        if search:
            pattern = f"%{search.strip()}%"
            conditions.append(
                or_(
                    ProviderRegistrationApplication.provider_name.ilike(pattern),
                    ProviderRegistrationApplication.user.has(
                        or_(
                            User.email.ilike(pattern),
                            User.first_name.ilike(pattern),
                            User.last_name.ilike(pattern),
                        )
                    ),
                )
            )
        if provider_type is not None:
            conditions.append(ProviderRegistrationApplication.provider_type == provider_type)
        if review_status is not None:
            conditions.append(ProviderRegistrationApplication.review_status == review_status)
        if email_verified is True:
            conditions.append(
                ProviderRegistrationApplication.user.has(
                    User.email_verified_at.is_not(None)
                )
            )
        if email_verified is False:
            conditions.append(
                ProviderRegistrationApplication.user.has(
                    User.email_verified_at.is_(None)
                )
            )
        total = self._db.scalar(
            select(func.count()).select_from(ProviderRegistrationApplication).where(*conditions)
        ) or 0
        rows = self._db.scalars(
            select(ProviderRegistrationApplication)
            .options(
                joinedload(ProviderRegistrationApplication.user),
                joinedload(ProviderRegistrationApplication.reviewer),
                joinedload(ProviderRegistrationApplication.provider),
            )
            .where(*conditions)
            .order_by(ProviderRegistrationApplication.created_at.desc(), ProviderRegistrationApplication.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), total

    def get(self, application_id: UUID) -> ProviderRegistrationApplication | None:
        return self._db.scalar(
            select(ProviderRegistrationApplication)
            .options(
                joinedload(ProviderRegistrationApplication.user),
                joinedload(ProviderRegistrationApplication.reviewer),
                joinedload(ProviderRegistrationApplication.provider),
            )
            .where(ProviderRegistrationApplication.id == application_id)
        )