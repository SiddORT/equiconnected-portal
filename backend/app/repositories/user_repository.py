"""
User data access — all DB queries for users go through here.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.user import User
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
    ) -> User:
        user = User(
            email=email.lower().strip(),
            password_hash=password_hash,
            role=role,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        self._db.add(user)
        self._db.flush()
        return user

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()
