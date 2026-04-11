import json
from typing import Any

from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI, RateLimitError

from app.config import settings
from app.errors import ConfigurationError, ModelOutputError, ProviderAuthError, ProviderUnavailableError
from app.schemas import AskResponse

SYSTEM_PROMPT = """You are a helpful assistant.
Return response strictly in JSON format:
{
  \"answer\": \"...\",
  \"confidence\": 0-1
}
"""


def _extract_text_content(response: Any) -> str:
    if hasattr(response, "choices") and response.choices:
        message = response.choices[0].message
        if hasattr(message, "content") and isinstance(message.content, str):
            return message.content
    raise ModelOutputError("No text content found in model response")


def ask_llm(question: str) -> AskResponse:
    if not settings.openai_api_key:
        raise ConfigurationError(
            message="Live answer generation is currently unavailable.",
            hint="Set a valid OPENAI_API_KEY in the backend environment to enable live answers.",
        )

    client = OpenAI(api_key=settings.openai_api_key)
    try:
        completion = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
        )
        content = _extract_text_content(completion)
        payload = json.loads(content)
        return AskResponse.model_validate(payload)
    except AuthenticationError as exc:
        raise ProviderAuthError() from exc
    except (APIConnectionError, RateLimitError) as exc:
        raise ProviderUnavailableError() from exc
    except APIStatusError as exc:
        if exc.status_code in {401, 403}:
            raise ProviderAuthError() from exc
        raise ProviderUnavailableError() from exc
    except json.JSONDecodeError as exc:
        raise ModelOutputError() from exc
