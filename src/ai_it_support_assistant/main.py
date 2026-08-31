from fastapi import FastAPI

from ai_it_support_assistant.api.routes.health import router as health_router
from ai_it_support_assistant.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Production-style GenAI IT support backend",
        version=settings.app_version,
        debug=settings.debug,
    )

    # Include the health check router
    app.include_router(health_router, prefix="/api/v1", tags=["health"])

    return app


app = create_app()
