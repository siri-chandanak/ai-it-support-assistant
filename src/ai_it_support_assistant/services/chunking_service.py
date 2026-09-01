from ai_it_support_assistant.schemas.document import DocumentChunk


class ChunkingError(Exception):
    pass


def chunk_text(
    *,
    document_id: str,
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[DocumentChunk]:
    if chunk_size <= 0:
        raise ChunkingError("chunk_size must be greater than zero.")

    if chunk_overlap < 0:
        raise ChunkingError("chunk_overlap cannot be negative.")

    if chunk_overlap >= chunk_size:
        raise ChunkingError("chunk_overlap must be smaller than chunk_size.")

    cleaned_text = text.strip()

    if not cleaned_text:
        raise ChunkingError("Cannot chunk empty text.")

    chunks: list[DocumentChunk] = []

    start = 0
    chunk_index = 0

    while start < len(cleaned_text):
        end = min(start + chunk_size, len(cleaned_text))

        chunk_content = cleaned_text[start:end].strip()

        if chunk_content:
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{document_id}:{chunk_index}",
                    document_id=document_id,
                    chunk_index=chunk_index,
                    text=chunk_content,
                    character_count=len(chunk_content),
                )
            )

            chunk_index += 1

        if end == len(cleaned_text):
            break

        start = end - chunk_overlap

    return chunks
