from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import shlex
import subprocess
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from codeagent.config import Settings
from codeagent.events import EventBus
from codeagent.llm.scripted import ScriptedProvider
from codeagent.models import ModelTurn, ToolCall
from codeagent.permission import PermissionAction, PermissionManager
from codeagent.runtime import AgentRuntime


IGNORED_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".next",
}
TEXT_FILE_LIMIT = 1_500_000


class FileWrite(BaseModel):
    path: str
    content: str


class TerminalCommand(BaseModel):
    command: str


class RuntimeHub:
    def __init__(self, workspace: Path, demo: bool = False) -> None:
        self.workspace = workspace.resolve()
        self.demo = demo

    def settings(self) -> Settings:
        settings = Settings.from_env(self.workspace)
        settings.non_interactive = False
        return settings

    def provider(self):
        settings = self.settings()
        if self.demo or not settings.model or not settings.anthropic_api_key:
            return DemoProvider()
        from codeagent.llm.anthropic import AnthropicProvider
        return AnthropicProvider(
            model=settings.model,
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
        )


class DemoProvider(ScriptedProvider):
    """A deterministic live-demo provider that exercises the real tool loop."""

    def __init__(self) -> None:
        super().__init__([])
        self.step = 0

    async def complete(self, *, messages, system, tools, max_tokens):
        self.step += 1
        tool_names = {item.get("name") for item in tools}
        if self.step == 1 and "read_file" in tool_names:
            call = ToolCall("demo_read", "read_file", {"path": "src/codeagent/runtime.py", "limit": 70})
            return ModelTurn(
                blocks=[
                    {"type": "text", "text": "I’ll trace the runtime boundary first, then verify how tools enter the loop."},
                    {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments},
                ],
                text="I’ll trace the runtime boundary first, then verify how tools enter the loop.",
                tool_calls=[call],
                input_tokens=364,
                output_tokens=71,
            )
        if self.step == 2 and "grep" in tool_names:
            call = ToolCall("demo_grep", "grep", {"pattern": "events.emit", "path": "src/codeagent"})
            return ModelTurn(
                blocks=[
                    {"type": "text", "text": "The core loop is centralized. I’m checking whether observability is equally centralized."},
                    {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments},
                ],
                text="The core loop is centralized. I’m checking whether observability is equally centralized.",
                tool_calls=[call],
                input_tokens=612,
                output_tokens=79,
            )
        return ModelTurn(
            blocks=[{"type": "text", "text": (
                "The harness uses one stable AgentRuntime for context, model turns, permissions, hooks, tool dispatch, goal evaluation, sessions, and the EventBus. "
                "The Web IDE can therefore visualize real execution without inventing a second orchestration layer. The highest-value next engineering step is provider streaming, so model tokens can appear incrementally while tool events continue through the same trace."
            )}],
            text=(
                "The harness uses one stable AgentRuntime for context, model turns, permissions, hooks, tool dispatch, goal evaluation, sessions, and the EventBus. "
                "The Web IDE can therefore visualize real execution without inventing a second orchestration layer. The highest-value next engineering step is provider streaming, so model tokens can appear incrementally while tool events continue through the same trace."
            ),
            input_tokens=941,
            output_tokens=128,
        )


def _safe_path(root: Path, raw: str) -> Path:
    raw_path = Path(raw)
    target = raw_path.resolve() if raw_path.is_absolute() else (root / raw_path).resolve()
    if not target.is_relative_to(root):
        raise HTTPException(400, "path escapes workspace")
    return target


def _run_git(workspace: Path, *args: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=workspace,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=10,
        )
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def _build_tree(root: Path, path: Path | None = None, depth: int = 0, max_depth: int = 6) -> list[dict[str, Any]]:
    path = path or root
    if depth > max_depth:
        return []
    items: list[dict[str, Any]] = []
    try:
        children = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except OSError:
        return items
    for child in children:
        if child.name in IGNORED_NAMES or child.name.startswith(".codeagent"):
            continue
        rel = child.relative_to(root).as_posix()
        if child.is_dir():
            items.append({
                "name": child.name,
                "path": rel,
                "type": "directory",
                "children": _build_tree(root, child, depth + 1, max_depth),
            })
        elif child.is_file():
            items.append({"name": child.name, "path": rel, "type": "file"})
    return items


