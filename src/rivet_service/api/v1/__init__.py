from fastapi import APIRouter

from .api_keys import router as api_keys_router
from .auth import router as auth_router
from .generate import router as generate_router
from .generations import router as generations_router
from .local_artifacts import router as local_artifacts_router
from .me import router as me_router
from .projects import router as projects_router

router = APIRouter(prefix="/api/v1")
router.include_router(generate_router)
router.include_router(auth_router)
router.include_router(me_router)
router.include_router(api_keys_router)
router.include_router(projects_router)
router.include_router(generations_router)
router.include_router(local_artifacts_router)
