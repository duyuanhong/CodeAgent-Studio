from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codeagent.tools.base import Tool, ToolContext


@dataclass(slots=True)
class SubagentSpec:
    name: str
    system_suffix: str
    allowed_tools: set[str] | None = None


DEFAULT_SUBAGENTS = {
    "explore": SubagentSpec(
        name="explore",
        system_suffix=(
            "You are an exploration subagent. Inspect the repository, answer focused questions, "
            "and avoid modifying files unless explicitly required."
        ),
        allowed_tools={"read_file", "glob", "grep", "bash", "skill_list", "skill_load", "memory_search"},
    ),
    "coder": SubagentSpec(
        name="coder",
        system_suffix="You are a coding subagent. Make focused, minimal changes and verify them.",
    ),
    "reviewer": SubagentSpec(
        name="reviewer",
        system_suffix=(
            "You are a code review subagent. Find concrete correctness, security, testing, and maintainability issues. "
            "Prefer evidence from files and command results."
        ),
        allowed_tools={"read_file", "glob", "grep", "bash", "skill_list", "skill_load", "memory_search"},
    ),
}


class SubagentManager:
    def __init__(self, runtime: Any, max_depth: int = 2) -> None:
        self.runtime = runtime
        self.max_depth = max_depth
        self.specs = dict(DEFAULT_SUBAGENTS)

    async def run(self, kind: str, prompt: str) -> str:
        if self.runtime.depth >= self.max_depth:
            return f"Error: subagent depth limit {self.max_depth} reached"
        spec = self.specs.get(kind)
        if spec is None:
            return f"Error: unknown subagent kind '{kind}'"
        child = self.runtime.spawn_child(
            system_suffix=spec.system_suffix,
            allowed_tools=spec.allowed_tools,
        )
        result = await child.run(prompt, save_session=False)
        return result.text


class SpawnSubagentTool(Tool):
    name = "spawn_subagent"
    description = "Run a focused explore, coder, or reviewer subagent with a fresh conversation context."
    input_schema = {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["explore", "coder", "reviewer"]},
            "prompt": {"type": "string"},
        },
        "required": ["kind", "prompt"],
    }

    async def execute(self, ctx: ToolContext, kind: str, prompt: str) -> str:
        return await ctx.runtime.subagents.run(kind, prompt)
