"""API v1 routers."""

from fastapi import APIRouter

from .dashboard import router as dashboard_router
from .hris_webhook import router as hris_webhook_router
from .screening import router as screening_router

# Create v1 router that includes all v1 endpoints
router = APIRouter(prefix="/v1")

router.include_router(screening_router)
router.include_router(hris_webhook_router)
router.include_router(dashboard_router)

__all__ = ["router", "screening_router", "hris_webhook_router", "dashboard_router"]
