from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from codeagent.tools.base import Tool, ToolContext


@dataclass(slots=True)
class MemoryRecord:
    id: str
    content: str
    kind: str = "project"
    persistent: bool = True
    created_at: float = 0.0


class MemoryStore:
    """Small file-backed memory store with keyword recall and consolidation."""

    ALLOWED_KINDS = {"user", "feedback", "project", "reference"}

    def __init__(self, path: Path) -> None:
        self.path = path
        self.records: list[MemoryRecord] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.records = [MemoryRecord(**item) for item in raw if isinstance(item, dict)]
        except Exception:
            self.records = []

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([asdict(r) for r in self.records], ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, content: str, kind: str = "project", persistent: bool = True) -> MemoryRecord:
        content = content.strip()
        if not content:
            raise ValueError("memory content cannot be empty")
        if kind not in self.ALLOWED_KINDS:
            raise ValueError(f"invalid memory kind: {kind}")
        normalized = re.sub(r"\s+", " ", content).strip().lower()
        for record in self.records:
            if re.sub(r"\s+", " ", record.content).strip().lower() == normalized:
                record.kind = kind
                record.persistent = persistent
                self.save()
                return record
        record = MemoryRecord(
            id=uuid.uuid4().hex[:12],
            content=content,
            kind=kind,
            persistent=persistent,
            created_at=time.time(),
        )
        self.records.append(record)
        self.save()
        return record

    def search(self, query: str, limit: int = 8) -> list[MemoryRecord]:
        words = {w.lower() for w in re.findall(r"[\w\u4e00-\u9fff]+", query) if len(w) > 1}
        if not words:
            return self.records[-limit:]
        scored: list[tuple[int, float, MemoryRecord]] = []
        for record in self.records:
            text = record.content.lower()
            score = sum(1 for word in words if word in text)
            if score:
                scored.append((score, record.created_at, record))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [record for _, _, record in scored[:limit]]

    def render_recall(self, query: str, limit: int = 8) -> str:
        rows = self.search(query, limit)
        if not rows:
            return "(no relevant memory)"
        return "\n".join(f"[{r.kind}] {r.content}" for r in rows)


class MemoryAddTool(Tool):
    name = "memory_add"
    description = "Persist a useful project, user, feedback, or reference memory."
    input_schema = {
        "type": "object",
        "properties": {
            "content": {"type": "string"},
            "kind": {"type": "string", "enum": ["user", "feedback", "project", "reference"]},
            "persistent": {"type": "boolean"},
        },
        "required": ["content"],
    }

    async def execute(self, ctx: ToolContext, content: str, kind: str = "project", persistent: bool = True) -> str:
        record = ctx.runtime.memory.add(content, kind, persistent)
        return f"Stored memory {record.id}"


class MemorySearchTool(Tool):
    name = "memory_search"
    description = "Search persistent memories relevant to the current task."
    input_schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 20}},
        "required": ["query"],
    }

    async def execute(self, ctx: ToolContext, query: str, limit: int = 8) -> str:
        return ctx.runtime.memory.render_recall(query, limit)
