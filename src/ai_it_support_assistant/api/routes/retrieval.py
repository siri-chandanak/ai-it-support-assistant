from fastapi import APIRouter, HTTPException, status

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.schemas.retrieval import (
    RetrievalRequest,
    RetrievalResponse,
)
from ai_it_support_assistant.services.embedding_service import (
    EmbeddingError,
)
from ai_it_support_assistant.services.retrieval_service import (
    RetrievalError,
    retrieve_chunks,
)

router = APIRouter()


@router.post(
    "/retrieval/search",
    response_model=RetrievalResponse,
)
def search_documents(
    request: RetrievalRequest,
) -> RetrievalResponse:
    settings = get_settings()

    try:
        results = retrieve_chunks(
            query=request.query,
            top_k=request.top_k,
            embedding_model_name=settings.embedding_model_name,
            qdrant_url=settings.qdrant_url,
            collection_name=settings.qdrant_collection_name,
        )
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Query embedding failed.",
        ) from exc
    except RetrievalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document retrieval is unavailable.",
        ) from exc

    return RetrievalResponse(
        query=request.query,
        results=results,
    )
