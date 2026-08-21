"""Approved public member profile endpoints."""
import os
import uuid
from typing import Annotated
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.profile import (
    HorseCreate, HorseResponse, HorseUpdate, MemberProfileResponse, PersonalProfileUpdate,
    PostalLookupResponse, StableProfileResponse, StableProfileUpdate,
)
from app.services.profile_service import HorseNotFoundError, MemberProfileAccessError, ProfileService

router = APIRouter(prefix="/profile", tags=["Member Profile"])
_DB = Annotated[Session, Depends(get_db)]


def _svc(db: _DB) -> ProfileService:
    return ProfileService(db)


_Svc = Annotated[ProfileService, Depends(_svc)]
_ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}
_MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
_UPLOADS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "uploads"
)


def _forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "member_profile_forbidden", "message": "This profile area is available to approved members only."},
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "horse_not_found", "message": "Horse not found."})


def _profile_response(user) -> MemberProfileResponse:
    roles = sorted({assignment.role.name for assignment in user.role_assignments} or {user.role.name})
    return MemberProfileResponse(
        first_name=user.first_name, last_name=user.last_name, email=user.email,
        mobile_number=user.mobile_number, address=user.address, country=user.country,
        state_province=user.state_province, city=user.city, postal_code=user.postal_code,
        roles=roles, stable_profile=user.stable_profile,
        horses=sorted(user.horses, key=lambda horse: (horse.created_at, horse.id)),
    )


@router.get("", response_model=MemberProfileResponse)
def get_profile(user: CurrentUser, svc: _Svc) -> MemberProfileResponse:
    try:
        return _profile_response(svc.get(user))
    except MemberProfileAccessError:
        raise _forbidden()


@router.put("/personal", response_model=MemberProfileResponse)
def update_personal(body: PersonalProfileUpdate, user: CurrentUser, svc: _Svc) -> MemberProfileResponse:
    try:
        return _profile_response(svc.update_personal(user, body))
    except MemberProfileAccessError:
        raise _forbidden()


@router.put("/stable", response_model=StableProfileResponse)
def update_stable(body: StableProfileUpdate, user: CurrentUser, svc: _Svc) -> StableProfileResponse:
    try:
        return StableProfileResponse.model_validate(svc.update_stable(user, body))
    except MemberProfileAccessError:
        raise _forbidden()


@router.get("/horses", response_model=list[HorseResponse])
def list_horses(user: CurrentUser, svc: _Svc) -> list[HorseResponse]:
    try:
        return [HorseResponse.model_validate(horse) for horse in svc.list_horses(user)]
    except MemberProfileAccessError:
        raise _forbidden()


@router.post("/horses", response_model=HorseResponse, status_code=status.HTTP_201_CREATED)
def add_horse(body: HorseCreate, user: CurrentUser, svc: _Svc) -> HorseResponse:
    try:
        return HorseResponse.model_validate(svc.add_horse(user, body))
    except MemberProfileAccessError:
        raise _forbidden()


@router.put("/horses/{horse_id}", response_model=HorseResponse)
def update_horse(horse_id: uuid.UUID, body: HorseUpdate, user: CurrentUser, svc: _Svc) -> HorseResponse:
    try:
        return HorseResponse.model_validate(svc.update_horse(user, horse_id, body))
    except MemberProfileAccessError:
        raise _forbidden()
    except HorseNotFoundError:
        raise _not_found()


@router.delete("/horses/{horse_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_horse(horse_id: uuid.UUID, user: CurrentUser, svc: _Svc) -> None:
    try:
        svc.delete_horse(user, horse_id)
    except MemberProfileAccessError:
        raise _forbidden()
    except HorseNotFoundError:
        raise _not_found()


@router.post("/horses/{horse_id}/photo", response_model=HorseResponse)
async def upload_horse_photo(horse_id: uuid.UUID, file: UploadFile, user: CurrentUser, svc: _Svc) -> HorseResponse:
    try:
        # Confirm role and ownership before persisting any bytes.
        svc.list_horses(user)
        svc.get_horse(user, horse_id)
    except MemberProfileAccessError:
        raise _forbidden()
    except HorseNotFoundError:
        raise _not_found()

    extension = _ALLOWED_IMAGE_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(422, detail={"code": "invalid_image_type", "message": "Only JPEG, PNG, GIF, and WebP images are accepted."})
    try:
        contents = await file.read()
    finally:
        await file.close()
    if len(contents) > _MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(413, detail={"code": "image_too_large", "message": "Images must be 10 MB or smaller."})
    destination_dir = os.path.join(_UPLOADS_DIR, "horses", str(user.id), str(horse_id))
    os.makedirs(destination_dir, exist_ok=True)
    filename = f"{uuid.uuid4()}{extension}"
    with open(os.path.join(destination_dir, filename), "wb") as saved:
        saved.write(contents)
    reference = f"/uploads/horses/{user.id}/{horse_id}/{filename}"
    return HorseResponse.model_validate(svc.set_horse_photo(user, horse_id, reference))


@router.delete("/horses/{horse_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
def remove_horse_photo(horse_id: uuid.UUID, user: CurrentUser, svc: _Svc) -> None:
    try:
        svc.remove_horse_photo(user, horse_id)
    except MemberProfileAccessError:
        raise _forbidden()
    except HorseNotFoundError:
        raise _not_found()


@router.get("/postal-lookup", response_model=PostalLookupResponse)
async def postal_lookup(
    user: CurrentUser,
    svc: _Svc,
    country: str = Query(min_length=1, max_length=100),
    postal_code: str = Query(min_length=1, max_length=32),
) -> PostalLookupResponse:
    try:
        svc.get(user)
    except MemberProfileAccessError:
        raise _forbidden()
    template = get_settings().POSTAL_LOOKUP_URL
    if not template:
        return PostalLookupResponse(status="unavailable")
    try:
        url = template.format(country=quote(country.strip(), safe=""), postal_code=quote(postal_code.strip(), safe=""))
    except (KeyError, ValueError):
        return PostalLookupResponse(status="unavailable")
    try:
        settings = get_settings()
        async with httpx.AsyncClient(
            timeout=settings.POSTAL_LOOKUP_TIMEOUT_SECONDS, follow_redirects=False
        ) as client:
            response = await client.get(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": f"{settings.APP_NAME}/{settings.APP_VERSION} ({settings.PUBLIC_APP_URL})",
                },
            )
        if response.status_code == 404:
            return PostalLookupResponse(status="no_match")
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            place = payload[0] if payload else {}
            address = place.get("address") or {}
            city = (
                address.get("city") or address.get("town") or address.get("village")
                or address.get("municipality")
            )
            state = address.get("state") or address.get("province")
        elif isinstance(payload, dict):
            place = (payload.get("places") or [{}])[0]
            city = place.get("place name") or place.get("city")
            state = place.get("state") or place.get("state abbreviation") or place.get("state_province")
        else:
            city = state = None
        if not city and not state:
            return PostalLookupResponse(status="no_match")
        return PostalLookupResponse(status="match", city=city, state_province=state)
    except (httpx.HTTPError, ValueError, TypeError):
        return PostalLookupResponse(status="unavailable")