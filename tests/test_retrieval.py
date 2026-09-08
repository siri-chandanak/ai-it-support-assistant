from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from tenacity import (
    Retrying,
    stop_after_attempt,
    wait_none,
)

from ai_it_support_assistant.cache.cache_service import (
    build_retrieval_cache_key,
    configure_retrieval_cache,
    set_cached_retrieval,
)
from ai_it_support_assistant.schemas.retrieval import RetrievedChunk
from ai_it_support_assistant.services.retrieval_service import (
    RetrievalError,
    query_qdrant_with_retry,
    retrieve_chunks,
)


def test_retrieve_chunks_returns_ranked_results() -> None:
    mock_client = MagicMock()

    mock_client.query_points.return_value = SimpleNamespace(
        points=[
            SimpleNamespace(
                score=0.91,
                payload={
                    "chunk_id": "doc-1:2",
                    "document_id": "doc-1",
                    "chunk_index": 2,
                    "text": "Restart the VPN client.",
                },
            ),
            SimpleNamespace(
                score=0.72,
                payload={
                    "chunk_id": "doc-2:0",
                    "document_id": "doc-2",
                    "chunk_index": 0,
                    "text": "Reset your MFA token.",
                },
            ),
        ]
    )

    with (
        patch(
            "ai_it_support_assistant.services.retrieval_service.embed_query",
            return_value=[0.1, 0.2, 0.3],
        ),
        patch(
            "ai_it_support_assistant.services.retrieval_service.get_qdrant_client",
            return_value=mock_client,
        ),
    ):
        results = retrieve_chunks(
            query="VPN login issue",
            top_k=2,
            embedding_model_name="test-model",
            embedding_cache_enabled=False,
            retrieval_cache_enabled=False,
            qdrant_url="http://test-qdrant:6333",
            collection_name="test_chunks",
            qdrant_timeout_seconds=5.0,
            qdrant_max_retries=3,
            user_roles=["reader"],
        )

    assert len(results) == 2

    assert results[0].chunk_id == "doc-1:2"
    assert results[0].document_id == "doc-1"
    assert results[0].score == 0.91

    assert results[1].chunk_id == "doc-2:0"


def test_retrieve_chunks_rejects_invalid_payload() -> None:
    mock_client = MagicMock()

    mock_client.query_points.return_value = SimpleNamespace(
        points=[
            SimpleNamespace(
                score=0.9,
                payload={"document_id": "doc-1"},
            )
        ]
    )

    with (
        patch(
            "ai_it_support_assistant.services.retrieval_service.embed_query",
            return_value=[0.1, 0.2],
        ),
        patch(
            "ai_it_support_assistant.services.retrieval_service.get_qdrant_client",
            return_value=mock_client,
        ),
    ):
        with pytest.raises(
            RetrievalError,
            match="invalid chunk metadata",
        ):
            retrieve_chunks(
                query="VPN issue",
                top_k=3,
                embedding_model_name="test-model",
                embedding_cache_enabled=False,
                retrieval_cache_enabled=False,
                qdrant_url="http://test",
                collection_name="test",
                qdrant_timeout_seconds=5.0,
                qdrant_max_retries=3,
                user_roles=["reader"],
            )


def test_qdrant_query_retries_then_succeeds() -> None:
    mock_client = MagicMock()

    expected_response = MagicMock()

    mock_client.query_points.side_effect = [
        ConnectionError("temporary failure"),
        expected_response,
    ]

    test_retryer = Retrying(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        reraise=True,
    )

    with patch(
        "ai_it_support_assistant.services.retrieval_service.create_qdrant_retryer",
        return_value=test_retryer,
    ):
        response = query_qdrant_with_retry(
            client=mock_client,
            collection_name="test-collection",
            query_vector=[0.1, 0.2, 0.3],
            top_k=5,
            max_attempts=3,
            user_roles=["reader"],
        )

    assert response is expected_response
    assert mock_client.query_points.call_count == 2


def test_qdrant_query_fails_after_max_attempts() -> None:
    mock_client = MagicMock()

    mock_client.query_points.side_effect = ConnectionError("Qdrant unavailable")

    test_retryer = Retrying(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        reraise=True,
    )

    with patch(
        "ai_it_support_assistant.services.retrieval_service.create_qdrant_retryer",
        return_value=test_retryer,
    ):
        with pytest.raises(ConnectionError):
            query_qdrant_with_retry(
                client=mock_client,
                collection_name="test",
                query_vector=[0.1, 0.2],
                top_k=3,
                max_attempts=3,
                user_roles=["reader"],
            )

    assert mock_client.query_points.call_count == 3


