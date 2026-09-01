from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.schemas.document import DocumentUploadResponse
from ai_it_support_assistant.services.document_service import (
    DocumentTooLargeError,
    InvalidDocumentError,
    save_document,
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
        document_id, _, size_bytes = await save_document(
            file=file, storage_path=settings.document_storage_path
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

    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename or "",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=size_bytes,
        status="saved successfully",
    )
