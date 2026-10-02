import logging

import openai

from app.config import get_settings

from .base import AIProvider, AIProviderError

log = logging.getLogger(__name__)

# Written for the user: they see this when a call fails.
_TRY_AGAIN = "The AI service didn't respond properly. Please try again in a minute."


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise AIProviderError("Resume reading isn't configured yet (OPENAI_API_KEY).")
        self._client = openai.OpenAI(api_key=settings.openai_api_key, timeout=120, max_retries=2)
        self._models = {
            "parse_resume": settings.openai_parse_model,
            "parse_jd": settings.openai_parse_model,
        }

    def extract[T](self, *, task: str, instructions: str, text: str, schema: type[T]) -> T:
        try:
            response = self._client.responses.parse(
                model=self._models[task],
                instructions=instructions,
                input=text,
                text_format=schema,
                # No `temperature`: some OpenAI models reject it, and the model is a setting.
                # Resumes are personal data: don't let OpenAI keep the conversation.
                store=False,
            )
        except openai.OpenAIError as exc:
            log.warning("OpenAI %s failed: %s", task, exc)
            raise AIProviderError(_TRY_AGAIN) from exc

        parsed = response.output_parsed
        if parsed is None:  # refusal, or output cut off before it was valid JSON
            log.warning("OpenAI %s gave nothing parseable: %s", task, response.output_text[:200])
            raise AIProviderError(_TRY_AGAIN)
        return parsed
