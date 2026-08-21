"""
User data access — all DB queries for users go through here.
"""
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.user import PUBLIC_ACCOUNT_ROLE_NAMES, User, UserRole
from app.models.role import Role


class UserRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = (
            select(User)
            .options(
                joinedload(User.role),
                selectinload(User.role_assignments).joinedload(UserRole.role),
                joinedload(User.provider_registration_application),
            )
            .where(User.id == user_id)
        )
        return self._db.scalars(stmt).first()

    def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .options(
                joinedload(User.role),
                selectinload(User.role_assignments).joinedload(UserRole.role),
                joinedload(User.provider_registration_application),
            )
            .where(User.email == email.lower().strip())
        )
        return self._db.scalars(stmt).first()

    def get_role_by_name(self, name: str) -> Role | None:
        stmt = select(Role).where(Role.name == name)
        return self._db.scalars(stmt).first()

    def get_roles_by_names(self, names: list[str]) -> list[Role]:
        stmt = select(Role).where(Role.name.in_(names))
        return list(self._db.scalars(stmt).all())

    def create_role(self, name: str, description: str | None = None) -> Role:
        role = Role(name=name, description=description)
        self._db.add(role)
        self._db.flush()
        return role

    def create_user(
        self,
        email: str,
        password_hash: str,
        role: Role,
        first_name: str | None = None,
        last_name: str | None = None,
        mobile_number: str | None = None,
        country: str | None = None,
        state_province: str | None = None,
        city: str | None = None,
        terms_accepted_at=None,
        privacy_accepted_at=None,
        is_active: bool = True,
        roles: list[Role] | None = None,
    ) -> User:
        user = User(
            email=email.lower().strip(),
            password_hash=password_hash,
            role=role,
            first_name=first_name,
            last_name=last_name,
            mobile_number=mobile_number,
            country=country,
            state_province=state_province,
            city=city,
            terms_accepted_at=terms_accepted_at,
            privacy_accepted_at=privacy_accepted_at,
            is_active=is_active,
        )
        self._db.add(user)
        self._db.flush()
        for assigned_role in roles or [role]:
            self._db.add(UserRole(user_id=user.id, role_id=assigned_role.id))
        self._db.flush()
        return user

    def update_password_hash(self, user: User, password_hash: str) -> None:
        """Persist a deliberately rotated password hash for an existing user."""
        user.password_hash = password_hash
        self._db.flush()

    def _public_registrant_filter(self):
        """A reusable EXISTS-style filter which never returns administrator accounts."""
        public_user_ids = (
            select(UserRole.user_id)
            .join(Role, UserRole.role_id == Role.id)
            .where(Role.name.in_(PUBLIC_ACCOUNT_ROLE_NAMES))
        )
        return User.id.in_(public_user_ids)

    def list_public_registrants(
        self,
        *,
        search: str | None = None,
        role: str | None = None,
        email_verified: bool | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[User], int]:
        """List only accounts made through the public registration role flow."""
        filters = [self._public_registrant_filter()]
        if search:
            pattern = f"%{search.strip().lower()}%"
            filters.append(
                or_(
                    func.lower(User.first_name).like(pattern),
                    func.lower(User.last_name).like(pattern),
                    func.lower(User.email).like(pattern),
                )
            )
        if role:
            matching_role_users = (
                select(UserRole.user_id)
                .join(Role, UserRole.role_id == Role.id)
                .where(Role.name == role)
            )
            filters.append(User.id.in_(matching_role_users))
        if email_verified is True:
            filters.append(User.email_verified_at.is_not(None))
        elif email_verified is False:
            filters.append(User.email_verified_at.is_(None))

        total = self._db.scalar(
            select(func.count()).select_from(User).where(*filters)
        ) or 0
        items = self._db.scalars(
            select(User)
            .options(
                joinedload(User.role),
                selectinload(User.role_assignments).joinedload(UserRole.role),
            )
            .where(*filters)
            .order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(items), total

    def get_public_registrant(self, user_id: uuid.UUID) -> User | None:
        return self._db.scalars(
            select(User)
            .options(
                joinedload(User.role),
                selectinload(User.role_assignments).joinedload(UserRole.role),
            )
            .where(User.id == user_id, self._public_registrant_filter())
        ).first()

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()
