from unittest.mock import MagicMock, patch

import pytest

from ai_it_support_assistant.schemas.document import DocumentChunk
from ai_it_support_assistant.services.vector_store_service import (
    VectorStoreError,
    store_chunk_vectors,
)


def test_store_chunk_vectors_upserts_points() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="doc-1:0",
            document_id="doc-1",
            chunk_index=0,
            text="Restart VPN.",
            character_count=12,
            allowed_roles=["reader"],
        )
    ]

    embeddings = [[0.1, 0.2, 0.3]]

    mock_client = MagicMock()
    mock_client.collection_exists.return_value = True

    with patch(
        "ai_it_support_assistant.services.vector_store_service.get_qdrant_client",
        return_value=mock_client,
    ):
        stored_count = store_chunk_vectors(
            chunks=chunks,
            embeddings=embeddings,
            qdrant_url="http://test-qdrant:6333",
            collection_name="test_chunks",
            qdrant_timeout_seconds=10.0,
        )

    assert stored_count == 1
    mock_client.upsert.assert_called_once()


def test_store_chunk_vectors_rejects_mismatched_counts() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="doc-1:0",
            document_id="doc-1",
            chunk_index=0,
            text="Restart VPN.",
            character_count=12,
            allowed_roles=["reader"],
        )
    ]

    with pytest.raises(
        VectorStoreError,
        match="Chunk count does not match embedding count",
    ):
        store_chunk_vectors(
            chunks=chunks,
            embeddings=[
                [0.1, 0.2],
                [0.3, 0.4],
            ],
            qdrant_url="http://localhost:6333",
            collection_name="test_chunks",
            qdrant_timeout_seconds=10.0,
        )
