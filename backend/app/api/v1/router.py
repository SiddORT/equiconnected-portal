"""
API v1 root router.
Register new feature routers here as they are introduced.
"""
from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.admin import router as admin_router
from app.api.v1.specializations import router as specializations_router
from app.api.v1.providers import router as providers_router
from app.api.v1.doctors import router as doctors_router
from app.api.v1.invitations import admin_router as invitations_admin_router, public_router as invitations_public_router
from app.api.v1.organization_requests import admin_router as organization_requests_admin_router, public_router as organizations_public_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(specializations_router)
api_v1_router.include_router(providers_router)
api_v1_router.include_router(doctors_router)
api_v1_router.include_router(invitations_admin_router)
api_v1_router.include_router(invitations_public_router)
api_v1_router.include_router(organizations_public_router)
api_v1_router.include_router(organization_requests_admin_router)
