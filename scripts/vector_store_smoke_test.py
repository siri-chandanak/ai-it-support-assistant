from ai_it_support_assistant.schemas.document import DocumentChunk
from ai_it_support_assistant.services.embedding_service import embed_chunks
from ai_it_support_assistant.services.vector_store_service import (
    store_chunk_vectors,
)


def main() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="test-document:0",
            document_id="test-document",
            chunk_index=0,
            text="Restart the VPN client before escalating.",
            character_count=41,
        ),
        DocumentChunk(
            chunk_id="test-document:1",
            document_id="test-document",
            chunk_index=1,
            text="Database passwords must be rotated every 90 days.",
            character_count=49,
        ),
    ]

    embeddings = embed_chunks(
        chunks=chunks,
        model_name="sentence-transformers/all-MiniLM-L6-v2",
    )

    stored_count = store_chunk_vectors(
        chunks=chunks,
        embeddings=embeddings,
        qdrant_url="http://localhost:6333",
        collection_name="document_chunks",
    )

    print(f"Stored vectors: {stored_count}")
    print(f"Vector dimension: {len(embeddings[0])}")


if __name__ == "__main__":
    main()