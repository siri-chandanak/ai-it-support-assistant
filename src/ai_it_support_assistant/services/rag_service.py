from ai_it_support_assistant.schemas.rag import (
    GroundedLLMOutput,
    RAGResponse,
    RAGSource,
)
from ai_it_support_assistant.schemas.retrieval import RetrievedChunk
from ai_it_support_assistant.services.llm_service import (
    LLMError,
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
                    chunk.text,
                ]
            )
        )

    return "\n\n".join(sections)


def validate_cited_sources(
    *,
    cited_source_numbers: list[int],
    chunk_count: int,
) -> None:
    for source_number in cited_source_numbers:
        if source_number < 1 or source_number > chunk_count:
            raise RAGError(f"LLM cited invalid source number: {source_number}")


def validate_grounded_output(
    *,
    llm_output: GroundedLLMOutput,
    chunk_count: int,
) -> None:
    validate_cited_sources(
        cited_source_numbers=llm_output.cited_source_numbers,
        chunk_count=chunk_count,
    )

    if llm_output.insufficient_context and llm_output.cited_source_numbers:
        raise RAGError("LLM cannot cite sources while declaring insufficient context.")

    if not llm_output.insufficient_context and not llm_output.cited_source_numbers:
        raise RAGError("Grounded answer must cite at least one source.")


def build_sources_from_citations(
    *,
    chunks: list[RetrievedChunk],
    cited_source_numbers: list[int],
) -> list[RAGSource]:
    sources: list[RAGSource] = []

    seen_source_numbers: set[int] = set()

    for source_number in cited_source_numbers:
        if source_number in seen_source_numbers:
            continue

        seen_source_numbers.add(source_number)

        chunk = chunks[source_number - 1]

        sources.append(
            RAGSource(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                score=chunk.score,
            )
        )

    return sources


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
    qdrant_timeout_seconds: float,
    qdrant_max_attempts: int,
    openai_timeout_seconds: float,
    openai_max_retries: int,
) -> RAGResponse:
    retrieved_chunks = retrieve_chunks(
        query=question,
        top_k=top_k,
        embedding_model_name=embedding_model_name,
        qdrant_url=qdrant_url,
        collection_name=collection_name,
        qdrant_timeout_seconds=qdrant_timeout_seconds,
        qdrant_max_retries=qdrant_max_attempts,
        openai_timeout_seconds=openai_timeout_seconds,
        openai_max_retries=openai_max_retries,
    )

    relevant_chunks = [chunk for chunk in retrieved_chunks if chunk.score >= score_threshold]

    if not relevant_chunks:
        return RAGResponse(
            question=question,
            answer=(
                "I couldn't find sufficiently relevant information "
                "in the available support documentation."
            ),
            insufficient_context=True,
            sources=[],
            retrieved_chunks=retrieved_chunks,
        )

    context = build_context(relevant_chunks)

    try:
        llm_output = generate_grounded_answer(
            question=question,
            context=context,
            api_key=openai_api_key,
            model_name=llm_model,
            timeout_seconds=openai_timeout_seconds,
            max_retries=openai_max_retries,
        )

        validate_grounded_output(
            llm_output=llm_output,
            chunk_count=len(relevant_chunks),
        )

    except LLMError:
        raise

    except RAGError:
        raise

    except Exception as exc:
        print(f"RAG generation error: {type(exc).__name__}: {exc}")

        raise RAGError("Failed to generate grounded RAG answer.") from exc

    sources = build_sources_from_citations(
        chunks=relevant_chunks,
        cited_source_numbers=llm_output.cited_source_numbers,
    )

    return RAGResponse(
        question=question,
        answer=llm_output.answer,
        insufficient_context=llm_output.insufficient_context,
        sources=sources,
        retrieved_chunks=retrieved_chunks,
    )
