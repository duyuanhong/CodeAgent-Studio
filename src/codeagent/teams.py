from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from codeagent.tools.base import Tool, ToolContext


@dataclass(slots=True)
class TeamMessage:
    id: str
    member: str
    task: str
    output: str | None = None
    error: str | None = None


@dataclass(slots=True)
class TeamMember:
    name: str
    kind: str
    inbox: asyncio.Queue[TeamMessage]
    worker: asyncio.Task[None]


class TeamManager:
    """Persistent teammate mailboxes plus a convenience parallel fan-out API."""

    def __init__(self, runtime: Any, concurrency: int = 4) -> None:
        self.runtime = runtime
        self.concurrency = concurrency
        self.members: dict[str, TeamMember] = {}
        self.messages: dict[str, TeamMessage] = {}
        self._counter = 0

    async def spawn(self, name: str, kind: str = "explore") -> str:
        if name in self.members:
            return f"Error: teammate '{name}' already exists"
        inbox: asyncio.Queue[TeamMessage] = asyncio.Queue()

        async def loop() -> None:
            while True:
                message = await inbox.get()
                if message.task == "__shutdown__":
                    return
                try:
                    message.output = await self.runtime.subagents.run(kind, message.task)
                except Exception as exc:
                    message.error = f"{type(exc).__name__}: {exc}"

        worker = asyncio.create_task(loop(), name=f"team:{name}")
        self.members[name] = TeamMember(name=name, kind=kind, inbox=inbox, worker=worker)
        return f"Spawned teammate '{name}' ({kind})"

    async def send(self, name: str, task: str) -> str:
        member = self.members.get(name)
        if member is None:
            return f"Error: unknown teammate '{name}'"
        self._counter += 1
        message_id = f"msg_{self._counter:04d}"
        message = TeamMessage(message_id, name, task)
        self.messages[message_id] = message
        await member.inbox.put(message)
        return message_id

    def poll(self, message_id: str) -> str:
        message = self.messages.get(message_id)
        if message is None:
            return f"Error: unknown team message {message_id}"
        if message.error:
            return f"{message_id}: failed\n{message.error}"
        if message.output is None:
            return f"{message_id}: running"
        return f"{message_id}: completed\n{message.output}"

    async def run_parallel(self, assignments: list[dict[str, str]]) -> list[TeamMessage]:
        semaphore = asyncio.Semaphore(self.concurrency)

        async def one(index: int, item: dict[str, str]) -> TeamMessage:
            kind = item.get("member", "explore")
            prompt = item.get("task", "")
            async with semaphore:
                try:
                    output = await self.runtime.subagents.run(kind, prompt)
                    return TeamMessage(f"parallel_{index}", kind, prompt, output=output)
                except Exception as exc:
                    return TeamMessage(f"parallel_{index}", kind, prompt, error=f"{type(exc).__name__}: {exc}")

        return await asyncio.gather(*(one(i, item) for i, item in enumerate(assignments, 1)))

    async def close(self) -> None:
        for member in list(self.members.values()):
            await member.inbox.put(TeamMessage("shutdown", member.name, "__shutdown__"))
        if self.members:
            await asyncio.gather(*(member.worker for member in self.members.values()), return_exceptions=True)
        self.members.clear()


class TeamRunTool(Tool):
    name = "team_run"
    description = "Run several explore, coder, or reviewer subagents in parallel and collect their outputs."
    input_schema = {
        "type": "object",
        "properties": {
            "assignments": {
                "type": "array",
                "minItems": 1,
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "properties": {
                        "member": {"type": "string", "enum": ["explore", "coder", "reviewer"]},
                        "task": {"type": "string"},
                    },
                    "required": ["member", "task"],
                },
            }
        },
        "required": ["assignments"],
    }

    async def execute(self, ctx: ToolContext, assignments: list[dict[str, str]]) -> str:
        results = await ctx.runtime.teams.run_parallel(assignments)
        sections = []
        for r in results:
            body = r.output if r.output is not None else f"Error: {r.error}"
            sections.append(f"## {r.member}: {r.task}\n{body}")
        return "\n\n".join(sections)


class TeamSpawnTool(Tool):
    name = "team_spawn"
    description = "Spawn a persistent teammate with its own mailbox."
    input_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "kind": {"type": "string", "enum": ["explore", "coder", "reviewer"]},
        },
        "required": ["name"],
    }

    async def execute(self, ctx: ToolContext, name: str, kind: str = "explore") -> str:
        return await ctx.runtime.teams.spawn(name, kind)


class TeamSendTool(Tool):
    name = "team_send"
    description = "Send a task to a persistent teammate and return a message id."
    input_schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "task": {"type": "string"}},
        "required": ["name", "task"],
    }

    async def execute(self, ctx: ToolContext, name: str, task: str) -> str:
        return await ctx.runtime.teams.send(name, task)


class TeamPollTool(Tool):
    name = "team_poll"
    description = "Poll a persistent teammate message id."
    input_schema = {
        "type": "object",
        "properties": {"message_id": {"type": "string"}},
        "required": ["message_id"],
    }

    async def execute(self, ctx: ToolContext, message_id: str) -> str:
        return ctx.runtime.teams.poll(message_id)
