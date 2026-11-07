from fastapi import APIRouter

from backend.app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "env": settings.app_env, "dataset_version": settings.dataset_version}
