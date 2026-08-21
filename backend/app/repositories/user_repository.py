"""
User data access — all DB queries for users go through here.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.user import User, UserRole
from app.models.role import Role


class UserRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = (
            select(User)
            .options(joinedload(User.role))
            .where(User.id == user_id)
        )
        return self._db.scalars(stmt).first()

    def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .options(joinedload(User.role))
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

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()
