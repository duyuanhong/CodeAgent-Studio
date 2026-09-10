from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from codeagent.tools.base import Tool, ToolContext


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool, *, replace: bool = False) -> None:
        if tool.name in self._tools and not replace:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def register_many(self, tools: Iterable[Tool]) -> None:
        for tool in tools:
            self.register(tool)

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema for tool in self._tools.values()]

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    async def execute(self, name: str, ctx: ToolContext, arguments: dict[str, Any]) -> str:
        tool = self.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'"
        try:
            return await tool.execute(ctx, **arguments)
        except Exception as exc:
            return f"Error: {type(exc).__name__}: {exc}"
