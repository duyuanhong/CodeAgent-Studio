from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable


class PermissionAction(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


@dataclass(slots=True)
class PermissionDecision:
    action: PermissionAction
    reason: str = ""


ApprovalCallback = Callable[[str, dict[str, Any], str], bool | Awaitable[bool]]


class PermissionManager:
    """Host-owned permission gate. Tool descriptions never grant authority."""

    HARD_DENY = (
        "rm -rf /",
        "sudo shutdown",
        "shutdown -h",
        "shutdown -r",
        "reboot",
        "mkfs",
        "dd if=",
        ":(){:|:&};:",
    )
    CONFIRM_PATTERNS = (
        re.compile(r"(?i)(?:^|[;&|()\n])\s*(?:rm|del)(?=\s|$|[;&|()])"),
        re.compile(r"(?i)\bgit\s+(?:reset\s+--hard|clean\s+-[a-z]*f|push\s+.*--force)\b"),
        re.compile(r"(?i)\b(?:pip|npm|pnpm|yarn)\s+(?:publish|unpublish)\b"),
        re.compile(r"(?i)\bchmod\s+777\b"),
    )

    def __init__(self, approval_callback: ApprovalCallback | None = None, non_interactive: bool = False) -> None:
        self.approval_callback = approval_callback
        self.non_interactive = non_interactive
        self.tool_overrides: dict[str, PermissionAction] = {}

    def set_tool_policy(self, tool_name: str, action: PermissionAction | str) -> None:
        self.tool_overrides[tool_name] = PermissionAction(action)

    def check(self, tool_name: str, arguments: dict[str, Any]) -> PermissionDecision:
        override = self.tool_overrides.get(tool_name)
        if override:
            return PermissionDecision(override, f"tool policy: {override.value}")
        if tool_name in {"bash", "background_bash"}:
            command = str(arguments.get("command", ""))
            lowered = command.lower()
            for pattern in self.HARD_DENY:
                if pattern.lower() in lowered:
                    return PermissionDecision(PermissionAction.DENY, f"hard-deny pattern: {pattern}")
            if any(pattern.search(command) for pattern in self.CONFIRM_PATTERNS):
                return PermissionDecision(PermissionAction.CONFIRM, "potentially destructive shell command")
        return PermissionDecision(PermissionAction.ALLOW)

    async def authorize(self, tool_name: str, arguments: dict[str, Any]) -> PermissionDecision:
        decision = self.check(tool_name, arguments)
        if decision.action != PermissionAction.CONFIRM:
            return decision
        if self.non_interactive or self.approval_callback is None:
            return PermissionDecision(PermissionAction.DENY, "confirmation required in non-interactive mode")
        allowed = self.approval_callback(tool_name, arguments, decision.reason)
        if inspect.isawaitable(allowed):
            allowed = await allowed
        return PermissionDecision(
            PermissionAction.ALLOW if allowed else PermissionAction.DENY,
            "approved by user" if allowed else "denied by user",
        )
