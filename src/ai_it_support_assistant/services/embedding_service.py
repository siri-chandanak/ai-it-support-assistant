from functools import lru_cache

from sentence_transformers import SentenceTransformer

from ai_it_support_assistant.schemas.document import DocumentChunk


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
