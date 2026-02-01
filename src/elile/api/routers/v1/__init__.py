"""API v1 routers."""

from fastapi import APIRouter

from .screening import router as screening_router

# Create v1 router that includes all v1 endpoints
router = APIRouter(prefix="/v1")

router.include_router(screening_router)

__all__ = ["router", "screening_router"]
