from app.config import get_settings

from .base import AIProvider, AIProviderError


def get_ai_provider() -> AIProvider:
    name = get_settings().ai_provider.lower()
    if name == "openai":
        from .openai import OpenAIProvider

        return OpenAIProvider()
    if name == "stub":
        from .stub import StubProvider

        return StubProvider()
    raise AIProviderError(f"Unknown AI_PROVIDER {name!r}: use 'openai' or 'stub'")


__all__ = ["AIProvider", "AIProviderError", "get_ai_provider"]
