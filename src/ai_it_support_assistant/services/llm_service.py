import logging
import time
from functools import lru_cache

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)
from opentelemetry.trace import Status, StatusCode

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.core.request_context import (
    get_request_id,
)
from ai_it_support_assistant.observability.metrics import (
    LLM_DURATION,
    LLM_ESTIMATED_COST_TOTAL,
    LLM_FAILURES,
    LLM_INPUT_TOKENS,
    LLM_OUTPUT_TOKENS,
    LLM_REQUESTS,
)
from ai_it_support_assistant.observability.tracing import (
    get_tracer,
)
from ai_it_support_assistant.schemas.rag import GroundedLLMOutput
from ai_it_support_assistant.services.cost_estimation_service import (
    estimate_llm_cost,
)

logger = logging.getLogger(__name__)
tracer = get_tracer()


class LLMError(Exception):
    pass


class LLMTimeoutError(LLMError):
    pass


class LLMRateLimitError(LLMError):
    pass


class LLMAuthenticationError(LLMError):
    pass


class LLMUnavailableError(LLMError):
    pass


@lru_cache
def get_openai_client(
    api_key: str,
    timeout_seconds: float,
    max_retries: int,
) -> OpenAI:
    if not api_key.strip():
        raise LLMError("OpenAI API key is not configured.")

    return OpenAI(
        api_key=api_key,
        timeout=timeout_seconds,
        max_retries=max_retries,
    )


