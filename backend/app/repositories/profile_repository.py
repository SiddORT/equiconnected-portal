"""Persistence queries for records owned by the authenticated member."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.profile import Horse, StableProfile
from app.models.user import User, UserRole


class ProfileRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_member(self, user_id: uuid.UUID) -> User | None:
        return self._db.scalars(
            select(User)
            .options(
                joinedload(User.role),
                selectinload(User.role_assignments).joinedload(UserRole.role),
                joinedload(User.stable_profile),
                selectinload(User.horses),
            )
            .where(User.id == user_id)
        ).first()

    def get_stable(self, user_id: uuid.UUID) -> StableProfile | None:
        return self._db.scalars(select(StableProfile).where(StableProfile.user_id == user_id)).first()

    def create_stable(self, user_id: uuid.UUID, fields: dict) -> StableProfile:
        stable = StableProfile(user_id=user_id, **fields)
        self._db.add(stable)
        self._db.flush()
        return stable

    def get_horse(self, user_id: uuid.UUID, horse_id: uuid.UUID) -> Horse | None:
        return self._db.scalars(
            select(Horse).where(Horse.id == horse_id, Horse.user_id == user_id)
        ).first()

    def get_horse_for_member(self, user_id: uuid.UUID, horse_id: uuid.UUID) -> Horse | None:
        return self.get_horse(user_id, horse_id)

    def add_horse(self, user_id: uuid.UUID, fields: dict) -> Horse:
        horse = Horse(user_id=user_id, **fields)
        self._db.add(horse)
        self._db.flush()
        return horse

    def delete_horse(self, horse: Horse) -> None:
        self._db.delete(horse)
        self._db.flush()

    def commit(self) -> None:
        self._db.commit()