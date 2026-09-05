from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from tenacity import (
    Retrying,
    stop_after_attempt,
    wait_none,
)

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
            qdrant_url="http://test-qdrant:6333",
            collection_name="test_chunks",
            qdrant_timeout_seconds=5.0,
            qdrant_max_retries=3,
            openai_timeout_seconds=10.0,
            openai_max_retries=2,
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
                qdrant_url="http://test",
                collection_name="test",
                qdrant_timeout_seconds=5.0,
                qdrant_max_retries=3,
                openai_timeout_seconds=10.0,
                openai_max_retries=2,
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
            )

    assert mock_client.query_points.call_count == 3
