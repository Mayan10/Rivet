from fastapi import APIRouter

from .generate import router as generate_router

router = APIRouter(prefix="/api/v1")
router.include_router(generate_router)
