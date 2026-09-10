from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from codeagent.tools.base import Tool, ToolContext
from codeagent.tools.files import safe_path


@dataclass(slots=True)
class Skill:
    name: str
    path: Path
    description: str


class SkillStore:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def roots(self) -> list[Path]:
        return [self.workspace / ".codeagent" / "skills", self.workspace / "skills"]

    def list(self) -> list[Skill]:
        found: dict[str, Skill] = {}
        for root in self.roots():
            if not root.exists():
                continue
            for file in root.glob("*/SKILL.md"):
                name = file.parent.name
                text = file.read_text(encoding="utf-8", errors="replace")
                description = ""
                for line in text.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("---"):
                        description = line[:240]
                        break
                found[name] = Skill(name=name, path=file, description=description)
        return sorted(found.values(), key=lambda s: s.name)

    def load(self, name: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", name):
            raise ValueError("invalid skill name")
        for skill in self.list():
            if skill.name == name:
                return skill.path.read_text(encoding="utf-8", errors="replace")
        raise FileNotFoundError(f"unknown skill: {name}")

    def catalog(self) -> str:
        skills = self.list()
        return "\n".join(f"- {s.name}: {s.description}" for s in skills) if skills else "(no skills)"


class SkillListTool(Tool):
    name = "skill_list"
    description = "List available on-demand skills."
    input_schema = {"type": "object", "properties": {}}

    async def execute(self, ctx: ToolContext) -> str:
        return ctx.runtime.skills.catalog()


class SkillLoadTool(Tool):
    name = "skill_load"
    description = "Load one skill instruction document on demand."
    input_schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }

    async def execute(self, ctx: ToolContext, name: str) -> str:
        return ctx.runtime.skills.load(name)
