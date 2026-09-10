from pathlib import Path

import pytest

from codeagent.config import Settings
from codeagent.llm.scripted import ScriptedProvider
from codeagent.models import ModelTurn, ToolCall
from codeagent.runtime import AgentRuntime


@pytest.mark.asyncio
async def test_agent_loop_executes_tool_and_returns_final(tmp_path: Path):
    (tmp_path / "hello.txt").write_text("hello harness", encoding="utf-8")
    first = ModelTurn(
        blocks=[{"type": "tool_use", "id": "call_1", "name": "read_file", "input": {"path": "hello.txt"}}],
        text="",
        tool_calls=[ToolCall("call_1", "read_file", {"path": "hello.txt"})],
    )
    second = ModelTurn(blocks=[{"type": "text", "text": "I found the file."}], text="I found the file.")
    provider = ScriptedProvider([first, second])
    runtime = AgentRuntime(provider, Settings(workspace=tmp_path, non_interactive=True))

    result = await runtime.run("Read hello.txt", save_session=False)

    assert result.status == "completed"
    assert result.text == "I found the file."
    assert len(provider.requests) == 2
    second_request = provider.requests[1]["messages"]
    tool_result_message = second_request[-1]
    assert tool_result_message["role"] == "user"
    assert tool_result_message["content"][0]["type"] == "tool_result"
    assert "hello harness" in tool_result_message["content"][0]["content"]
    await runtime.close()
