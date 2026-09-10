from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from codeagent.models import ModelTurn


class ModelProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str,
        tools: Sequence[dict[str, Any]],
        max_tokens: int,
    ) -> ModelTurn:
        raise NotImplementedError
