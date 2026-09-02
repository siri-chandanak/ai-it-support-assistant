from fastapi import APIRouter, HTTPException, status

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.schemas.rag import (
    RAGRequest,
    RAGResponse,
)
from ai_it_support_assistant.services.embedding_service import (
    EmbeddingError,
)
from ai_it_support_assistant.services.rag_service import (
    RAGError,
    answer_question,
)
from ai_it_support_assistant.services.retrieval_service import (
    RetrievalError,
)

router = APIRouter()


@router.post(
    "/rag/answer",
    response_model=RAGResponse,
)
def rag_answer(
    request: RAGRequest,
) -> RAGResponse:
    settings = get_settings()

    try:
        return answer_question(
            question=request.question,
            top_k=settings.rag_top_k,
            score_threshold=settings.rag_score_threshold,
            embedding_model_name=settings.embedding_model_name,
            qdrant_url=settings.qdrant_url,
            collection_name=settings.qdrant_collection_name,
            openai_api_key=settings.openai_api_key,
            llm_model=settings.llm_model,
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
    except RAGError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Answer generation failed.",
        ) from exc
