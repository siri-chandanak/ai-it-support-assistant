from fastapi import UploadFile

from ai_it_support_assistant.cache.cache_service import (
    clear_retrieval_cache,
)
from ai_it_support_assistant.schemas.document import ExtractedDocument
from ai_it_support_assistant.services.chunking_service import chunk_text
from ai_it_support_assistant.services.document_service import save_document
from ai_it_support_assistant.services.embedding_service import embed_chunks
from ai_it_support_assistant.services.text_extraction_service import extract_text
from ai_it_support_assistant.services.vector_store_service import (
    store_chunk_vectors,
)


async def ingest_document(
    *,
    file: UploadFile,
    storage_path: str,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model_name: str,
    qdrant_url: str,
    qdrant_collection_name: str,
    qdrant_timeout_seconds: float,
) -> tuple[ExtractedDocument, int, int]:
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

        embeddings = embed_chunks(
            chunks=chunks,
            model_name=embedding_model_name,
        )

        indexed_chunk_count = store_chunk_vectors(
            chunks=chunks,
            embeddings=embeddings,
            qdrant_url=qdrant_url,
            collection_name=qdrant_collection_name,
            qdrant_timeout_seconds=qdrant_timeout_seconds,
        )

        clear_retrieval_cache()

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

    return document, size_bytes, indexed_chunk_count
