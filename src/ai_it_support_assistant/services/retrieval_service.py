from qdrant_client import QdrantClient
from tenacity import (
    Retrying,
    stop_after_attempt,
    wait_exponential,
)

from ai_it_support_assistant.schemas.retrieval import RetrievedChunk
from ai_it_support_assistant.services.embedding_service import embed_query
from ai_it_support_assistant.services.vector_store_service import get_qdrant_client


class RetrievalError(Exception):
    pass


def retrieve_chunks(
    *,
    query: str,
    top_k: int,
    embedding_model_name: str,
    qdrant_url: str,
    collection_name: str,
    qdrant_timeout_seconds: float,
    qdrant_max_retries: int,
    openai_timeout_seconds: float,
    openai_max_retries: int,
) -> list[RetrievedChunk]:
    query_vector = embed_query(
        query=query,
        model_name=embedding_model_name,
    )

    client = get_qdrant_client(qdrant_url, qdrant_timeout_seconds)

    try:
        response = query_qdrant_with_retry(
            client=client,
            collection_name=collection_name,
            query_vector=query_vector,
            top_k=top_k,
            max_attempts=qdrant_max_retries,
        )
    except Exception as exc:
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

    return results


def query_qdrant_with_retry(
    *,
    client: QdrantClient,
    collection_name: str,
    query_vector: list[float],
    top_k: int,
    max_attempts: int,
):
    retryer = Retrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=4,
        ),
        reraise=True,
    )

    for attempt in retryer:
        with attempt:
            return client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=top_k,
                with_payload=True,
            )

    raise RetrievalError("Qdrant retry loop exited unexpectedly.")


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
