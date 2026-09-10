from __future__ import annotations

import json
import re
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codeagent.permission import PermissionAction
from codeagent.tools.base import Tool, ToolContext


_NAME = re.compile(r"[^A-Za-z0-9_-]")


def normalize_name(value: str) -> str:
    cleaned = _NAME.sub("_", value)
    if not cleaned:
        raise ValueError("MCP name becomes empty after normalization")
    return cleaned


@dataclass(slots=True)
class MCPServerConfig:
    name: str
    command: str
    args: list[str]
    env: dict[str, str] | None = None


class MCPProxyTool(Tool):
    def __init__(self, manager: "MCPManager", server: str, remote_name: str, description: str, schema: dict[str, Any]) -> None:
        self.manager = manager
        self.server = server
        self.remote_name = remote_name
        self.name = f"mcp__{normalize_name(server)}__{normalize_name(remote_name)}"
        if len(self.name) > 64:
            raise ValueError(f"MCP tool name is longer than 64 characters: {self.name}")
        self.description = description
        self.input_schema = schema or {"type": "object", "properties": {}}

    async def execute(self, ctx: ToolContext, **kwargs: Any) -> str:
        return await self.manager.call(self.server, self.remote_name, kwargs)


class MCPManager:
    """Optional official MCP SDK adapter. Servers are declared by the host in .codeagent/mcp.json."""

    def __init__(self, runtime: Any, config_path: Path) -> None:
        self.runtime = runtime
        self.config_path = config_path
        self.configs: dict[str, MCPServerConfig] = {}
        self.sessions: dict[str, Any] = {}
        self.stacks: dict[str, AsyncExitStack] = {}
        self.load_config()

    def load_config(self) -> None:
        if not self.config_path.exists():
            return
        raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        for name, item in raw.get("mcpServers", {}).items():
            self.configs[name] = MCPServerConfig(
                name=name,
                command=item["command"],
                args=list(item.get("args", [])),
                env=dict(item.get("env", {})) or None,
            )

    async def connect(self, name: str) -> str:
        if name in self.sessions:
            return f"MCP server '{name}' already connected"
        cfg = self.configs.get(name)
        if cfg is None:
            return f"Error: unknown MCP server '{name}'. Configured: {', '.join(self.configs) or '(none)'}"
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            return "Error: MCP support requires `pip install -e '.[mcp]'`"

        stack = AsyncExitStack()
        try:
            params = StdioServerParameters(command=cfg.command, args=cfg.args, env=cfg.env)
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            listing = await session.list_tools()
            names: list[str] = []
            for remote in listing.tools:
                proxy = MCPProxyTool(
                    manager=self,
                    server=name,
                    remote_name=remote.name,
                    description=remote.description or "",
                    schema=remote.inputSchema or {"type": "object", "properties": {}},
                )
                if proxy.name in self.runtime.tools.names:
                    raise ValueError(f"MCP tool collision: {proxy.name}")
                self.runtime.tools.register(proxy)
                # Unknown external tools default to confirmation. Hosts may relax this explicitly.
                self.runtime.permissions.set_tool_policy(proxy.name, PermissionAction.CONFIRM)
                names.append(proxy.name)
            self.sessions[name] = session
            self.stacks[name] = stack
            return f"Connected '{name}': {', '.join(names) or '(no tools)'}"
        except Exception:
            await stack.aclose()
            raise

    async def call(self, server: str, tool: str, arguments: dict[str, Any]) -> str:
        session = self.sessions.get(server)
        if session is None:
            return f"Error: MCP server '{server}' is not connected"
        result = await session.call_tool(tool, arguments)
        pieces: list[str] = []
        for item in getattr(result, "content", []) or []:
            text = getattr(item, "text", None)
            pieces.append(str(text if text is not None else item))
        return "\n".join(pieces) if pieces else str(result)

    async def close(self) -> None:
        for stack in list(self.stacks.values()):
            await stack.aclose()
        self.sessions.clear()
        self.stacks.clear()


class ConnectMCPTool(Tool):
    name = "connect_mcp"
    description = "Connect a host-configured MCP server and dynamically register its tools."
    input_schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }

    async def execute(self, ctx: ToolContext, name: str) -> str:
        return await ctx.runtime.mcp.connect(name)
