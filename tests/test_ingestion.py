from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import UploadFile

from ai_it_support_assistant.services.ingestion_service import ingest_document


@pytest.mark.asyncio
async def test_ingestion_creates_chunks(tmp_path: Path) -> None:
    file_path = tmp_path / "input.txt"
    file_path.write_text(
        "A" * 2500,
        encoding="utf-8",
    )

    with file_path.open("rb") as file_handle:
        upload = UploadFile(
            filename="input.txt",
            file=file_handle,
        )

        with (
            patch(
                "ai_it_support_assistant.services.ingestion_service.embed_chunks",
                return_value=[
                    [0.1, 0.2, 0.3],
                    [0.4, 0.5, 0.6],
                    [0.7, 0.8, 0.9],
                ],
            ),
            patch(
                "ai_it_support_assistant.services.ingestion_service.store_chunk_vectors",
                return_value=3,
            ),
        ):
            document, size_bytes, indexed_chunk_count = await ingest_document(
                file=upload,
                storage_path=str(tmp_path / "stored"),
                chunk_size=1000,
                chunk_overlap=200,
                embedding_model_name="test-model",
                qdrant_url="http://localhost:6333",
                qdrant_collection_name="test_chunks",
                qdrant_timeout_seconds=5.0,
            )

    assert size_bytes == 2500
    assert document.character_count == 2500
    assert len(document.chunks) == 3
    assert indexed_chunk_count == 3
