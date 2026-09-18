import logging
import time

from opentelemetry.trace import Status, StatusCode

from ai_it_support_assistant.core.request_context import (
    get_request_id,
)
from ai_it_support_assistant.observability.metrics import (
    RAG_ABSTENTIONS,
    RAG_DURATION,
)
from ai_it_support_assistant.observability.tracing import get_tracer
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

logger = logging.getLogger(__name__)


tracer = get_tracer()


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


def normalize_grounded_output(
    output: GroundedLLMOutput,
) -> GroundedLLMOutput:
    if output.insufficient_context and output.cited_source_numbers:
        return output.model_copy(
            update={
                "cited_source_numbers": [],
            }
        )

    return output


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
    embedding_cache_enabled: bool,
    retrieval_cache_enabled: bool,
    qdrant_url: str,
    collection_name: str,
    openai_api_key: str,
    llm_model: str,
    qdrant_timeout_seconds: float,
    qdrant_max_attempts: int,
    openai_timeout_seconds: float,
    openai_max_retries: int,
    user_roles: list[str],
) -> RAGResponse:
    rag_start = time.perf_counter()

    # Prometheus outcome.
    #
    # Default to "error" so that if anything fails before we explicitly
    # classify the request, the finally block records it correctly.
    outcome = "error"

    with tracer.start_as_current_span("rag.answer") as rag_span:
        rag_span.set_attribute(
            "rag.top_k",
            top_k,
        )
        rag_span.set_attribute(
            "rag.score_threshold",
            score_threshold,
        )
        rag_span.set_attribute(
            "rag.user_role_count",
            len(user_roles),
        )
        rag_span.set_attribute(
            "rag.embedding_cache_enabled",
            embedding_cache_enabled,
        )
        rag_span.set_attribute(
            "rag.retrieval_cache_enabled",
            retrieval_cache_enabled,
        )

        logger.info(
            ("rag_started request_id=%s question_length=%s top_k=%s score_threshold=%s"),
            get_request_id(),
            len(question),
            top_k,
            score_threshold,
        )

        try:
            retrieved_chunks = retrieve_chunks(
                query=question,
                top_k=top_k,
                embedding_model_name=embedding_model_name,
                embedding_cache_enabled=embedding_cache_enabled,
                retrieval_cache_enabled=retrieval_cache_enabled,
                qdrant_url=qdrant_url,
                collection_name=collection_name,
                qdrant_timeout_seconds=qdrant_timeout_seconds,
                qdrant_max_retries=qdrant_max_attempts,
                user_roles=user_roles,
            )

            rag_span.set_attribute(
                "rag.retrieved_count",
                len(retrieved_chunks),
            )

            with tracer.start_as_current_span("rag.filter") as filter_span:
                relevant_chunks = [
                    chunk for chunk in retrieved_chunks if chunk.score >= score_threshold
                ]

                filter_span.set_attribute(
                    "rag.filter.input_count",
                    len(retrieved_chunks),
                )
                filter_span.set_attribute(
                    "rag.filter.output_count",
                    len(relevant_chunks),
                )
                filter_span.set_attribute(
                    "rag.filter.score_threshold",
                    score_threshold,
                )

            rag_span.set_attribute(
                "rag.relevant_count",
                len(relevant_chunks),
            )

            logger.info(
                (
                    "retrieval_filtered "
                    "request_id=%s "
                    "retrieved_count=%s "
                    "relevant_count=%s "
                    "score_threshold=%s"
                ),
                get_request_id(),
                len(retrieved_chunks),
                len(relevant_chunks),
                score_threshold,
            )

            # ========================================================
            # RETRIEVAL ABSTENTION
            # ========================================================

            if not relevant_chunks:
                outcome = "retrieval_abstention"

                # Prometheus
                RAG_ABSTENTIONS.labels(
                    reason="retrieval",
                ).inc()

                # OpenTelemetry
                rag_span.set_attribute(
                    "rag.insufficient_context",
                    True,
                )
                rag_span.set_attribute(
                    "rag.outcome",
                    outcome,
                )

                rag_span.add_event(
                    "rag_abstained",
                    {
                        "reason": "no_chunks_above_threshold",
                    },
                )

                logger.info(
                    ("rag_abstained request_id=%s reason=no_chunks_above_threshold"),
                    get_request_id(),
                )

                return RAGResponse(
                    question=question,
                    answer=(
                        "I couldn't find sufficiently relevant "
                        "information in the available support "
                        "documentation."
                    ),
                    insufficient_context=True,
                    sources=[],
                    retrieved_chunks=retrieved_chunks,
                )

            context = build_context(relevant_chunks)

            rag_span.set_attribute(
                "rag.context_character_count",
                len(context),
            )

            try:
                llm_start = time.perf_counter()

                llm_output = generate_grounded_answer(
                    question=question,
                    context=context,
                    api_key=openai_api_key,
                    model_name=llm_model,
                    timeout_seconds=(openai_timeout_seconds),
                    max_retries=(openai_max_retries),
                )

                llm_duration_ms = (time.perf_counter() - llm_start) * 1000

                llm_output = normalize_grounded_output(llm_output)

                validate_grounded_output(
                    llm_output=llm_output,
                    chunk_count=len(relevant_chunks),
                )

                logger.info(
                    (
                        "llm_completed "
                        "request_id=%s "
                        "duration_ms=%.2f "
                        "insufficient_context=%s "
                        "citation_count=%s"
                    ),
                    get_request_id(),
                    llm_duration_ms,
                    llm_output.insufficient_context,
                    len(llm_output.cited_source_numbers),
                )

                # ====================================================
                # SUFFICIENCY ABSTENTION
                # ====================================================

                if llm_output.insufficient_context:
                    outcome = "sufficiency_abstention"

                    # Prometheus
                    RAG_ABSTENTIONS.labels(
                        reason="sufficiency",
                    ).inc()

                    # OpenTelemetry
                    rag_span.set_attribute(
                        "rag.insufficient_context",
                        True,
                    )
                    rag_span.set_attribute(
                        "rag.outcome",
                        outcome,
                    )

                    rag_span.add_event(
                        "rag_abstained",
                        {
                            "reason": "insufficient_evidence",
                        },
                    )

                    logger.info(
                        ("rag_abstained request_id=%s reason=insufficient_evidence"),
                        get_request_id(),
                    )

                else:
                    # Normal successful answer.
                    outcome = "answered"

            except LLMError as exc:
                outcome = "error"

                rag_span.record_exception(exc)

                rag_span.set_status(
                    Status(
                        StatusCode.ERROR,
                        "LLM generation failed",
                    )
                )

                rag_span.set_attribute(
                    "rag.outcome",
                    outcome,
                )

                raise

            except RAGError as exc:
                outcome = "error"

                rag_span.record_exception(exc)

                rag_span.set_status(
                    Status(
                        StatusCode.ERROR,
                        "RAG validation failed",
                    )
                )

                rag_span.set_attribute(
                    "rag.outcome",
                    outcome,
                )

                raise

            except Exception as exc:
                outcome = "error"

                rag_span.record_exception(exc)

                rag_span.set_status(
                    Status(
                        StatusCode.ERROR,
                        "Unexpected RAG generation failure",
                    )
                )

                rag_span.set_attribute(
                    "rag.outcome",
                    outcome,
                )

                logger.exception(
                    "rag_generation_failed request_id=%s error_type=%s",
                    get_request_id(),
                    type(exc).__name__,
                )

                raise RAGError("Failed to generate grounded RAG answer.") from exc

            sources = build_sources_from_citations(
                chunks=relevant_chunks,
                cited_source_numbers=(llm_output.cited_source_numbers),
            )

            rag_duration_ms = (time.perf_counter() - rag_start) * 1000

            rag_span.set_attribute(
                "rag.source_count",
                len(sources),
            )

            rag_span.set_attribute(
                "rag.citation_count",
                len(llm_output.cited_source_numbers),
            )

            rag_span.set_attribute(
                "rag.insufficient_context",
                llm_output.insufficient_context,
            )

            # If it wasn't a sufficiency abstention,
            # outcome was set to "answered" above.
            rag_span.set_attribute(
                "rag.outcome",
                outcome,
            )

            rag_span.add_event(
                "rag_completed",
                {
                    "source_count": len(sources),
                    "insufficient_context": llm_output.insufficient_context,
                },
            )

            logger.info(
                (
                    "rag_completed "
                    "request_id=%s "
                    "duration_ms=%.2f "
                    "source_count=%s "
                    "insufficient_context=%s"
                ),
                get_request_id(),
                rag_duration_ms,
                len(sources),
                llm_output.insufficient_context,
            )

            return RAGResponse(
                question=question,
                answer=llm_output.answer,
                insufficient_context=(llm_output.insufficient_context),
                sources=sources,
                retrieved_chunks=(retrieved_chunks),
            )

        except (LLMError, RAGError) as exc:
            # outcome should already be "error",
            # but explicitly keep this safe.
            outcome = "error"

            rag_span.record_exception(exc)

            rag_span.set_status(
                Status(
                    StatusCode.ERROR,
                    "RAG pipeline failed",
                )
            )

            rag_span.set_attribute(
                "rag.outcome",
                outcome,
            )

            logger.exception(
                "rag_failed request_id=%s error_type=%s",
                get_request_id(),
                type(exc).__name__,
            )

            raise

        except Exception as exc:
            outcome = "error"

            rag_span.record_exception(exc)

            rag_span.set_status(
                Status(
                    StatusCode.ERROR,
                    "RAG pipeline failed",
                )
            )

            rag_span.set_attribute(
                "rag.outcome",
                outcome,
            )

            logger.exception(
                "rag_failed request_id=%s error_type=%s",
                get_request_id(),
                type(exc).__name__,
            )

            raise

        finally:
            # ========================================================
            # PROMETHEUS: COMPLETE RAG PIPELINE DURATION
            # ========================================================

            RAG_DURATION.labels(
                outcome=outcome,
            ).observe(time.perf_counter() - rag_start)
