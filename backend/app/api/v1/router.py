"""
API v1 root router.
Register new feature routers here as they are introduced.
"""
from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.admin import router as admin_router
from app.api.v1.specializations import router as specializations_router
from app.api.v1.providers import router as providers_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(specializations_router)
api_v1_router.include_router(providers_router)
