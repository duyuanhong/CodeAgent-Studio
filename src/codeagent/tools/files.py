from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import Any

from codeagent.tools.base import Tool, ToolContext


def safe_path(workspace: Path, raw: str) -> Path:
    root = workspace.resolve()
    target = (root / raw).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"path escapes workspace: {raw}")
    return target


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read a UTF-8 text file inside the workspace."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "offset": {"type": "integer", "minimum": 0},
            "limit": {"type": "integer", "minimum": 1},
        },
        "required": ["path"],
    }

    async def execute(self, ctx: ToolContext, path: str, offset: int = 0, limit: int | None = None) -> str:
        target = safe_path(ctx.workspace, path)
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        selected = lines[offset : offset + limit if limit else None]
        width = len(str(offset + len(selected) + 1))
        rendered = [f"{i:>{width}} | {line}" for i, line in enumerate(selected, start=offset + 1)]
        if limit and offset + limit < len(lines):
            rendered.append(f"... ({len(lines) - offset - limit} more lines)")
        return "\n".join(rendered) if rendered else "(empty file)"


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write a UTF-8 file inside the workspace, creating parent directories."
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"],
    }

    async def execute(self, ctx: ToolContext, path: str, content: str) -> str:
        target = safe_path(ctx.workspace, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content.encode('utf-8'))} bytes to {path}"


class EditFileTool(Tool):
    name = "edit_file"
    description = "Replace one exact text occurrence in a UTF-8 file."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_text": {"type": "string"},
            "new_text": {"type": "string"},
        },
        "required": ["path", "old_text", "new_text"],
    }

    async def execute(self, ctx: ToolContext, path: str, old_text: str, new_text: str) -> str:
        target = safe_path(ctx.workspace, path)
        text = target.read_text(encoding="utf-8", errors="replace")
        count = text.count(old_text)
        if count != 1:
            return f"Error: expected exactly 1 occurrence in {path}, found {count}"
        target.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        return f"Edited {path}"


class GlobTool(Tool):
    name = "glob"
    description = "Find workspace files matching a glob pattern. Use ** for recursive matching."
    input_schema = {
        "type": "object",
        "properties": {"pattern": {"type": "string"}, "limit": {"type": "integer", "minimum": 1}},
        "required": ["pattern"],
    }

    async def execute(self, ctx: ToolContext, pattern: str, limit: int = 200) -> str:
        root = ctx.workspace.resolve()
        matches: list[str] = []
        for path in root.glob(pattern):
            resolved = path.resolve()
            if resolved.is_relative_to(root):
                matches.append(str(resolved.relative_to(root)))
            if len(matches) >= limit:
                break
        return "\n".join(sorted(matches)) if matches else "(no matches)"


class GrepTool(Tool):
    name = "grep"
    description = "Search text recursively inside workspace files using a regular expression."
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string", "default": "."},
            "include": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1},
        },
        "required": ["pattern"],
    }

    async def execute(
        self,
        ctx: ToolContext,
        pattern: str,
        path: str = ".",
        include: str | None = None,
        limit: int = 200,
    ) -> str:
        base = safe_path(ctx.workspace, path)
        regex = re.compile(pattern)
        matches: list[str] = []
        files = [base] if base.is_file() else base.rglob("*")
        for file in files:
            if not file.is_file():
                continue
            rel = str(file.relative_to(ctx.workspace))
            if include and not fnmatch.fnmatch(rel, include) and not fnmatch.fnmatch(file.name, include):
                continue
            if any(part in {".git", ".codeagent", "node_modules", ".venv", "venv"} for part in file.parts):
                continue
            try:
                for line_no, line in enumerate(file.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if regex.search(line):
                        matches.append(f"{rel}:{line_no}:{line}")
                        if len(matches) >= limit:
                            return "\n".join(matches) + "\n... (limit reached)"
            except OSError:
                continue
        return "\n".join(matches) if matches else "(no matches)"


def default_file_tools() -> list[Tool]:
    return [ReadFileTool(), WriteFileTool(), EditFileTool(), GlobTool(), GrepTool()]
