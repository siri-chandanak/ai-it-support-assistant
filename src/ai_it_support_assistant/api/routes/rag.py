import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ai_it_support_assistant.api.dependencies.auth import (
    get_current_user,
)
from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.core.request_context import (
    get_request_id,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.rag import (
    RAGRequest,
    RAGResponse,
)
from ai_it_support_assistant.services.embedding_service import (
    EmbeddingError,
)
from ai_it_support_assistant.services.llm_service import (
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from ai_it_support_assistant.services.rag_service import (
    RAGError,
    answer_question,
)
from ai_it_support_assistant.services.retrieval_service import (
    RetrievalError,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/rag/answer",
    response_model=RAGResponse,
)
def rag_answer(
    request: RAGRequest,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
) -> RAGResponse:
    settings = get_settings()
    logger.info(
        ("rag_authorized request_id=%s user_id=%s role_count=%s"),
        get_request_id(),
        current_user.user_id,
        len(current_user.roles),
    )
    try:
        return answer_question(
            question=request.question,
            top_k=settings.rag_top_k,
            user_roles=current_user.roles,
            score_threshold=settings.rag_score_threshold,
            embedding_model_name=settings.embedding_model_name,
            embedding_cache_enabled=settings.embedding_cache_enabled,
            retrieval_cache_enabled=settings.retrieval_cache_enabled,
            qdrant_url=settings.qdrant_url,
            collection_name=settings.qdrant_collection_name,
            openai_api_key=settings.openai_api_key,
            llm_model=settings.llm_model,
            qdrant_timeout_seconds=settings.qdrant_timeout_seconds,
            qdrant_max_attempts=settings.qdrant_max_attempts,
            openai_timeout_seconds=settings.openai_timeout_seconds,
            openai_max_retries=settings.openai_max_retries,
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

    except LLMAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answer service is misconfigured.",
        ) from exc

    except LLMRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answer service is temporarily capacity-limited.",
        ) from exc

    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Answer generation timed out.",
        ) from exc

    except LLMUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answer service is temporarily unavailable.",
        ) from exc
