"""Business rules for verified public member profiles."""
import uuid

from sqlalchemy.orm import Session

from app.models.profile import Horse, StableProfile
from app.models.user import User
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import HorseCreate, HorseUpdate, PersonalProfileUpdate, StableProfileUpdate

MEMBER_ROLES = frozenset({"horse_owner", "stable_manager"})


class MemberProfileAccessError(Exception):
    pass


class HorseNotFoundError(Exception):
    pass


class ProfileService:
    def __init__(self, db: Session) -> None:
        self._repo = ProfileRepository(db)

    @staticmethod
    def role_names(user: User) -> set[str]:
        return {assignment.role.name for assignment in user.role_assignments} or {user.role.name}

    def _member_roles(self, user: User) -> set[str]:
        roles = self.role_names(user)
        if not roles.intersection(MEMBER_ROLES):
            raise MemberProfileAccessError
        return roles

    def get(self, user: User) -> User:
        member = self._repo.get_member(user.id)
        if member is None:
            raise MemberProfileAccessError
        self._member_roles(member)
        return member

    def update_personal(self, user: User, payload: PersonalProfileUpdate) -> User:
        member = self.get(user)
        for field, value in payload.model_dump().items():
            setattr(member, field, value)
        self._repo.commit()
        return self.get(user)

    def update_stable(self, user: User, payload: StableProfileUpdate) -> StableProfile:
        member = self.get(user)
        if "stable_manager" not in self._member_roles(member):
            raise MemberProfileAccessError
        stable = member.stable_profile
        if stable is None:
            stable = self._repo.create_stable(member.id, payload.model_dump())
        else:
            for field, value in payload.model_dump().items():
                setattr(stable, field, value)
        self._repo.commit()
        return self._repo.get_stable(member.id)  # type: ignore[return-value]

    def list_horses(self, user: User) -> list[Horse]:
        member = self.get(user)
        if "horse_owner" not in self._member_roles(member):
            raise MemberProfileAccessError
        return sorted(member.horses, key=lambda horse: (horse.created_at, horse.id))

    def add_horse(self, user: User, payload: HorseCreate) -> Horse:
        self.list_horses(user)
        horse = self._repo.add_horse(user.id, payload.model_dump())
        self._repo.commit()
        return horse

    def get_horse(self, user: User, horse_id: uuid.UUID) -> Horse:
        self.list_horses(user)
        horse = self._repo.get_horse_for_member(user.id, horse_id)
        if horse is None:
            raise HorseNotFoundError
        return horse

    def update_horse(self, user: User, horse_id: uuid.UUID, payload: HorseUpdate) -> Horse:
        self.list_horses(user)
        horse = self._repo.get_horse(user.id, horse_id)
        if horse is None:
            raise HorseNotFoundError
        for field, value in payload.model_dump().items():
            setattr(horse, field, value)
        self._repo.commit()
        return horse

    def delete_horse(self, user: User, horse_id: uuid.UUID) -> None:
        self.list_horses(user)
        horse = self._repo.get_horse(user.id, horse_id)
        if horse is None:
            raise HorseNotFoundError
        self._repo.delete_horse(horse)
        self._repo.commit()

    def set_horse_photo(self, user: User, horse_id: uuid.UUID, reference: str | None) -> Horse:
        self.list_horses(user)
        horse = self._repo.get_horse(user.id, horse_id)
        if horse is None:
            raise HorseNotFoundError
        horse.photo_reference = reference
        self._repo.commit()
        return horse

    def remove_horse_photo(self, user: User, horse_id: uuid.UUID) -> None:
        self.set_horse_photo(user, horse_id, None)