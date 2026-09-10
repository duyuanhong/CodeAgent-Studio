from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable



@dataclass(slots=True)
class ScheduledJob:
    id: str
    cron: str
    prompt: str
    next_run: float
    enabled: bool = True


def _croniter(expression: str, base: float):
    try:
        from croniter import croniter
    except ImportError as exc:
        raise RuntimeError("Cron scheduling requires the croniter package") from exc
    return croniter(expression, base)


class CronScheduler:
    """In-process cron scheduler. A production deployment should persist jobs externally."""

    def __init__(self, callback: Callable[[str], Awaitable[None]]) -> None:
        self.callback = callback
        self.jobs: dict[str, ScheduledJob] = {}
        self._runner: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def add(self, cron: str, prompt: str) -> ScheduledJob:
        iterator = _croniter(cron, time.time())
        job = ScheduledJob("cron_" + uuid.uuid4().hex[:10], cron, prompt, float(iterator.get_next(float)))
        self.jobs[job.id] = job
        return job

    def remove(self, job_id: str) -> None:
        self.jobs.pop(job_id, None)

    async def start(self) -> None:
        if self._runner and not self._runner.done():
            return
        self._stop.clear()
        self._runner = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._runner:
            await self._runner

    async def _loop(self) -> None:
        while not self._stop.is_set():
            now = time.time()
            for job in list(self.jobs.values()):
                if job.enabled and job.next_run <= now:
                    asyncio.create_task(self.callback(job.prompt))
                    job.next_run = float(_croniter(job.cron, now).get_next(float))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

from codeagent.tools.base import Tool, ToolContext


class CronAddTool(Tool):
    name = "cron_add"
    description = "Schedule an agent prompt with a standard five-field cron expression for the current process."
    input_schema = {
        "type": "object",
        "properties": {"cron": {"type": "string"}, "prompt": {"type": "string"}},
        "required": ["cron", "prompt"],
    }

    async def execute(self, ctx: ToolContext, cron: str, prompt: str) -> str:
        job = ctx.runtime.scheduler.add(cron, prompt)
        await ctx.runtime.scheduler.start()
        return f"Scheduled {job.id}; next_run={job.next_run:.3f}"


class CronListTool(Tool):
    name = "cron_list"
    description = "List in-process scheduled agent jobs."
    input_schema = {"type": "object", "properties": {}}

    async def execute(self, ctx: ToolContext) -> str:
        jobs = ctx.runtime.scheduler.jobs.values()
        if not jobs:
            return "(no scheduled jobs)"
        return "\n".join(f"{j.id} enabled={j.enabled} cron={j.cron} prompt={j.prompt}" for j in jobs)
