from fastapi import FastAPI

from ai_it_support_assistant.api.routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI IT Support Assistant",
        description="Production-style GenAI IT support backend",
        version="0.1.0",
    )

    # Include the health check router
    app.include_router(health_router, prefix="/api/v1", tags=["health"])

    return app


app = create_app()