def test_retrieve_chunks_uses_retrieval_cache() -> None:
    configure_retrieval_cache(
        max_size=100,
        ttl_seconds=300,
    )

    query = "How do I restart VPN?"
    model_name = "test-model"
    collection_name = "document_chunks"
    top_k = 5

    cached_chunks = [
        RetrievedChunk(
            chunk_id="doc:0",
            document_id="doc",
            chunk_index=0,
            text="VPN instructions",
            score=0.9,
        )
    ]

    cache_key = build_retrieval_cache_key(
        query=query,
        model_name=model_name,
        collection_name=collection_name,
        top_k=top_k,
        user_roles=["reader"],
    )

    set_cached_retrieval(
        key=cache_key,
        chunks=cached_chunks,
    )

    with (
        patch("ai_it_support_assistant.services.retrieval_service.embed_query") as mock_embed_query,
        patch(
            "ai_it_support_assistant.services.retrieval_service.get_qdrant_client"
        ) as mock_qdrant_client,
    ):
        results = retrieve_chunks(
            query=query,
            embedding_model_name=model_name,
            embedding_cache_enabled=False,
            retrieval_cache_enabled=True,
            collection_name=collection_name,
            top_k=top_k,
            qdrant_url="http://localhost:6333",
            qdrant_timeout_seconds=5.0,
            qdrant_max_retries=1,
            user_roles=["reader"],
        )

    assert results == cached_chunks
    mock_embed_query.assert_not_called()
    mock_qdrant_client.assert_not_called()


def test_retrieve_chunks_caches_qdrant_results() -> None:
    configure_retrieval_cache(
        max_size=100,
        ttl_seconds=300,
    )

    query = "How do I restart VPN?"
    model_name = "test-model"
    collection_name = "document_chunks"
    top_k = 5

    fake_vector = [0.1, 0.2, 0.3]

    mock_point = MagicMock()
    mock_point.id = "doc:0"
    mock_point.score = 0.9
    mock_point.payload = {
        "chunk_id": "doc:0",
        "document_id": "doc",
        "chunk_index": 0,
        "text": "VPN instructions",
    }

    mock_query_response = MagicMock()
    mock_query_response.points = [mock_point]

    mock_qdrant_client = MagicMock()
    mock_qdrant_client.query_points.return_value = mock_query_response

    with (
        patch(
            "ai_it_support_assistant.services.retrieval_service.embed_query",
            return_value=fake_vector,
        ) as mock_embed_query,
        patch(
            "ai_it_support_assistant.services.retrieval_service.get_qdrant_client",
            return_value=mock_qdrant_client,
        ) as mock_get_qdrant_client,
    ):
        first_results = retrieve_chunks(
            query=query,
            embedding_model_name=model_name,
            embedding_cache_enabled=False,
            retrieval_cache_enabled=True,
            collection_name=collection_name,
            top_k=top_k,
            qdrant_url="http://localhost:6333",
            qdrant_timeout_seconds=5.0,
            qdrant_max_retries=1,
            user_roles=["reader"],
        )

        second_results = retrieve_chunks(
            query=query,
            embedding_model_name=model_name,
            embedding_cache_enabled=False,
            retrieval_cache_enabled=True,
            collection_name=collection_name,
            top_k=top_k,
            qdrant_url="http://localhost:6333",
            qdrant_timeout_seconds=5.0,
            qdrant_max_retries=1,
            user_roles=["reader"],
        )

    assert first_results == second_results

    mock_embed_query.assert_called_once()

    mock_get_qdrant_client.assert_called_once()

    mock_qdrant_client.query_points.assert_called_once()


def test_authorization_filter_is_sent_to_qdrant() -> None:
    mock_client = MagicMock()

    # Qdrant returns no results.
    mock_client.query_points.return_value.points = []

    # Fake query embedding so the real embedding model
    # does not run during this unit test.
    fake_query_vector = [
        0.1,
        0.2,
        0.3,
    ]

    with (
        patch(
            "ai_it_support_assistant.services.retrieval_service.get_qdrant_client",
            return_value=mock_client,
        ),
        patch(
            "ai_it_support_assistant.services.retrieval_service.embed_query",
            return_value=fake_query_vector,
        ),
    ):
        retrieve_chunks(
            query="VPN",
            top_k=3,
            embedding_model_name="test-model",
            embedding_cache_enabled=False,
            retrieval_cache_enabled=False,
            qdrant_url="http://localhost:6333",
            collection_name="test_chunks",
            qdrant_timeout_seconds=5.0,
            qdrant_max_retries=1,
            user_roles=["reader"],
        )

    mock_client.query_points.assert_called_once()

    kwargs = mock_client.query_points.call_args.kwargs

    assert "query_filter" in kwargs
    assert kwargs["query_filter"] is not None