def create_app(workspace: str | Path | None = None, *, demo: bool | None = None) -> FastAPI:
    root = Path(workspace or os.getenv("CODEAGENT_WORKSPACE") or Path.cwd()).resolve()
    root.mkdir(parents=True, exist_ok=True)
    is_demo = demo if demo is not None else os.getenv("CODEAGENT_WEB_DEMO", "0") == "1"
    hub = RuntimeHub(root, is_demo)

    app = FastAPI(title="CodeAgent Studio", version="0.2.0")
    app.state.hub = hub
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        settings = hub.settings()
        code_files = list(root.glob("src/**/*.py"))
        test_files = list(root.glob("tests/test_*.py"))
        tool_count = 0
        try:
            runtime = AgentRuntime(hub.provider(), settings)
            tool_count = len(runtime.tools.names)
            await runtime.close()
        except Exception:
            pass
        lines = 0
        for file in code_files:
            try:
                lines += len(file.read_text(encoding="utf-8").splitlines())
            except OSError:
                pass
        git_code, branch = _run_git(root, "branch", "--show-current")
        return {
            "status": "ok",
            "workspace": str(root),
            "workspaceName": root.name,
            "model": settings.model or "Demo Runtime",
            "provider": "demo" if is_demo or not settings.anthropic_api_key else "anthropic",
            "demo": is_demo or not settings.anthropic_api_key or not settings.model,
            "branch": branch if git_code == 0 and branch else "local",
            "metrics": {
                "modules": len(code_files),
                "tests": len(test_files),
                "tools": tool_count,
                "lines": lines,
            },
        }

    @app.get("/api/workspace/tree")
    async def workspace_tree() -> dict[str, Any]:
        return {"root": root.name, "items": _build_tree(root)}

    @app.get("/api/workspace/file")
    async def read_file(path: str) -> dict[str, Any]:
        target = _safe_path(root, path)
        if not target.is_file():
            raise HTTPException(404, "file not found")
        if target.stat().st_size > TEXT_FILE_LIMIT:
            raise HTTPException(413, "file too large for editor")
        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(415, "binary file") from exc
        return {"path": target.relative_to(root).as_posix(), "content": content, "size": target.stat().st_size}

    @app.put("/api/workspace/file")
    async def write_file(body: FileWrite) -> dict[str, Any]:
        target = _safe_path(root, body.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body.content, encoding="utf-8")
        return {"ok": True, "path": target.relative_to(root).as_posix(), "bytes": len(body.content.encode("utf-8"))}

    @app.get("/api/git/status")
    async def git_status() -> dict[str, Any]:
        code, output = _run_git(root, "status", "--porcelain=v1", "--branch")
        if code != 0:
            return {"available": False, "branch": "local", "changes": []}
        lines = output.splitlines()
        branch = "local"
        changes = []
        if lines and lines[0].startswith("##"):
            branch = lines.pop(0)[2:].strip().split("...")[0]
        for line in lines:
            if len(line) >= 4:
                changes.append({"status": line[:2].strip() or "M", "path": line[3:]})
        return {"available": True, "branch": branch, "changes": changes}

    @app.get("/api/git/diff")
    async def git_diff(path: str | None = None) -> dict[str, Any]:
        args = ["diff", "--no-ext-diff", "--unified=3"]
        if path:
            target = _safe_path(root, path)
            args.extend(["--", target.relative_to(root).as_posix()])
        code, output = _run_git(root, *args)
        return {"available": code == 0, "diff": output}

    @app.get("/api/git/file-diff")
    async def git_file_diff(path: str) -> dict[str, Any]:
        target = _safe_path(root, path)
        rel = target.relative_to(root).as_posix()
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        code, original = _run_git(root, "show", f"HEAD:{rel}")
        if code != 0:
            original = ""
        return {"path": rel, "original": original, "modified": current}

    @app.get("/api/sessions")
    async def sessions() -> dict[str, Any]:
        runtime = AgentRuntime(hub.provider(), hub.settings())
        try:
            ids = runtime.sessions.list()[:40]
            entries = []
            for session_id in ids:
                try:
                    data = runtime.sessions.load(session_id)
                    metadata = data.get("metadata", {})
                    first_user = next(
                        (m.get("content", "") for m in data.get("messages", []) if m.get("role") == "user"),
                        "",
                    )
                    entries.append({
                        "id": session_id,
                        "title": str(first_user)[:90] or "Untitled session",
                        "status": metadata.get("status", "completed"),
                        "inputTokens": metadata.get("input_tokens", 0),
                        "outputTokens": metadata.get("output_tokens", 0),
                    })
                except Exception:
                    continue
            return {"items": entries}
        finally:
            await runtime.close()

    @app.get("/api/tasks")
    async def tasks() -> dict[str, Any]:
        path = root / ".codeagent" / "tasks.json"
        if not path.exists():
            return {"items": []}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = []
        if isinstance(payload, dict):
            payload = list(payload.values())
        return {"items": payload if isinstance(payload, list) else []}

    @app.get("/api/worktrees")
    async def worktrees() -> dict[str, Any]:
        code, output = _run_git(root, "worktree", "list", "--porcelain")
        items: list[dict[str, str]] = []
        if code == 0:
            current: dict[str, str] = {}
            for line in output.splitlines() + [""]:
                if not line.strip():
                    if current:
                        items.append(current)
                        current = {}
                    continue
                key, _, value = line.partition(" ")
                current[key] = value
        return {"items": items}

    @app.get("/api/workflows")
    async def workflows() -> dict[str, Any]:
        candidates = list((root / "examples").glob("*.yaml")) + list((root / ".codeagent" / "workflows").glob("*.yaml"))
        return {"items": [{"name": p.stem, "path": p.relative_to(root).as_posix()} for p in candidates if p.is_file()]}

    @app.post("/api/terminal")
    async def terminal(body: TerminalCommand) -> dict[str, Any]:
        command = body.command.strip()
        if not command:
            return {"code": 0, "output": ""}
        permission = PermissionManager(non_interactive=True).check("bash", {"command": command})
        if permission.action == PermissionAction.DENY:
            raise HTTPException(403, permission.reason)
        if permission.action == PermissionAction.CONFIRM:
            raise HTTPException(409, f"Command requires approval in agent mode: {permission.reason}")
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            output = stdout.decode(errors="replace")[-100_000:]
            return {"code": proc.returncode or 0, "output": output}
        except asyncio.TimeoutError:
            proc.kill()
            return {"code": 124, "output": "Command timed out after 120s"}

    @app.websocket("/ws/agent")
    async def agent_socket(ws: WebSocket) -> None:
        await ws.accept()
        event_bus = EventBus()
        permission_waiters: dict[str, asyncio.Future[bool]] = {}
        send_lock = asyncio.Lock()

        async def send(payload: dict[str, Any]) -> None:
            async with send_lock:
                await ws.send_json(payload)

        async def forward_event(event) -> None:
            await send({"type": "agent_event", "event": event.to_dict()})

        unsubscribe_events = event_bus.subscribe(forward_event)

        async def approval(name: str, arguments: dict[str, Any], reason: str) -> bool:
            request_id = uuid.uuid4().hex[:12]
            future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
            permission_waiters[request_id] = future
            await send({
                "type": "permission_request",
                "id": request_id,
                "tool": name,
                "arguments": arguments,
                "reason": reason,
            })
            try:
                return await asyncio.wait_for(future, timeout=300)
            except asyncio.TimeoutError:
                return False
            finally:
                permission_waiters.pop(request_id, None)

        runtime = AgentRuntime(
            hub.provider(),
            hub.settings(),
            approval_callback=approval,
            event_bus=event_bus,
        )
        current_run: asyncio.Task[Any] | None = None

        await send({
            "type": "ready",
            "sessionId": runtime.session_id,
            "model": hub.settings().model or "Demo Runtime",
            "demo": isinstance(runtime.provider, DemoProvider),
            "tools": runtime.tools.names,
        })

        async def execute_prompt(prompt: str, goal: str | None = None) -> None:
            try:
                if goal:
                    runtime.set_goal(goal)
                result = await runtime.run(prompt)
                await send({
                    "type": "run_complete",
                    "result": {
                        "text": result.text,
                        "status": result.status,
                        "reason": result.reason,
                        "inputTokens": result.input_tokens,
                        "outputTokens": result.output_tokens,
                        "sessionId": runtime.session_id,
                    },
                })
            except asyncio.CancelledError:
                await send({"type": "run_cancelled"})
            except Exception as exc:
                await send({"type": "error", "message": f"{type(exc).__name__}: {exc}"})

        try:
            while True:
                payload = await ws.receive_json()
                msg_type = payload.get("type")
                if msg_type == "prompt":
                    if current_run and not current_run.done():
                        await send({"type": "error", "message": "An agent run is already active."})
                        continue
                    prompt = str(payload.get("prompt", "")).strip()
                    if not prompt:
                        continue
                    current_run = asyncio.create_task(execute_prompt(prompt, payload.get("goal")))
                elif msg_type == "permission_response":
                    request_id = str(payload.get("id", ""))
                    future = permission_waiters.get(request_id)
                    if future and not future.done():
                        future.set_result(bool(payload.get("allow")))
                elif msg_type == "cancel":
                    if current_run and not current_run.done():
                        current_run.cancel()
                elif msg_type == "new_session":
                    if current_run and not current_run.done():
                        await send({"type": "error", "message": "Finish or cancel the current run first."})
                        continue
                    runtime.messages.clear()
                    runtime.session_id = runtime.sessions.new_id()
                    runtime.input_tokens = 0
                    runtime.output_tokens = 0
                    await send({"type": "session_changed", "sessionId": runtime.session_id})
                elif msg_type == "resume_session":
                    if current_run and not current_run.done():
                        await send({"type": "error", "message": "Finish or cancel the current run first."})
                        continue
                    runtime.load_session(str(payload.get("sessionId", "")))
                    await send({"type": "session_changed", "sessionId": runtime.session_id, "messages": runtime.messages})
        except WebSocketDisconnect:
            pass
        finally:
            if current_run and not current_run.done():
                current_run.cancel()
            unsubscribe_events()
            await runtime.close()

    frontend_dist = root / "web" / "dist"
    if frontend_dist.exists():
        assets = frontend_dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{full_path:path}")
        async def spa(full_path: str):
            requested = frontend_dist / full_path
            if full_path and requested.is_file():
                return FileResponse(requested)
            return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CodeAgent Studio Web IDE")
    parser.add_argument("--workspace", default=os.getenv("CODEAGENT_WORKSPACE", "."))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--demo", action="store_true", help="Use deterministic demo model turns")
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    if args.workspace:
        os.environ["CODEAGENT_WORKSPACE"] = str(Path(args.workspace).resolve())
    if args.demo:
        os.environ["CODEAGENT_WEB_DEMO"] = "1"

    import uvicorn

    uvicorn.run("codeagent.webapp.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
