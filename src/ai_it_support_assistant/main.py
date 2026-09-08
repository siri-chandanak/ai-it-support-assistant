from fastapi import FastAPI

from ai_it_support_assistant.api.middleware.request_context import (
    RequestContextMiddleware,
)
from ai_it_support_assistant.api.routes.agent import router as agent_router
from ai_it_support_assistant.api.routes.auth import router as auth_router
from ai_it_support_assistant.api.routes.documents import router as documents_router
from ai_it_support_assistant.api.routes.health import router as health_router
from ai_it_support_assistant.api.routes.rag import router as rag_router
from ai_it_support_assistant.api.routes.retrieval import router as retrieval_router
from ai_it_support_assistant.cache.cache_service import (
    configure_embedding_cache,
    configure_retrieval_cache,
)
from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()

    configure_logging(log_level=settings.log_level)

    configure_embedding_cache(
        max_size=settings.embedding_cache_max_size,
        ttl_seconds=settings.embedding_cache_ttl_seconds,
    )

    configure_retrieval_cache(
        max_size=settings.retrieval_cache_max_size,
        ttl_seconds=settings.retrieval_cache_ttl_seconds,
    )

    app = FastAPI(
        title=settings.app_name,
        description="Production-style GenAI IT support backend",
        version=settings.app_version,
        debug=settings.debug,
    )
    app.add_middleware(RequestContextMiddleware)

    # Include the health check router
    app.include_router(health_router, prefix="/api/v1", tags=["health"])

    # Include the documents router
    app.include_router(documents_router, prefix="/api/v1", tags=["documents"])

    # Include the retrieval router
    app.include_router(retrieval_router, prefix="/api/v1", tags=["retrieval"])

    # Include the RAG router
    app.include_router(rag_router, prefix="/api/v1", tags=["rag"])

    # Include the auth router
    app.include_router(auth_router, prefix="/api/v1", tags=["auth"])

    # Include the agent router
    app.include_router(agent_router, prefix="/api/v1", tags=["agent"])

    return app


app = create_app()
