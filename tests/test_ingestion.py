from pathlib import Path

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

        document, size_bytes = await ingest_document(
            file=upload,
            storage_path=str(tmp_path / "stored"),
            chunk_size=1000,
            chunk_overlap=200,
        )

    assert size_bytes == 2500
    assert document.character_count == 2500
    assert len(document.chunks) == 3
