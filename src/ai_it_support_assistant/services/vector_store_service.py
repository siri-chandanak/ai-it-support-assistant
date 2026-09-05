from functools import lru_cache
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from ai_it_support_assistant.schemas.document import DocumentChunk


class VectorStoreError(Exception):
    pass


@lru_cache
def get_qdrant_client(qdrant_url: str, timeout_seconds: float) -> QdrantClient:
    return QdrantClient(url=qdrant_url, timeout=timeout_seconds)


def ensure_collection(
    *,
    client: QdrantClient,
    collection_name: str,
    vector_size: int,
) -> None:
    try:
        if client.collection_exists(collection_name):
            return

        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )
    except Exception as exc:
        raise VectorStoreError(
            f"Unable to initialize Qdrant collection: {collection_name}"
        ) from exc


def store_chunk_vectors(
    *,
    chunks: list[DocumentChunk],
    embeddings: list[list[float]],
    qdrant_url: str,
    collection_name: str,
    qdrant_timeout_seconds: float,
) -> int:
    if not chunks:
        raise VectorStoreError("Cannot store an empty chunk list.")

    if len(chunks) != len(embeddings):
        raise VectorStoreError("Chunk count does not match embedding count.")

    if not embeddings or not embeddings[0]:
        raise VectorStoreError("Embeddings cannot be empty.")

    client = get_qdrant_client(qdrant_url, qdrant_timeout_seconds)

    vector_size = len(embeddings[0])

    ensure_collection(
        client=client,
        collection_name=collection_name,
        vector_size=vector_size,
    )

    points = [
        models.PointStruct(
            id=str(uuid5(NAMESPACE_URL, chunk.chunk_id)),
            vector=embedding,
            payload={
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "character_count": chunk.character_count,
            },
        )
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]

    try:
        client.upsert(
            collection_name=collection_name,
            points=points,
            wait=True,
        )
    except Exception as exc:
        raise VectorStoreError("Failed to store chunk vectors in Qdrant.") from exc

    return len(points)
