import hashlib
from threading import Lock

from cachetools import TTLCache

from ai_it_support_assistant.observability.metrics import (
    embedding_cache_hits_total,
    embedding_cache_misses_total,
    retrieval_cache_hits_total,
    retrieval_cache_misses_total,
)
from ai_it_support_assistant.schemas.retrieval import (
    RetrievedChunk,
)


class CacheError(Exception):
    pass


_embedding_cache: TTLCache | None = None
_retrieval_cache: TTLCache | None = None

_embedding_cache_lock = Lock()
_retrieval_cache_lock = Lock()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_query(query: str) -> str:
    return " ".join(query.strip().lower().split())


def build_embedding_cache_key(
    *,
    query: str,
    model_name: str,
) -> str:
    normalized_query = normalize_query(query)
    query_hash = hash_text(normalized_query)

    return f"embedding:{model_name}:{query_hash}"


def configure_embedding_cache(
    *,
    max_size: int,
    ttl_seconds: int,
) -> None:
    global _embedding_cache

    with _embedding_cache_lock:
        _embedding_cache = TTLCache(
            maxsize=max_size,
            ttl=ttl_seconds,
        )


def configure_retrieval_cache(
    *,
    max_size: int,
    ttl_seconds: int,
) -> None:
    global _retrieval_cache

    with _retrieval_cache_lock:
        _retrieval_cache = TTLCache(
            maxsize=max_size,
            ttl=ttl_seconds,
        )


def get_cached_embedding(
    key: str,
) -> list[float] | None:
    if _embedding_cache is None:
        return None

    with _embedding_cache_lock:
        value = _embedding_cache.get(key)

    if value is None:
        embedding_cache_misses_total.inc()
        return None

    embedding_cache_hits_total.inc()

    return list(value)


def set_cached_embedding(
    *,
    key: str,
    embedding: list[float],
) -> None:
    if _embedding_cache is None:
        return

    with _embedding_cache_lock:
        _embedding_cache[key] = list(embedding)


def build_retrieval_cache_key(
    *,
    query: str,
    model_name: str,
    collection_name: str,
    top_k: int,
    user_roles: list[str],
) -> str:
    normalized_query = normalize_query(query)

    query_hash = hash_text(normalized_query)

    normalized_roles = ",".join(sorted(set(user_roles)))

    return (
        f"retrieval:"
        f"{model_name}:"
        f"{collection_name}:"
        f"top_k={top_k}:"
        f"roles={normalized_roles}:"
        f"{query_hash}"
    )


def get_cached_retrieval(
    key: str,
) -> list[RetrievedChunk] | None:
    if _retrieval_cache is None:
        return None

    with _retrieval_cache_lock:
        cached = _retrieval_cache.get(key)

    if cached is None:
        retrieval_cache_misses_total.inc()
        return None

    retrieval_cache_hits_total.inc()

    return [RetrievedChunk.model_validate(item) for item in cached]


def set_cached_retrieval(
    *,
    key: str,
    chunks: list[RetrievedChunk],
) -> None:
    if _retrieval_cache is None:
        return

    serialized = [chunk.model_dump() for chunk in chunks]

    with _retrieval_cache_lock:
        _retrieval_cache[key] = serialized


def clear_embedding_cache() -> None:
    if _embedding_cache is None:
        return

    with _embedding_cache_lock:
        _embedding_cache.clear()


def clear_retrieval_cache() -> None:
    if _retrieval_cache is None:
        return

    with _retrieval_cache_lock:
        _retrieval_cache.clear()


def clear_all_caches() -> None:
    clear_embedding_cache()
    clear_retrieval_cache()
