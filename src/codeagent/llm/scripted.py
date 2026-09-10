from __future__ import annotations

from collections import deque
import copy
from collections.abc import Sequence
from typing import Any

from codeagent.llm.base import ModelProvider
from codeagent.models import ModelTurn


class ScriptedProvider(ModelProvider):
    """Deterministic provider for tests and local demos without an API key."""

    def __init__(self, turns: Sequence[ModelTurn]) -> None:
        self.turns = deque(turns)
        self.requests: list[dict[str, Any]] = []

    async def complete(self, *, messages, system, tools, max_tokens) -> ModelTurn:
        self.requests.append(
            {"messages": copy.deepcopy(messages), "system": system, "tools": copy.deepcopy(list(tools)), "max_tokens": max_tokens}
        )
        if not self.turns:
            return ModelTurn(blocks=[{"type": "text", "text": "done"}], text="done")
        return self.turns.popleft()
