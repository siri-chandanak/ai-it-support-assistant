from functools import lru_cache

from openai import OpenAI

from ai_it_support_assistant.schemas.rag import GroundedLLMOutput


class LLMError(Exception):
    pass


@lru_cache
def get_openai_client(api_key: str) -> OpenAI:
    if not api_key.strip():
        raise LLMError("OpenAI API key is not configured.")

    return OpenAI(api_key=api_key)


def generate_grounded_answer(
    *,
    question: str,
    context: str,
    api_key: str,
    model_name: str,
) -> GroundedLLMOutput:
    if not question.strip():
        raise LLMError("Question cannot be empty.")

    if not context.strip():
        raise LLMError("RAG context cannot be empty.")

    client = get_openai_client(api_key)

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
6. If the supplied sources do not contain enough information
   to answer the question, set insufficient_context to true,
   provide a short explanation, and return no source numbers.
7. Do not claim that you executed an action.
""".strip()

    input_text = f"""
Question:
{question}

Company support context:
{context}
""".strip()

    try:
        response = client.responses.create(
            model=model_name,
            instructions=instructions,
            input=input_text,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "grounded_rag_answer",
                    "strict": True,
                    "schema": GroundedLLMOutput.model_json_schema(),
                }
            },
        )
    except Exception as exc:
        print(f"OpenAI API error: {type(exc).__name__}: {exc}")

        raise LLMError("Failed to generate LLM response.") from exc

    if not response.output_text.strip():
        raise LLMError("LLM returned an empty response.")

    try:
        return GroundedLLMOutput.model_validate_json(response.output_text)
    except Exception as exc:
        raise LLMError("LLM returned invalid structured output.") from exc
