from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from codeagent.tools.base import Tool, ToolContext


@dataclass(slots=True)
class TodoItem:
    content: str
    status: str = "pending"
    active_form: str = ""


class TodoStore:
    ALLOWED = {"pending", "in_progress", "completed"}

    def __init__(self, path: Path) -> None:
        self.path = path
        self.items: list[TodoItem] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.items = [TodoItem(**item) for item in raw if isinstance(item, dict)]
        except Exception:
            self.items = []

    def replace(self, items: list[dict[str, Any]]) -> None:
        parsed: list[TodoItem] = []
        in_progress = 0
        for item in items:
            content = str(item.get("content", "")).strip()
            status = str(item.get("status", "pending"))
            if not content:
                raise ValueError("todo content cannot be empty")
            if status not in self.ALLOWED:
                raise ValueError(f"invalid todo status: {status}")
            if status == "in_progress":
                in_progress += 1
            parsed.append(TodoItem(content, status, str(item.get("active_form", ""))))
        if in_progress > 1:
            raise ValueError("at most one todo may be in_progress")
        self.items = parsed
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([asdict(item) for item in self.items], ensure_ascii=False, indent=2), encoding="utf-8")

    def render(self) -> str:
        if not self.items:
            return "(no todos)"
        marks = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}
        return "\n".join(f"{marks[item.status]} {item.content}" for item in self.items)


class TodoWriteTool(Tool):
    name = "todo_write"
    description = "Replace the current task plan. Use pending, in_progress, or completed status."
    input_schema = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
                        "active_form": {"type": "string"},
                    },
                    "required": ["content", "status"],
                },
            }
        },
        "required": ["todos"],
    }

    async def execute(self, ctx: ToolContext, todos: list[dict[str, Any]]) -> str:
        ctx.runtime.todos.replace(todos)
        return ctx.runtime.todos.render()
