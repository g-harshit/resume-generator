import logging

import openai

from app.config import get_settings

from .base import AIProvider, AIProviderError

log = logging.getLogger(__name__)

# Written for the user: they see this when a call fails.
_TRY_AGAIN = "The AI service didn't respond properly. Please try again in a minute."


# Low temperature where wording must stay close to the person's own: less drift, fewer
# embellishments for the guard to revert. Reasoning models refuse the parameter; then
# it's dropped and the call retried once.
# Reasoning models think briefly on tasks where a person is waiting on one line.
_REASONING = {"keyword_rewrite": "low"}
_TEMPERATURE = {
    "tailor": 0.3,
    "write_summary": 0.3,
    "repair_tailoring": 0.0,
    "verify_tailoring": 0.0,
    "bridge_claims": 0.0,
    "judge_bridge_claims": 0.0,
    "bridge_rewrite": 0.0,
    "verify_bridge_rewrite": 0.0,
}


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
            "tailor": settings.openai_tailor_model,
            "write_summary": settings.openai_tailor_model,
            "verify_tailoring": settings.openai_tailor_model,
            "repair_tailoring": settings.openai_tailor_model,
            "bridge_claims": settings.openai_tailor_model,
            "judge_bridge_claims": settings.openai_tailor_model,
            "bridge_rewrite": settings.openai_tailor_model,
            "verify_bridge_rewrite": settings.openai_tailor_model,
            "keyword_rewrite": settings.openai_keywords_model,
        }

    def _call(self, task: str, instructions: str, text: str, schema, temperature):
        return self._client.responses.parse(
            model=self._models[task],
            instructions=instructions,
            input=text,
            text_format=schema,
            # Resumes are personal data: don't let OpenAI keep the conversation.
            store=False,
            **({"temperature": temperature} if temperature is not None else {}),
            **({"reasoning": {"effort": _REASONING[task]}} if task in _REASONING else {}),
        )

    def extract[T](self, *, task: str, instructions: str, text: str, schema: type[T]) -> T:
        temperature = _TEMPERATURE.get(task)
        try:
            try:
                response = self._call(task, instructions, text, schema, temperature)
            except openai.BadRequestError as exc:
                if temperature is None or "temperature" not in str(exc):
                    raise
                response = self._call(task, instructions, text, schema, None)
        except openai.OpenAIError as exc:
            log.warning("OpenAI %s failed: %s", task, exc)
            raise AIProviderError(_TRY_AGAIN) from exc

        parsed = response.output_parsed
        if parsed is None:  # refusal, or output cut off before it was valid JSON
            log.warning("OpenAI %s gave nothing parseable: %s", task, response.output_text[:200])
            raise AIProviderError(_TRY_AGAIN)
        return parsed
