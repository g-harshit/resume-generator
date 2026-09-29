"""A provider that answers from code, for tests (and offline development).

Tests register what each task returns:

    stub.answer("parse_resume", lambda text: ParsedResume(...))
    stub.answer("parse_resume", AIProviderError("down"))   # make it fail
"""

from collections.abc import Callable
from typing import Any

from .base import AIProvider, AIProviderError

_answers: dict[str, Callable[[str], Any] | Exception] = {}
calls: list[dict] = []


def answer(task: str, result: Callable[[str], Any] | Exception) -> None:
    _answers[task] = result


def reset() -> None:
    _answers.clear()
    calls.clear()


class StubProvider(AIProvider):
    name = "stub"

    def extract[T](self, *, task: str, instructions: str, text: str, schema: type[T]) -> T:
        calls.append({"task": task, "instructions": instructions, "text": text})
        result = _answers.get(task)
        if result is None:
            raise AIProviderError(f"stub has no answer for {task!r}")
        if isinstance(result, Exception):
            raise result
        return result(text)
