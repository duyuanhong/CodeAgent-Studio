from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass

from codeagent.tools.base import Tool, ToolContext


@dataclass(slots=True)
class BackgroundJob:
    id: str
    command: str
    started_at: float
    task: asyncio.Task[str]


class BackgroundManager:
    def __init__(self) -> None:
        self.jobs: dict[str, BackgroundJob] = {}
        self.notified: set[str] = set()

    async def launch(self, runtime, command: str, timeout: int | None = None) -> BackgroundJob:
        job_id = "bg_" + uuid.uuid4().hex[:10]

        async def worker() -> str:
            tool = runtime.tools.get("bash")
            if tool is None:
                return "Error: bash tool unavailable"
            from codeagent.tools.base import ToolContext
            return await tool.execute(ToolContext(runtime=runtime, workspace=runtime.settings.workspace), command=command, timeout=timeout)

        task = asyncio.create_task(worker(), name=job_id)
        job = BackgroundJob(job_id, command, time.time(), task)
        self.jobs[job_id] = job
        return job

    def status(self, job_id: str) -> str:
        job = self.jobs.get(job_id)
        if not job:
            return f"Error: unknown background job {job_id}"
        if not job.task.done():
            return f"{job_id}: running"
        try:
            value = job.task.result()
        except Exception as exc:
            return f"{job_id}: failed: {type(exc).__name__}: {exc}"
        return f"{job_id}: completed\n{value}"

    def running(self) -> list[BackgroundJob]:
        return [job for job in self.jobs.values() if not job.task.done()]

    def collect_notifications(self) -> list[str]:
        notes: list[str] = []
        for job_id, job in self.jobs.items():
            if job_id in self.notified or not job.task.done():
                continue
            self.notified.add(job_id)
            notes.append(self.status(job_id))
        return notes


class BackgroundBashTool(Tool):
    name = "background_bash"
    description = "Start a shell command in the background and immediately return a job id."
    input_schema = {
        "type": "object",
        "properties": {"command": {"type": "string"}, "timeout": {"type": "integer", "minimum": 1, "maximum": 3600}},
        "required": ["command"],
    }

    async def execute(self, ctx: ToolContext, command: str, timeout: int | None = None) -> str:
        job = await ctx.runtime.background.launch(ctx.runtime, command, timeout)
        return f"Started {job.id}"


class BackgroundPollTool(Tool):
    name = "background_poll"
    description = "Check a background shell job."
    input_schema = {
        "type": "object",
        "properties": {"job_id": {"type": "string"}},
        "required": ["job_id"],
    }

    async def execute(self, ctx: ToolContext, job_id: str) -> str:
        return ctx.runtime.background.status(job_id)
