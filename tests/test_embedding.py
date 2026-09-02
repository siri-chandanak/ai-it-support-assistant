from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ai_it_support_assistant.schemas.document import DocumentChunk
from ai_it_support_assistant.services.embedding_service import EmbeddingError, embed_chunks


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
