"""Language master administration and public provider signup lookup."""
from math import ceil
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.auth.dependencies import CurrentUser, require_role
from app.db.session import get_db
from app.models.language import Language
from app.schemas.language import LanguageCreate, LanguageResponse, LanguageUpdate

router = APIRouter(prefix="/admin/languages", tags=["Languages"], dependencies=[Depends(require_role("admin"))])

@router.get("")
def list_languages(
    db: Annotated[Session, Depends(get_db)],
    search: str | None = Query(None, max_length=100),
    is_active: bool | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
):
    q = db.query(Language)
    if search:
        q = q.filter(Language.name.ilike(f"%{search.strip()}%") | Language.code.ilike(f"%{search.strip()}%"))
    if is_active is not None:
        q = q.filter(Language.is_active == is_active)
    total = q.count()
    items = q.order_by(Language.name, Language.id).offset((page - 1) * page_size).limit(page_size).all()
    return {"data": [LanguageResponse.model_validate(x) for x in items],
            "meta": {"page": page, "page_size": page_size, "total": total, "total_pages": max(1, ceil(total / page_size))}}

@router.post("", response_model=LanguageResponse, status_code=status.HTTP_201_CREATED)
def create_language(body: LanguageCreate, db: Annotated[Session, Depends(get_db)], user: CurrentUser):
    if db.query(Language).filter(Language.code == body.code.lower()).first():
        raise HTTPException(409, detail={"code": "duplicate_language_code", "message": "Language code already exists."})
    item = Language(name=body.name, code=body.code.lower(), is_active=body.is_active)
    db.add(item); db.commit(); db.refresh(item)
    return item

@router.patch("/{id}", response_model=LanguageResponse)
def update_language(id: UUID, body: LanguageUpdate, db: Annotated[Session, Depends(get_db)], user: CurrentUser):
    item = db.get(Language, id)
    if not item: raise HTTPException(404, detail={"code": "language_not_found", "message": "Language not found."})
    values = body.model_dump(exclude_unset=True)
    if "code" in values: values["code"] = values["code"].lower()
    if "code" in values and db.query(Language).filter(Language.code == values["code"], Language.id != id).first():
        raise HTTPException(409, detail={"code": "duplicate_language_code", "message": "Language code already exists."})
    for key, value in values.items(): setattr(item, key, value)
    db.commit(); db.refresh(item)
    return item

@router.delete("/{id}", response_model=LanguageResponse)
def delete_language(id: UUID, db: Annotated[Session, Depends(get_db)], user: CurrentUser):
    item = db.get(Language, id)
    if not item: raise HTTPException(404, detail={"code": "language_not_found", "message": "Language not found."})
    item.is_active = False; db.commit(); db.refresh(item)
    return item