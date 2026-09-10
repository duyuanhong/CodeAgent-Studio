from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from codeagent.tools.base import Tool, ToolContext


@dataclass(slots=True)
class Task:
    id: str
    subject: str
    description: str = ""
    status: str = "pending"
    owner: str | None = None
    blocked_by: list[str] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0


class TaskStore:
    ALLOWED = {"pending", "in_progress", "completed", "failed"}

    def __init__(self, path: Path) -> None:
        self.path = path
        self.tasks: dict[str, Task] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.tasks = {item["id"]: Task(**item) for item in raw if isinstance(item, dict)}
        except Exception:
            self.tasks = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([asdict(t) for t in self.tasks.values()], ensure_ascii=False, indent=2), encoding="utf-8")

    def create(self, subject: str, description: str = "", blocked_by: list[str] | None = None) -> Task:
        deps = list(dict.fromkeys(blocked_by or []))
        missing = [dep for dep in deps if dep not in self.tasks]
        if missing:
            raise ValueError(f"unknown dependencies: {', '.join(missing)}")
        now = time.time()
        task = Task(uuid.uuid4().hex[:10], subject.strip(), description.strip(), "pending", None, deps, now, now)
        if not task.subject:
            raise ValueError("task subject cannot be empty")
        self.tasks[task.id] = task
        self._ensure_acyclic()
        self.save()
        return task

    def update(self, task_id: str, **changes: Any) -> Task:
        import copy

        backup = copy.deepcopy(self.tasks)
        try:
            task = self.tasks[task_id]
            if "status" in changes:
                status = str(changes["status"])
                if status not in self.ALLOWED:
                    raise ValueError(f"invalid task status: {status}")
                if status == "in_progress":
                    unmet = [d for d in task.blocked_by if self.tasks[d].status != "completed"]
                    if unmet:
                        raise ValueError(f"task {task_id} is blocked by: {', '.join(unmet)}")
                task.status = status
            if "owner" in changes:
                task.owner = changes["owner"] or None
            if "subject" in changes and str(changes["subject"]).strip():
                task.subject = str(changes["subject"]).strip()
            if "description" in changes:
                task.description = str(changes["description"])
            if "blocked_by" in changes:
                deps = list(dict.fromkeys(changes["blocked_by"] or []))
                if task_id in deps:
                    raise ValueError("task cannot depend on itself")
                missing = [dep for dep in deps if dep not in self.tasks]
                if missing:
                    raise ValueError(f"unknown dependencies: {', '.join(missing)}")
                task.blocked_by = deps
            task.updated_at = time.time()
            self._ensure_acyclic()
            self.save()
            return task
        except Exception:
            self.tasks = backup
            raise

    def ready(self) -> list[Task]:
        return [
            t for t in self.tasks.values()
            if t.status == "pending" and all(self.tasks[d].status == "completed" for d in t.blocked_by)
        ]

    def claim(self, task_id: str, owner: str) -> Task:
        task = self.tasks[task_id]
        if task.status != "pending":
            raise ValueError(f"task {task_id} is not pending")
        unmet = [d for d in task.blocked_by if self.tasks[d].status != "completed"]
        if unmet:
            raise ValueError(f"task {task_id} is blocked by: {', '.join(unmet)}")
        task.owner = owner
        task.status = "in_progress"
        task.updated_at = time.time()
        self.save()
        return task

    def complete(self, task_id: str, success: bool = True) -> Task:
        return self.update(task_id, status="completed" if success else "failed")

    def render(self) -> str:
        if not self.tasks:
            return "(no tasks)"
        return "\n".join(
            f"{t.id} [{t.status}] owner={t.owner or '-'} deps={','.join(t.blocked_by) or '-'} {t.subject}"
            for t in self.tasks.values()
        )

    def _ensure_acyclic(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise ValueError("task dependency cycle detected")
            if task_id in visited:
                return
            visiting.add(task_id)
            for dep in self.tasks[task_id].blocked_by:
                visit(dep)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in self.tasks:
            visit(task_id)


class TaskCreateTool(Tool):
    name = "task_create"
    description = "Create a persistent task with optional dependency task ids."
    input_schema = {
        "type": "object",
        "properties": {
            "subject": {"type": "string"},
            "description": {"type": "string"},
            "blocked_by": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["subject"],
    }

    async def execute(self, ctx: ToolContext, subject: str, description: str = "", blocked_by: list[str] | None = None) -> str:
        task = ctx.runtime.tasks.create(subject, description, blocked_by)
        return f"Created {task.id}: {task.subject}"


class TaskListTool(Tool):
    name = "task_list"
    description = "List the persistent task graph and task states."
    input_schema = {"type": "object", "properties": {}}

    async def execute(self, ctx: ToolContext) -> str:
        return ctx.runtime.tasks.render()


class TaskUpdateTool(Tool):
    name = "task_update"
    description = "Update task status, owner, description, subject, or dependencies."
    input_schema = {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "failed"]},
            "owner": {"type": "string"},
            "subject": {"type": "string"},
            "description": {"type": "string"},
            "blocked_by": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["task_id"],
    }

    async def execute(self, ctx: ToolContext, task_id: str, **changes: Any) -> str:
        clean = {k: v for k, v in changes.items() if v is not None}
        task = ctx.runtime.tasks.update(task_id, **clean)
        return f"Updated {task.id}: status={task.status}, owner={task.owner or '-'}"


class TaskClaimTool(Tool):
    name = "task_claim"
    description = "Atomically claim a ready pending task for an owner."
    input_schema = {
        "type": "object",
        "properties": {"task_id": {"type": "string"}, "owner": {"type": "string"}},
        "required": ["task_id", "owner"],
    }

    async def execute(self, ctx: ToolContext, task_id: str, owner: str) -> str:
        task = ctx.runtime.tasks.claim(task_id, owner)
        return f"Claimed {task.id} for {owner}"


class TaskCompleteTool(Tool):
    name = "task_complete"
    description = "Mark a task completed or failed."
    input_schema = {
        "type": "object",
        "properties": {"task_id": {"type": "string"}, "success": {"type": "boolean"}},
        "required": ["task_id"],
    }

    async def execute(self, ctx: ToolContext, task_id: str, success: bool = True) -> str:
        task = ctx.runtime.tasks.complete(task_id, success)
        return f"{task.id}: {task.status}"
