import logging
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from ai_it_support_assistant.cache.cache_service import (
    build_embedding_cache_key,
    get_cached_embedding,
    set_cached_embedding,
)
from ai_it_support_assistant.core.request_context import (
    get_request_id,
)
from ai_it_support_assistant.schemas.document import DocumentChunk

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    pass


@lru_cache
def get_embedding_model(model_name: str) -> SentenceTransformer:
    try:
        return SentenceTransformer(model_name)
    except Exception as exc:
        raise EmbeddingError(f"Unable to load embedding model: {model_name}") from exc


def embed_chunks(
    *,
    chunks: list[DocumentChunk],
    model_name: str,
) -> list[list[float]]:
    if not chunks:
        raise EmbeddingError("Cannot embed an empty chunk list.")

    model = get_embedding_model(model_name)

    texts = [chunk.text for chunk in chunks]

    try:
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
        )
    except Exception as exc:
        raise EmbeddingError("Failed to generate embeddings.") from exc

    return embeddings.tolist()


def embed_query(
    *,
    query: str,
    model_name: str,
    cache_enabled: bool,
) -> list[float]:
    cleaned_query = query.strip()

    if not cleaned_query:
        raise EmbeddingError("Cannot embed an empty query.")

    cache_key = build_embedding_cache_key(
        query=cleaned_query,
        model_name=model_name,
    )

    if cache_enabled:
        cached_embedding = get_cached_embedding(cache_key)

        if cached_embedding is not None:
            logger.info(
                ("embedding_cache_hit request_id=%s"),
                get_request_id(),
            )

            return cached_embedding

        logger.info(
            ("embedding_cache_miss request_id=%s"),
            get_request_id(),
        )

    model = get_embedding_model(model_name)

    try:
        embedding = model.encode(
            cleaned_query,
            normalize_embeddings=True,
        )
    except Exception as exc:
        raise EmbeddingError("Failed to generate query embedding.") from exc

    embedding_list = embedding.tolist()

    if cache_enabled:
        set_cached_embedding(
            key=cache_key,
            embedding=embedding_list,
        )

    return embedding.tolist()
