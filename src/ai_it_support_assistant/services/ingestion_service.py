from fastapi import UploadFile

from ai_it_support_assistant.schemas.document import ExtractedDocument
from ai_it_support_assistant.services.document_service import save_document
from ai_it_support_assistant.services.text_extraction_service import extract_text


async def ingest_document(
    file: UploadFile,
    storage_path: str,
) -> tuple[ExtractedDocument, int]:
    document_id, stored_path, size_bytes = await save_document(
        file=file,
        storage_path=storage_path,
    )

    try:
        text = extract_text(stored_path)
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise

    document = ExtractedDocument(
        document_id=document_id,
        filename=file.filename or "",
        content_type=file.content_type or "application/octet-stream",
        text=text,
        character_count=len(text),
    )

    return document, size_bytes
