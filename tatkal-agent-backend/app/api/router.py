"""
API v1 router.

All v1 endpoints are mounted under ``/api/v1``.
"""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.tasks import router as tasks_router
from app.api.runs import router as runs_router
from app.api.tools import router as tools_router
from app.api.skills import router as skills_router
from app.api.integrations import router as integrations_router
from app.api.audit import router as audit_router
from app.api.evidence import router as evidence_router
from app.api.railway import router as railway_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(runs_router)
api_v1_router.include_router(tools_router)
api_v1_router.include_router(skills_router)
api_v1_router.include_router(integrations_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(evidence_router)
api_v1_router.include_router(railway_router)
