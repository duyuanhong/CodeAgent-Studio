from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from codeagent.background import BackgroundBashTool, BackgroundManager, BackgroundPollTool
from codeagent.config import Settings
from codeagent.context import ContextManager
from codeagent.events import EventBus
from codeagent.goal import GoalController, GoalEvaluator
from codeagent.hooks import HookDecision, HookManager
from codeagent.llm.base import ModelProvider
from codeagent.mcp import ConnectMCPTool, MCPManager
from codeagent.memory import MemoryAddTool, MemorySearchTool, MemoryStore
from codeagent.models import RunResult, ToolCall, ToolResult
from codeagent.permission import ApprovalCallback, PermissionAction, PermissionManager
from codeagent.scheduler import CronAddTool, CronListTool, CronScheduler
from codeagent.session import SessionStore
from codeagent.skills import SkillListTool, SkillLoadTool, SkillStore
from codeagent.subagents import SpawnSubagentTool, SubagentManager
from codeagent.tasks import TaskClaimTool, TaskCompleteTool, TaskCreateTool, TaskListTool, TaskStore, TaskUpdateTool
from codeagent.teams import TeamManager, TeamPollTool, TeamRunTool, TeamSendTool, TeamSpawnTool
from codeagent.todo import TodoStore, TodoWriteTool
from codeagent.tools import BashTool, ToolContext, ToolRegistry, default_file_tools
from codeagent.workflow import WorkflowManager, WorkflowRunTool
from codeagent.worktrees import WorktreeCreateTool, WorktreeListTool, WorktreeManager, WorktreeRemoveTool


