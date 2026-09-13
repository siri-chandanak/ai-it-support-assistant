from fastapi import APIRouter, HTTPException, status

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.services.database_health_service import (
    DatabaseHealthError,
    check_database_health,
)

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    settings = get_settings()

    return {
        "status": "healthy",
        "environment": settings.environment,
        "version": settings.app_version,
    }


@router.get("/ready")
def readiness_check() -> dict[str, str]:
    settings = get_settings()

    try:
        check_database_health(
            database_url=settings.database_url,
        )
    except DatabaseHealthError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable.",
        ) from exc

    return {"status": "ready"}