def generate_grounded_answer(
    *,
    question: str,
    context: str,
    api_key: str,
    model_name: str,
    timeout_seconds: float,
    max_retries: int,
) -> GroundedLLMOutput:
    if not question.strip():
        raise LLMError("Question cannot be empty.")

    if not context.strip():
        raise LLMError("RAG context cannot be empty.")

    logger.info(
        ("llm_request_started request_id=%s model=%s context_characters=%s"),
        get_request_id(),
        model_name,
        len(context),
    )

    client = get_openai_client(
        api_key,
        timeout_seconds,
        max_retries,
    )

    instructions = """
You are an AI IT Support Assistant.

Answer the user's question using only the provided company
support context.

Rules:
1. Use only facts supported by the supplied sources.
2. Do not use outside knowledge.
3. Do not invent missing procedures, commands, credentials,
   policies, URLs, people, or system states.
4. Every factual answer must cite the source numbers that
   support it.
5. Source numbers must refer only to sources provided in the
   context.
6. Set insufficient_context to true only when the supplied
   sources do not contain enough evidence to provide any
   meaningful grounded answer.

   If the sources support a partial but useful answer, provide
   only the supported information, set insufficient_context to
   false, and cite the supporting sources.

   Do not mark the context insufficient merely because some
   details, examples, commands, OS-specific steps, or a complete
   procedure are missing.
7. Do not claim that you executed an action.
""".strip()

    input_text = f"""
Question:
{question}

Company support context:
{context}
""".strip()

    with tracer.start_as_current_span("llm.generate") as span:
        # Safe tracing attributes only.
        span.set_attribute(
            "llm.provider",
            "openai",
        )
        span.set_attribute(
            "llm.model",
            model_name,
        )
        span.set_attribute(
            "llm.context_character_count",
            len(context),
        )

        # ----------------------------------------------------
        # Prometheus request counter
        # ----------------------------------------------------

        LLM_REQUESTS.labels(
            model=model_name,
        ).inc()

        llm_start_time = time.perf_counter()

        try:
            response = client.responses.create(
                model=model_name,
                instructions=instructions,
                input=input_text,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": ("grounded_rag_answer"),
                        "strict": True,
                        "schema": (GroundedLLMOutput.model_json_schema()),
                    }
                },
            )

        except AuthenticationError as exc:
            LLM_FAILURES.labels(
                model=model_name,
            ).inc()

            span.set_attribute(
                "llm.error_type",
                "authentication",
            )
            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "LLM authentication failure",
                )
            )

            logger.error(
                ("llm_authentication_failed request_id=%s"),
                get_request_id(),
            )

            raise LLMAuthenticationError("LLM provider authentication failed.") from exc

        except RateLimitError as exc:
            LLM_FAILURES.labels(
                model=model_name,
            ).inc()

            span.set_attribute(
                "llm.error_type",
                "rate_limit",
            )
            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "LLM rate limit",
                )
            )

            logger.warning(
                ("llm_rate_limited request_id=%s"),
                get_request_id(),
            )

            raise LLMRateLimitError("LLM provider rate limit exceeded.") from exc

        except APITimeoutError as exc:
            LLM_FAILURES.labels(
                model=model_name,
            ).inc()

            span.set_attribute(
                "llm.error_type",
                "timeout",
            )
            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "LLM timeout",
                )
            )

            logger.warning(
                ("llm_timeout request_id=%s"),
                get_request_id(),
            )

            raise LLMTimeoutError("LLM provider request timed out.") from exc

        except APIConnectionError as exc:
            LLM_FAILURES.labels(
                model=model_name,
            ).inc()

            span.set_attribute(
                "llm.error_type",
                "connection",
            )
            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "LLM connection failure",
                )
            )

            logger.error(
                ("llm_connection_failed request_id=%s"),
                get_request_id(),
            )

            raise LLMUnavailableError("Unable to connect to LLM provider.") from exc

        except APIStatusError as exc:
            LLM_FAILURES.labels(
                model=model_name,
            ).inc()

            span.set_attribute(
                "llm.error_type",
                "api_status",
            )
            span.set_attribute(
                "llm.status_code",
                exc.status_code,
            )
            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "LLM provider API failure",
                )
            )

            logger.error(
                ("llm_api_status_error request_id=%s status_code=%s"),
                get_request_id(),
                exc.status_code,
            )

            raise LLMUnavailableError(f"LLM provider returned status {exc.status_code}.") from exc

        except Exception as exc:
            LLM_FAILURES.labels(
                model=model_name,
            ).inc()

            span.set_attribute(
                "llm.error_type",
                "unexpected",
            )
            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "Unexpected LLM failure",
                )
            )

            logger.error(
                ("llm_unexpected_error request_id=%s error_type=%s"),
                get_request_id(),
                type(exc).__name__,
            )

            raise LLMError("Failed to generate LLM response.") from exc

        finally:
            # Measure provider latency for success and failure.
            LLM_DURATION.labels(
                model=model_name,
            ).observe(time.perf_counter() - llm_start_time)

        # ----------------------------------------------------
        # Token usage
        # ----------------------------------------------------

        usage = getattr(
            response,
            "usage",
            None,
        )

        if usage is not None:
            input_tokens = getattr(
                usage,
                "input_tokens",
                None,
            )

            output_tokens = getattr(
                usage,
                "output_tokens",
                None,
            )

            if input_tokens is not None:
                span.set_attribute(
                    "llm.input_tokens",
                    input_tokens,
                )

                LLM_INPUT_TOKENS.labels(
                    model=model_name,
                    operation="rag_answer",
                ).inc(input_tokens)

            if output_tokens is not None:
                span.set_attribute(
                    "llm.output_tokens",
                    output_tokens,
                )

                LLM_OUTPUT_TOKENS.labels(
                    model=model_name,
                    operation="rag_answer",
                ).inc(output_tokens)

            if input_tokens is not None and output_tokens is not None:
                settings = get_settings()

                estimated_cost = estimate_llm_cost(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    input_rate=(settings.llm_input_cost_per_million_tokens),
                    output_rate=(settings.llm_output_cost_per_million_tokens),
                )

                LLM_ESTIMATED_COST_TOTAL.labels(
                    model=model_name,
                    operation="rag_answer",
                ).inc(estimated_cost)

                span.set_attribute(
                    "llm.estimated_cost",
                    estimated_cost,
                )

        # ----------------------------------------------------
        # Empty response handling
        # ----------------------------------------------------

        if not response.output_text.strip():
            LLM_FAILURES.labels(
                model=model_name,
            ).inc()

            span.set_attribute(
                "llm.error_type",
                "empty_response",
            )

            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "LLM returned empty response",
                )
            )

            raise LLMError("LLM returned an empty response.")

        # ----------------------------------------------------
        # Structured output validation
        # ----------------------------------------------------

        try:
            grounded_output = GroundedLLMOutput.model_validate_json(response.output_text)

        except Exception as exc:
            LLM_FAILURES.labels(
                model=model_name,
            ).inc()

            span.set_attribute(
                "llm.error_type",
                "invalid_structured_output",
            )

            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "Invalid structured LLM output",
                )
            )

            raise LLMError("LLM returned invalid structured output.") from exc

        # ----------------------------------------------------
        # Successful result tracing
        # ----------------------------------------------------

        span.set_attribute(
            "llm.insufficient_context",
            grounded_output.insufficient_context,
        )

        span.set_attribute(
            "llm.outcome",
            ("insufficient_context" if grounded_output.insufficient_context else "answered"),
        )

        logger.info(
            ("llm_request_completed request_id=%s model=%s insufficient_context=%s"),
            get_request_id(),
            model_name,
            grounded_output.insufficient_context,
        )

        return grounded_output
