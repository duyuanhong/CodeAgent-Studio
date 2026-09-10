from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ToolContext:
    runtime: Any
    workspace: Any


class Tool(ABC):
    name: str
    description: str
    input_schema: dict[str, Any]

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    @abstractmethod
    async def execute(self, ctx: ToolContext, **kwargs: Any) -> str:
        raise NotImplementedError


class FunctionTool(Tool):
    def __init__(self, name: str, description: str, input_schema: dict[str, Any], fn) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.fn = fn

    async def execute(self, ctx: ToolContext, **kwargs: Any) -> str:
        try:
            value = self.fn(ctx=ctx, **kwargs)
        except TypeError as exc:
            if "ctx" not in str(exc):
                raise
            value = self.fn(**kwargs)
        if inspect.isawaitable(value):
            value = await value
        return str(value)
