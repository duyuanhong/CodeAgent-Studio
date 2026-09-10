from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Role = Literal["user", "assistant"]


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class ModelTurn:
    """Provider-neutral model output used by the runtime."""

    blocks: list[dict[str, Any]]
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(slots=True)
class ToolResult:
    tool_use_id: str
    content: str
    is_error: bool = False

    def as_block(self) -> dict[str, Any]:
        block: dict[str, Any] = {
            "type": "tool_result",
            "tool_use_id": self.tool_use_id,
            "content": self.content,
        }
        if self.is_error:
            block["is_error"] = True
        return block


@dataclass(slots=True)
class RunResult:
    text: str
    messages: list[dict[str, Any]]
    status: str = "completed"
    reason: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
