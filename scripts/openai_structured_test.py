from openai import OpenAI

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.schemas.rag import GroundedLLMOutput

settings = get_settings()

client = OpenAI(
    api_key=settings.openai_api_key,
)

response = client.responses.create(
    model=settings.llm_model,
    instructions=("Return a grounded test answer. Use Source 1 and mark context as sufficient."),
    input="""
Question:
How do I fix VPN?

Company support context:

[Source 1]
Restart the VPN client.
""",
    text={
        "format": {
            "type": "json_schema",
            "name": "grounded_rag_answer",
            "strict": True,
            "schema": GroundedLLMOutput.model_json_schema(),
        }
    },
)

print("Raw output:")
print(response.output_text)

parsed = GroundedLLMOutput.model_validate_json(response.output_text)

print("\nParsed output:")
print(parsed)
