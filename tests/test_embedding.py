from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ai_it_support_assistant.cache.cache_service import (
    build_embedding_cache_key,
    configure_embedding_cache,
    set_cached_embedding,
)
from ai_it_support_assistant.schemas.document import DocumentChunk
from ai_it_support_assistant.services.embedding_service import (
    EmbeddingError,
    embed_chunks,
    embed_query,
)


def test_embed_chunks_returns_vectors() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="doc-1:0",
            document_id="doc-1",
            chunk_index=0,
            text="Restart the VPN client.",
            character_count=23,
        ),
        DocumentChunk(
            chunk_id="doc-1:1",
            document_id="doc-1",
            chunk_index=1,
            text="Reset your MFA token.",
            character_count=21,
        ),
    ]

    mock_model = MagicMock()
    mock_model.encode.return_value = np.array(
        [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
        ]
    )

    with patch(
        "ai_it_support_assistant.services.embedding_service.get_embedding_model",
        return_value=mock_model,
    ):
        embeddings = embed_chunks(
            chunks=chunks,
            model_name="test-model",
        )

    assert embeddings == [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
    ]

    mock_model.encode.assert_called_once()


def test_embed_chunks_rejects_empty_list() -> None:
    with pytest.raises(
        EmbeddingError,
        match="Cannot embed an empty chunk list",
    ):
        embed_chunks(
            chunks=[],
            model_name="test-model",
        )


def test_embed_query_returns_vector() -> None:
    mock_model = MagicMock()

    mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])

    with patch(
        "ai_it_support_assistant.services.embedding_service.get_embedding_model",
        return_value=mock_model,
    ):
        vector = embed_query(
            query="How do I restart VPN?",
            model_name="test-model",
            cache_enabled=False,
        )

    assert vector == [0.1, 0.2, 0.3]

    mock_model.encode.assert_called_once_with(
        "How do I restart VPN?",
        normalize_embeddings=True,
    )


def test_embed_query_rejects_empty_query() -> None:
    with pytest.raises(
        EmbeddingError,
        match="Cannot embed an empty query",
    ):
        embed_query(
            query="   ",
            model_name="test-model",
            cache_enabled=False,
        )


def test_embed_query_uses_cache() -> None:
    configure_embedding_cache(
        max_size=100,
        ttl_seconds=300,
    )
    query = "How do I restart VPN?"
    model_name = "test-model"

    cache_key = build_embedding_cache_key(
        query=query,
        model_name=model_name,
    )

    expected_vector = [0.1, 0.2, 0.3]

    set_cached_embedding(
        key=cache_key,
        embedding=expected_vector,
    )

    with patch(
        "ai_it_support_assistant.services.embedding_service.get_embedding_model"
    ) as mock_model_loader:
        vector = embed_query(
            query=query,
            model_name=model_name,
            cache_enabled=True,
        )

    assert vector == expected_vector
    mock_model_loader.assert_not_called()
