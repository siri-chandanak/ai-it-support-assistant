from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.schemas.document import DocumentUploadResponse
from ai_it_support_assistant.services.chunking_service import ChunkingError
from ai_it_support_assistant.services.document_service import (
    DocumentTooLargeError,
    InvalidDocumentError,
)
from ai_it_support_assistant.services.ingestion_service import ingest_document
from ai_it_support_assistant.services.text_extraction_service import (
    TextExtractionError,
)

router = APIRouter()


@router.post(
    "/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: Annotated[UploadFile, File()],
) -> DocumentUploadResponse:
    settings = get_settings()

    try:
        document, size_bytes = await ingest_document(
            file=file,
            storage_path=settings.document_storage_path,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    except InvalidDocumentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    except DocumentTooLargeError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e),
        ) from e

    except TextExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    except ChunkingError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document chunking failed.",
        ) from exc

    return DocumentUploadResponse(
        document_id=document.document_id,
        filename=document.filename,
        content_type=document.content_type,
        size_bytes=size_bytes,
        character_count=document.character_count,
        chunk_count=len(document.chunks),
        status="processed",
    )
