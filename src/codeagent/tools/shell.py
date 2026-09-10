from __future__ import annotations

import asyncio

from codeagent.tools.base import Tool, ToolContext


class BashTool(Tool):
    name = "bash"
    description = "Run a shell command in the workspace and return stdout plus stderr."
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "timeout": {"type": "integer", "minimum": 1, "maximum": 600},
        },
        "required": ["command"],
    }

    async def execute(self, ctx: ToolContext, command: str, timeout: int | None = None) -> str:
        settings = ctx.runtime.settings
        timeout = min(timeout or settings.command_timeout, 600)
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=ctx.workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return f"Error: command timed out after {timeout}s"
        output = (stdout + stderr).decode("utf-8", errors="replace").strip() or "(no output)"
        output = output[: settings.max_tool_output_chars]
        if proc.returncode:
            return f"Error: exit code {proc.returncode}\n{output}"
        return output
