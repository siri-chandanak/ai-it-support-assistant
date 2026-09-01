from fastapi import UploadFile

from ai_it_support_assistant.schemas.document import ExtractedDocument
from ai_it_support_assistant.services.chunking_service import chunk_text
from ai_it_support_assistant.services.document_service import save_document
from ai_it_support_assistant.services.text_extraction_service import extract_text


async def ingest_document(
    file: UploadFile,
    storage_path: str,
    chunk_size: int,
    chunk_overlap: int,
) -> tuple[ExtractedDocument, int]:
    document_id, stored_path, size_bytes = await save_document(
        file=file,
        storage_path=storage_path,
    )

    try:
        text = extract_text(stored_path)

        chunks = chunk_text(
            document_id=document_id,
            text=text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise

    document = ExtractedDocument(
        document_id=document_id,
        filename=file.filename or "",
        content_type=file.content_type or "application/octet-stream",
        text=text,
        character_count=len(text),
        chunks=chunks,
    )

    return document, size_bytes
