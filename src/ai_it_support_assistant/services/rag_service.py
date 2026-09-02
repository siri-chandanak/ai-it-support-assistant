from ai_it_support_assistant.schemas.rag import (
    RAGResponse,
    RAGSource,
)
from ai_it_support_assistant.services.llm_service import (
    generate_grounded_answer,
)
from ai_it_support_assistant.services.retrieval_service import (
    retrieve_chunks,
)


class RAGError(Exception):
    pass


def build_context(
    chunks: list,
) -> str:
    if not chunks:
        return ""

    sections: list[str] = []

    for index, chunk in enumerate(chunks, start=1):
        sections.append(
            "\n".join(
                [
                    f"[Source {index}]",
                    f"Document ID: {chunk.document_id}",
                    f"Chunk ID: {chunk.chunk_id}",
                    f"Chunk Index: {chunk.chunk_index}",
                    f"Content: {chunk.text}",
                ]
            )
        )

    return "\n\n".join(sections)


def answer_question(
    *,
    question: str,
    top_k: int,
    score_threshold: float,
    embedding_model_name: str,
    qdrant_url: str,
    collection_name: str,
    openai_api_key: str,
    llm_model: str,
) -> RAGResponse:
    retrieved_chunks = retrieve_chunks(
        query=question,
        top_k=top_k,
        embedding_model_name=embedding_model_name,
        qdrant_url=qdrant_url,
        collection_name=collection_name,
    )

    relevant_chunks = [chunk for chunk in retrieved_chunks if chunk.score >= score_threshold]

    if not relevant_chunks:
        return RAGResponse(
            question=question,
            answer=(
                "I couldn't find sufficiently relevant information "
                "in the available support documentation."
            ),
            sources=[],
            retrieved_chunks=retrieved_chunks,
        )

    context = build_context(relevant_chunks)

    try:
        answer = generate_grounded_answer(
            question=question,
            context=context,
            api_key=openai_api_key,
            model_name=llm_model,
        )
    except Exception as exc:
        raise RAGError("Failed to generate RAG answer.") from exc

    sources = [
        RAGSource(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            score=chunk.score,
        )
        for chunk in retrieved_chunks
    ]

    return RAGResponse(
        question=question,
        answer=answer,
        sources=sources,
        retrieved_chunks=retrieved_chunks,
    )
