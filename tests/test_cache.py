from ai_it_support_assistant.cache.cache_service import (
    build_embedding_cache_key,
    build_retrieval_cache_key,
    configure_embedding_cache,
    get_cached_embedding,
    set_cached_embedding,
)


def test_embedding_cache_round_trip() -> None:
    configure_embedding_cache(
        max_size=10,
        ttl_seconds=60,
    )

    set_cached_embedding(
        key="test",
        embedding=[0.1, 0.2],
    )

    assert get_cached_embedding("test") == [0.1, 0.2]


def test_embedding_cache_key_normalizes_query() -> None:
    key_one = build_embedding_cache_key(
        query="How do I reset VPN?",
        model_name="model-a",
    )

    key_two = build_embedding_cache_key(
        query="  HOW   DO I RESET VPN? ",
        model_name="model-a",
    )

    assert key_one == key_two


def test_embedding_cache_key_includes_model() -> None:
    key_one = build_embedding_cache_key(
        query="How do I reset VPN?",
        model_name="model-a",
    )

    key_two = build_embedding_cache_key(
        query="How do I reset VPN?",
        model_name="model-b",
    )

    assert key_one != key_two


def test_retrieval_cache_key_includes_top_k() -> None:
    key_three = build_retrieval_cache_key(
        query="VPN issue",
        model_name="model-a",
        collection_name="documents",
        top_k=3,
    )

    key_five = build_retrieval_cache_key(
        query="VPN issue",
        model_name="model-a",
        collection_name="documents",
        top_k=5,
    )

    assert key_three != key_five
