from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable


@dataclass(slots=True)
class AgentEvent:
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


EventHandler = Callable[[AgentEvent], Any | Awaitable[Any]]


class EventBus:
    """Small async event bus. The future Web IDE can stream these events."""

    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []
        self._queues: list[asyncio.Queue[AgentEvent]] = []

    def subscribe(self, handler: EventHandler) -> Callable[[], None]:
        self._handlers.append(handler)

        def unsubscribe() -> None:
            if handler in self._handlers:
                self._handlers.remove(handler)

        return unsubscribe

    def create_queue(self, maxsize: int = 0) -> tuple[asyncio.Queue[AgentEvent], Callable[[], None]]:
        queue: asyncio.Queue[AgentEvent] = asyncio.Queue(maxsize=maxsize)
        self._queues.append(queue)

        def close() -> None:
            if queue in self._queues:
                self._queues.remove(queue)

        return queue, close

    async def emit(self, event_type: str, **data: Any) -> AgentEvent:
        event = AgentEvent(type=event_type, data=data)
        for queue in list(self._queues):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass
        for handler in list(self._handlers):
            value = handler(event)
            if inspect.isawaitable(value):
                await value
        return event
