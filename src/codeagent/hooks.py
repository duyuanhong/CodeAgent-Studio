from __future__ import annotations

import inspect
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass(slots=True)
class HookDecision:
    blocked: bool = False
    reason: str = ""
    replacement: Any = None


Hook = Callable[..., Any | Awaitable[Any]]


class HookManager:
    EVENTS = (
        "user_prompt_submit",
        "before_model",
        "after_model",
        "pre_tool_use",
        "post_tool_use",
        "stop",
    )

    def __init__(self) -> None:
        self._hooks: dict[str, list[Hook]] = defaultdict(list)

    def register(self, event: str, callback: Hook) -> None:
        if event not in self.EVENTS:
            raise ValueError(f"Unknown hook event: {event}")
        self._hooks[event].append(callback)

    async def trigger(self, event: str, **payload: Any) -> list[Any]:
        results: list[Any] = []
        for callback in list(self._hooks.get(event, [])):
            value = callback(**payload)
            if inspect.isawaitable(value):
                value = await value
            results.append(value)
        return results

    async def first_block(self, event: str, **payload: Any) -> HookDecision | None:
        for value in await self.trigger(event, **payload):
            if isinstance(value, HookDecision) and value.blocked:
                return value
            if isinstance(value, str) and value:
                return HookDecision(blocked=True, reason=value)
        return None
