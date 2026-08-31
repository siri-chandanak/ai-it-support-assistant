from fastapi import APIRouter

from ai_it_support_assistant.core.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    settings = get_settings()

    return {
        "status": "healthy",
        "environment": settings.environment,
        "version": settings.app_version,
    }
