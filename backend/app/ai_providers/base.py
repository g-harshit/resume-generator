"""The contract every AI vendor integration implements.

One method, `extract`: instructions + input text in, an instance of a Pydantic model
out, validated. Prompts live with the feature that uses them (`services/parse_resume.py`),
never here, so adding a feature never means adding a provider method.
"""

from abc import ABC, abstractmethod


class AIProviderError(Exception):
    """The vendor failed or refused. `str(error)` is safe to show the user."""


class AIProvider(ABC):
    name: str

    @abstractmethod
    def extract[T](self, *, task: str, instructions: str, text: str, schema: type[T]) -> T:
        """Return `schema` filled from `text`.

        `task` names the call ("parse_resume", ...) so a provider can pick a model per
        task and the stub can route canned answers.
        """