class AgentRuntime:
    """One agent loop, surrounded by composable harness mechanisms."""

    def __init__(
        self,
        provider: ModelProvider,
        settings: Settings | None = None,
        *,
        approval_callback: ApprovalCallback | None = None,
        system_suffix: str = "",
        allowed_tools: set[str] | None = None,
        depth: int = 0,
        event_bus: EventBus | None = None,
    ) -> None:
        self.provider = provider
        self.settings = settings or Settings.from_env()
        self.settings.workspace.mkdir(parents=True, exist_ok=True)
        self.settings.state_dir.mkdir(parents=True, exist_ok=True)
        self.depth = depth
        self.system_suffix = system_suffix.strip()
        self.allowed_tools = allowed_tools
        self.events = event_bus or EventBus()
        self.permissions = PermissionManager(approval_callback, self.settings.non_interactive)
        self.hooks = HookManager()
        self.context = ContextManager(self.settings.context_char_limit, self.settings.keep_recent_tool_results)
        self.todos = TodoStore(self.settings.state_dir / "todos.json")
        self.skills = SkillStore(self.settings.workspace)
        self.memory = MemoryStore(self.settings.state_dir / "memory.json")
        self.tasks = TaskStore(self.settings.state_dir / "tasks.json")
        self.worktrees = WorktreeManager(self.settings.workspace, self.settings.state_dir / "worktrees")
        self.background = BackgroundManager()
        self.sessions = SessionStore(self.settings.state_dir / "sessions")
        self.session_id = self.sessions.new_id()
        self.messages: list[dict[str, Any]] = []
        self.input_tokens = 0
        self.output_tokens = 0

        self.tools = ToolRegistry()
        self._register_builtin_tools()
        if "worktree_create" in self.tools.names:
            self.permissions.set_tool_policy("worktree_create", PermissionAction.CONFIRM)
        if "worktree_remove" in self.tools.names:
            self.permissions.set_tool_policy("worktree_remove", PermissionAction.CONFIRM)

        self.subagents = SubagentManager(self)
        self.teams = TeamManager(self)
        self.mcp = MCPManager(self, self.settings.state_dir / "mcp.json")
        self.workflows = WorkflowManager(
            self,
            self.settings.state_dir / "workflows",
            self.settings.state_dir / "workflow_runs",
        )
        self.goal = GoalController(GoalEvaluator(provider))
        self.scheduler = CronScheduler(self._run_scheduled_prompt)

    def _register_builtin_tools(self) -> None:
        tools = [
            BashTool(),
            *default_file_tools(),
            TodoWriteTool(),
            SkillListTool(),
            SkillLoadTool(),
            MemoryAddTool(),
            MemorySearchTool(),
            TaskCreateTool(),
            TaskListTool(),
            TaskUpdateTool(),
            TaskClaimTool(),
            TaskCompleteTool(),
            BackgroundBashTool(),
            BackgroundPollTool(),
            SpawnSubagentTool(),
            TeamRunTool(),
            TeamSpawnTool(),
            TeamSendTool(),
            TeamPollTool(),
            WorktreeCreateTool(),
            WorktreeListTool(),
            WorktreeRemoveTool(),
            ConnectMCPTool(),
            WorkflowRunTool(),
            CronAddTool(),
            CronListTool(),
        ]
        for tool in tools:
            if self.allowed_tools is None or tool.name in self.allowed_tools:
                self.tools.register(tool)

    def spawn_child(self, *, system_suffix: str = "", allowed_tools: set[str] | None = None) -> "AgentRuntime":
        child_settings = Settings(
            workspace=self.settings.workspace,
            model=self.settings.model,
            anthropic_api_key=self.settings.anthropic_api_key,
            anthropic_base_url=self.settings.anthropic_base_url,
            max_tokens=self.settings.max_tokens,
            max_iterations=self.settings.max_iterations,
            context_char_limit=self.settings.context_char_limit,
            keep_recent_tool_results=self.settings.keep_recent_tool_results,
            command_timeout=self.settings.command_timeout,
            max_tool_output_chars=self.settings.max_tool_output_chars,
            auto_extract_memory=False,
            non_interactive=self.settings.non_interactive,
        )
        return AgentRuntime(
            self.provider,
            child_settings,
            approval_callback=self.permissions.approval_callback,
            system_suffix=system_suffix,
            allowed_tools=allowed_tools,
            depth=self.depth + 1,
            event_bus=self.events,
        )

    def system_prompt(self, user_prompt: str = "") -> str:
        memory = self.memory.render_recall(user_prompt, 6) if user_prompt else "(none)"
        skill_catalog = self.skills.catalog()
        prompt = f"""You are CodeAgent, a coding agent operating inside this workspace:
{self.settings.workspace}

You have tools for inspecting and editing files, running commands, planning work, memory, tasks, subagents, teams, MCP, workflows, and scheduling when those tools are registered.

Operating rules:
1. Inspect relevant code before editing it.
2. Prefer small, verifiable changes.
3. Use tools when evidence is required. Never claim a command succeeded without a tool result.
4. Keep file operations inside the workspace.
5. Respect permission denials. Do not try equivalent bypass commands after a denial.
6. Use todo_write for multi-step tasks when a plan materially improves reliability.
7. Load skills on demand. Do not assume unloaded skill contents.
8. Before finishing a code change, run the most relevant available checks when practical.

Relevant persistent memory:
{memory}

Available on-demand skills:
{skill_catalog}
"""
        if self.system_suffix:
            prompt += "\nRole-specific instructions:\n" + self.system_suffix
        return prompt

    async def run(self, prompt: str, *, save_session: bool = True) -> RunResult:
        await self.events.emit("user_prompt", prompt=prompt, session_id=self.session_id, depth=self.depth)
        hook_block = await self.hooks.first_block("user_prompt_submit", runtime=self, prompt=prompt)
        if hook_block:
            return RunResult("", self.messages, status="blocked", reason=hook_block.reason)
        self.messages.append({"role": "user", "content": prompt})
        last_text = ""

        for iteration in range(1, self.settings.max_iterations + 1):
            notifications = self.background.collect_notifications()
            if notifications:
                note = "Background job notifications:\n" + "\n\n".join(notifications)
                self.messages.append({"role": "user", "content": note})
                await self.events.emit("background_notifications", notifications=notifications)

            prepared = self.context.prepare(self.messages)
            if prepared is not self.messages:
                await self.events.emit(
                    "context_compacted",
                    before_chars=self.context.estimate(self.messages),
                    after_chars=self.context.estimate(prepared),
                )
            await self.hooks.trigger("before_model", runtime=self, messages=prepared)
            await self.events.emit("model_start", iteration=iteration)
            turn = await self.provider.complete(
                messages=prepared,
                system=self.system_prompt(prompt),
                tools=self.tools.schemas(),
                max_tokens=self.settings.max_tokens,
            )
            self.input_tokens += turn.input_tokens
            self.output_tokens += turn.output_tokens
            self.messages.append({"role": "assistant", "content": turn.blocks or turn.text})
            last_text = turn.text
            await self.events.emit(
                "model_end",
                iteration=iteration,
                text=turn.text,
                tool_count=len(turn.tool_calls),
                input_tokens=turn.input_tokens,
                output_tokens=turn.output_tokens,
            )
            await self.hooks.trigger("after_model", runtime=self, turn=turn)

            if turn.tool_calls:
                results: list[dict[str, Any]] = []
                for call in turn.tool_calls:
                    result = await self._execute_call(call)
                    results.append(result.as_block())
                self.messages.append({"role": "user", "content": results})
                continue

            stop_block = await self.hooks.first_block("stop", runtime=self, text=turn.text, messages=self.messages)
            if stop_block:
                self.messages.append({"role": "user", "content": f"Stop hook blocked completion: {stop_block.reason}\nContinue the task."})
                await self.events.emit("stop_blocked", reason=stop_block.reason)
                continue

            action, reason = await self.goal.on_proposed_stop(self.messages)
            await self.events.emit("goal_decision", action=action, reason=reason, condition=self.goal.condition)
            if action == "block":
                self.messages.append({"role": "user", "content": f"Goal evaluator says completion is not yet proven: {reason}\nContinue working toward the active goal."})
                continue
            if action in {"failed", "limit"}:
                result = RunResult(last_text, self.messages, status=action, reason=reason, input_tokens=self.input_tokens, output_tokens=self.output_tokens)
                if save_session:
                    self._save_session(result)
                return result

            result = RunResult(last_text, self.messages, input_tokens=self.input_tokens, output_tokens=self.output_tokens)
            if self.settings.auto_extract_memory and self.depth == 0:
                await self._extract_memories(prompt, last_text)
            if save_session:
                self._save_session(result)
            await self.events.emit("final", text=last_text, session_id=self.session_id)
            return result

        result = RunResult(
            last_text,
            self.messages,
            status="iteration_limit",
            reason=f"max iterations reached: {self.settings.max_iterations}",
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )
        if save_session:
            self._save_session(result)
        return result

    async def _execute_call(self, call: ToolCall) -> ToolResult:
        output, is_error = await self._execute_tool(call.name, call.arguments)
        return ToolResult(call.id, output, is_error=is_error)

    async def execute_tool_direct(self, name: str, arguments: dict[str, Any]) -> str:
        output, _ = await self._execute_tool(name, arguments)
        return output

    async def _execute_tool(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        await self.events.emit("tool_requested", name=name, arguments=arguments)
        pre_block = await self.hooks.first_block("pre_tool_use", runtime=self, name=name, arguments=arguments)
        if pre_block:
            await self.events.emit("tool_denied", name=name, reason=pre_block.reason)
            return f"Permission denied by hook: {pre_block.reason}", True

        decision = await self.permissions.authorize(name, arguments)
        await self.events.emit("permission", name=name, action=decision.action.value, reason=decision.reason)
        if decision.action != PermissionAction.ALLOW:
            return f"Permission denied: {decision.reason}", True

        await self.events.emit("tool_start", name=name, arguments=arguments)
        output = await self.tools.execute(name, ToolContext(runtime=self, workspace=self.settings.workspace), arguments)
        is_error = output.startswith("Error:")
        await self.hooks.trigger("post_tool_use", runtime=self, name=name, arguments=arguments, output=output)
        await self.events.emit("tool_end", name=name, output=output, is_error=is_error)
        return output, is_error

    def set_goal(self, condition: str) -> None:
        self.goal.set(condition)

    def load_session(self, session_id: str) -> None:
        payload = self.sessions.load(session_id)
        self.session_id = session_id
        self.messages = list(payload.get("messages", []))

    async def _run_scheduled_prompt(self, prompt: str) -> None:
        child = self.spawn_child(system_suffix="This task was triggered by the scheduler.")
        try:
            await child.run(prompt, save_session=True)
        finally:
            await child.close()

    async def _extract_memories(self, user_prompt: str, answer: str) -> None:
        request = (
            "Extract only durable information that will improve future coding assistance. "
            "Return JSON array of objects with content and kind, where kind is user, feedback, project, or reference. "
            "Return [] when nothing should be remembered.\n\n"
            + json.dumps({"user": user_prompt, "assistant": answer}, ensure_ascii=False)
        )
        try:
            turn = await self.provider.complete(
                messages=[{"role": "user", "content": request}],
                system="You are a conservative memory extractor. Do not store secrets, transient status, or guesses.",
                tools=[],
                max_tokens=600,
            )
            raw = turn.text.strip()
            if raw.startswith("```"):
                lines = raw.splitlines()[1:]
                if lines and lines[-1].strip() == "```":
                    lines.pop()
                raw = "\n".join(lines)
            items = json.loads(raw)
            if isinstance(items, list):
                for item in items[:8]:
                    if isinstance(item, dict) and item.get("content"):
                        self.memory.add(str(item["content"]), str(item.get("kind", "project")))
        except Exception:
            return

    def _save_session(self, result: RunResult) -> None:
        self.sessions.save(
            self.session_id,
            self.messages,
            {
                "status": result.status,
                "reason": result.reason,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
            },
        )

    async def close(self) -> None:
        await self.teams.close()
        await self.mcp.close()
        if self.scheduler._runner and not self.scheduler._runner.done():
            await self.scheduler.stop()
