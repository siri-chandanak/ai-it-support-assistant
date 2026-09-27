from ai_it_support_assistant.cache.cache_service import (
    configure_embedding_cache,
    configure_retrieval_cache,
)
from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.core.logging import configure_logging
from ai_it_support_assistant.mcp_server.server import mcp


def main() -> None:
    settings = get_settings()

    configure_embedding_cache(
        max_size=settings.embedding_cache_max_size,
        ttl_seconds=settings.embedding_cache_ttl_seconds,
    )

    configure_retrieval_cache(
        max_size=settings.retrieval_cache_max_size,
        ttl_seconds=settings.retrieval_cache_ttl_seconds,
    )

    configure_logging(log_level=settings.log_level)

    if not settings.mcp_enabled:
        raise RuntimeError("MCP server is disabled.")

    mcp.run(
        transport="streamable-http",
        host=settings.mcp_host,
        port=settings.mcp_port,
        json_response=True,
        stateless_http=True,
    )


if __name__ == "__main__":
    main()
