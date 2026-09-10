from __future__ import annotations

import asyncio
import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from codeagent.tools.base import Tool, ToolContext


class WorkflowError(Exception):
    pass


@dataclass(slots=True)
class WorkflowRun:
    run_id: str
    name: str
    status: str
    results: dict[str, Any]


class WorkflowManager:
    """Saved, resumable orchestration with agent, tool, pipeline, and parallel steps."""

    def __init__(self, runtime: Any, root: Path, runs_dir: Path) -> None:
        self.runtime = runtime
        self.root = root
        self.runs_dir = runs_dir

    def load(self, name: str) -> dict[str, Any]:
        if not name or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for ch in name):
            raise WorkflowError("invalid workflow name")
        path = self.root / f"{name}.yaml"
        if not path.exists():
            raise WorkflowError(f"workflow not found: {name}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("steps"), list):
            raise WorkflowError("workflow must contain a steps list")
        return data

    async def run(self, name: str, args: dict[str, Any] | None = None, run_id: str | None = None) -> WorkflowRun:
        spec = self.load(name)
        run_id = run_id or f"wf_{name}_{secrets.token_hex(6)}"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        journal_path = self.runs_dir / f"{run_id}.json"
        state: dict[str, Any] = {"run_id": run_id, "name": name, "status": "running", "results": {}, "args": args or {}}
        if journal_path.exists():
            previous = json.loads(journal_path.read_text(encoding="utf-8"))
            if previous.get("name") != name:
                raise WorkflowError("run id belongs to another workflow")
            state.update(previous)
            state["status"] = "running"
        self._save(journal_path, state)

        try:
            for index, step in enumerate(spec["steps"]):
                key = str(step.get("id") or f"step_{index + 1}")
                if key in state["results"]:
                    continue
                state["results"][key] = await self._execute_step(step, state)
                self._save(journal_path, state)
            state["status"] = "completed"
            self._save(journal_path, state)
        except Exception as exc:
            state["status"] = "failed"
            state["error"] = f"{type(exc).__name__}: {exc}"
            self._save(journal_path, state)
            raise
        return WorkflowRun(run_id, name, state["status"], state["results"])

    async def _execute_step(self, step: dict[str, Any], state: dict[str, Any]) -> Any:
        step_type = step.get("type", "agent")
        if step_type == "agent":
            prompt = self._render(str(step.get("prompt", "")), state)
            kind = str(step.get("kind", "coder"))
            return await self.runtime.subagents.run(kind, prompt)
        if step_type == "tool":
            tool = str(step.get("tool", ""))
            args = self._render_obj(step.get("args", {}), state)
            return await self.runtime.execute_tool_direct(tool, args)
        if step_type == "pipeline":
            results = []
            for child in step.get("steps", []):
                results.append(await self._execute_step(child, state))
            return results
        if step_type == "parallel":
            children = list(step.get("steps", []))
            return await asyncio.gather(*(self._execute_step(child, state) for child in children))
        raise WorkflowError(f"unknown step type: {step_type}")

    @staticmethod
    def _save(path: Path, state: dict[str, Any]) -> None:
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    @staticmethod
    def _render(text: str, state: dict[str, Any]) -> str:
        # Intentionally small templating surface: {{args.key}} and {{results.step}}.
        import re

        def replace(match) -> str:
            expression = match.group(1).strip().split(".")
            value: Any = state
            for part in expression:
                if not isinstance(value, dict) or part not in value:
                    return match.group(0)
                value = value[part]
            return str(value)

        return re.sub(r"\{\{\s*([^{}]+?)\s*\}\}", replace, text)

    def _render_obj(self, value: Any, state: dict[str, Any]) -> Any:
        if isinstance(value, str):
            return self._render(value, state)
        if isinstance(value, list):
            return [self._render_obj(item, state) for item in value]
        if isinstance(value, dict):
            return {key: self._render_obj(item, state) for key, item in value.items()}
        return value


class WorkflowRunTool(Tool):
    name = "workflow_run"
    description = "Run or resume a saved workflow from .codeagent/workflows/<name>.yaml."
    input_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "args": {"type": "object"},
            "run_id": {"type": "string"},
        },
        "required": ["name"],
    }

    async def execute(self, ctx: ToolContext, name: str, args: dict[str, Any] | None = None, run_id: str | None = None) -> str:
        run = await ctx.runtime.workflows.run(name, args, run_id)
        return json.dumps({"run_id": run.run_id, "status": run.status, "results": run.results}, ensure_ascii=False, indent=2)
