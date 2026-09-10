from __future__ import annotations

import asyncio
import re
from pathlib import Path

from codeagent.tools.base import Tool, ToolContext


_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class WorktreeManager:
    """Git worktree isolation for parallel coding tasks."""

    def __init__(self, workspace: Path, root: Path) -> None:
        self.workspace = workspace.resolve()
        self.root = root.resolve()

    @staticmethod
    def validate_name(name: str) -> str:
        if not _SAFE.fullmatch(name):
            raise ValueError("worktree name must be a 1-64 character safe slug")
        return name

    async def _git(self, *args: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=self.workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = (stdout + stderr).decode("utf-8", errors="replace").strip()
        if proc.returncode:
            raise RuntimeError(output or f"git exited with {proc.returncode}")
        return output

    async def ensure_repo(self) -> None:
        await self._git("rev-parse", "--show-toplevel")

    async def create(self, name: str, branch: str | None = None) -> Path:
        self.validate_name(name)
        await self.ensure_repo()
        self.root.mkdir(parents=True, exist_ok=True)
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("invalid worktree path")
        if path.exists():
            raise FileExistsError(f"worktree already exists: {path}")
        branch = branch or f"codeagent/{name}"
        await self._git("worktree", "add", "-b", branch, str(path), "HEAD")
        return path

    async def remove(self, name: str, force: bool = False) -> str:
        self.validate_name(name)
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("invalid worktree path")
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(path))
        return await self._git(*args) or f"Removed {name}"

    async def list(self) -> str:
        await self.ensure_repo()
        return await self._git("worktree", "list", "--porcelain")


class WorktreeCreateTool(Tool):
    name = "worktree_create"
    description = "Create an isolated git worktree and branch for a parallel coding task."
    input_schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "branch": {"type": "string"}},
        "required": ["name"],
    }

    async def execute(self, ctx: ToolContext, name: str, branch: str | None = None) -> str:
        path = await ctx.runtime.worktrees.create(name, branch)
        return str(path)


class WorktreeListTool(Tool):
    name = "worktree_list"
    description = "List git worktrees for the current repository."
    input_schema = {"type": "object", "properties": {}}

    async def execute(self, ctx: ToolContext) -> str:
        return await ctx.runtime.worktrees.list()


class WorktreeRemoveTool(Tool):
    name = "worktree_remove"
    description = "Remove a CodeAgent-managed git worktree."
    input_schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "force": {"type": "boolean"}},
        "required": ["name"],
    }

    async def execute(self, ctx: ToolContext, name: str, force: bool = False) -> str:
        return await ctx.runtime.worktrees.remove(name, force)
