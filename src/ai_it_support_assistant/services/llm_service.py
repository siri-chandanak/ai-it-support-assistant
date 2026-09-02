from functools import lru_cache

from openai import OpenAI


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
) -> str:
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
1. Do not invent information that is not supported by the context.
2. If the context does not contain enough information, say that the
   available documentation does not provide enough information.
3. Do not claim that an action was performed.
4. Keep the answer concise and operationally useful.
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
        )
    except Exception as exc:
        raise LLMError("Failed to generate LLM response.") from exc

    answer = response.output_text.strip()

    if not answer:
        raise LLMError("LLM returned an empty response.")

    return answer
