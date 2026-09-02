from openai import OpenAI

from ai_it_support_assistant.core.config import get_settings

settings = get_settings()

client = OpenAI(api_key=settings.openai_api_key)

response = client.responses.create(
    model=settings.llm_model,
    input="Reply with exactly: OpenAI connection works",
)

print(response.output_text)
