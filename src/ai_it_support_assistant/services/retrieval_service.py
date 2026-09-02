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
) -> list[RetrievedChunk]:
    query_vector = embed_query(
        query=query,
        model_name=embedding_model_name,
    )

    client = get_qdrant_client(qdrant_url)

    try:
        response = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )
    except Exception as exc:
        raise RetrievalError("Failed to query vector store.") from exc

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
