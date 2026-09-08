import logging
import time

from qdrant_client import QdrantClient, models
from tenacity import (
    Retrying,
    stop_after_attempt,
    wait_exponential,
)

from ai_it_support_assistant.cache.cache_service import (
    build_retrieval_cache_key,
    get_cached_retrieval,
    set_cached_retrieval,
)
from ai_it_support_assistant.core.request_context import (
    get_request_id,
)
from ai_it_support_assistant.schemas.retrieval import RetrievedChunk
from ai_it_support_assistant.services.embedding_service import embed_query
from ai_it_support_assistant.services.vector_store_service import get_qdrant_client

logger = logging.getLogger(__name__)


class RetrievalError(Exception):
    pass


def create_qdrant_retryer(
    max_attempts: int,
) -> Retrying:
    return Retrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=4,
        ),
        reraise=True,
    )


def build_authorization_filter(
    user_roles: list[str],
) -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(
                key="allowed_roles",
                match=models.MatchAny(any=user_roles),
            )
        ]
    )


def query_qdrant_with_retry(
    *,
    client: QdrantClient,
    collection_name: str,
    query_vector: list[float],
    top_k: int,
    max_attempts: int,
    user_roles: list[str],
):
    retryer = create_qdrant_retryer(
        max_attempts=max_attempts,
    )
    authorization_filter = build_authorization_filter(user_roles)
    for attempt in retryer:
        with attempt:
            attempt_number = attempt.retry_state.attempt_number
            logger.info(
                ("qdrant_query_attempt request_id=%s attempt=%s"),
                get_request_id(),
                attempt_number,
            )
            return client.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=authorization_filter,
                limit=top_k,
                with_payload=True,
            )

    raise RetrievalError("Qdrant retry loop exited unexpectedly.")


def retrieve_chunks(
    *,
    query: str,
    top_k: int,
    embedding_model_name: str,
    embedding_cache_enabled: bool,
    retrieval_cache_enabled: bool,
    qdrant_url: str,
    collection_name: str,
    qdrant_timeout_seconds: float,
    qdrant_max_retries: int,
    user_roles: list[str],
) -> list[RetrievedChunk]:
    logger.info(
        ("retrieval_started request_id=%s question_length=%s top_k=%s"),
        get_request_id(),
        len(query),
        top_k,
    )

    embedding_start = time.perf_counter()

    retrieval_cache_key = build_retrieval_cache_key(
        query=query,
        model_name=embedding_model_name,
        collection_name=collection_name,
        top_k=top_k,
        user_roles=user_roles,
    )

    if retrieval_cache_enabled:
        cached_results = get_cached_retrieval(retrieval_cache_key)

        if cached_results is not None:
            logger.info(
                ("retrieval_cache_hit request_id=%s result_count=%s"),
                get_request_id(),
                len(cached_results),
            )

            return cached_results

        logger.info(
            ("retrieval_cache_miss request_id=%s"),
            get_request_id(),
        )

    query_vector = embed_query(
        query=query,
        model_name=embedding_model_name,
        cache_enabled=embedding_cache_enabled,
    )

    embedding_duration_ms = (time.perf_counter() - embedding_start) * 1000

    logger.info(
        ("query_embedding_completed request_id=%s duration_ms=%.2f vector_dimensions=%s"),
        get_request_id(),
        embedding_duration_ms,
        len(query_vector),
    )

    client = get_qdrant_client(qdrant_url, qdrant_timeout_seconds)

    try:
        qdrant_start = time.perf_counter()
        response = query_qdrant_with_retry(
            client=client,
            collection_name=collection_name,
            query_vector=query_vector,
            top_k=top_k,
            max_attempts=qdrant_max_retries,
            user_roles=user_roles,
        )
        qdrant_duration_ms = (time.perf_counter() - qdrant_start) * 1000

        logger.info(
            ("qdrant_search_completed request_id=%s duration_ms=%.2f top_k=%s result_count=%s"),
            get_request_id(),
            qdrant_duration_ms,
            top_k,
            len(response.points),
        )

    except Exception as exc:
        logger.exception(
            ("qdrant_search_failed request_id=%s collection=%s"),
            get_request_id(),
            collection_name,
        )
        raise RetrievalError("Failed to query vector store after retrying.") from exc

    results: list[RetrievedChunk] = []

    for point in response.points:
        payload = point.payload or {}

        try:
            results.append(
                RetrievedChunk(
                    chunk_id=str(payload["chunk_id"]),
                    document_id=str(payload["document_id"]),
                    chunk_index=int(payload["chunk_index"]),
                    text=str(payload["text"]),
                    score=float(point.score),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RetrievalError("Vector store returned invalid chunk metadata.") from exc
    logger.info(
        ("retrieval_completed request_id=%s retrieved_count=%s top_score=%s"),
        get_request_id(),
        len(results),
        results[0].score if results else None,
    )

    logger.debug(
        ("retrieval_result_metadata request_id=%s chunk_ids=%s"),
        get_request_id(),
        [chunk.chunk_id for chunk in results],
    )

    if retrieval_cache_enabled and results:
        set_cached_retrieval(
            key=retrieval_cache_key,
            chunks=results,
        )

    return results
