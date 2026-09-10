from pathlib import Path

import pytest

from codeagent.config import Settings
from codeagent.llm.scripted import ScriptedProvider
from codeagent.runtime import AgentRuntime


@pytest.mark.asyncio
async def test_workflow_tool_steps_and_resume(tmp_path: Path):
    runtime = AgentRuntime(ScriptedProvider([]), Settings(workspace=tmp_path, non_interactive=True))
    root = tmp_path / ".codeagent" / "workflows"
    root.mkdir(parents=True, exist_ok=True)
    (root / "files.yaml").write_text(
        """steps:\n  - id: write\n    type: tool\n    tool: write_file\n    args:\n      path: generated.txt\n      content: hello\n  - id: read\n    type: tool\n    tool: read_file\n    args:\n      path: generated.txt\n""",
        encoding="utf-8",
    )
    run = await runtime.workflows.run("files")
    assert run.status == "completed"
    assert (tmp_path / "generated.txt").read_text(encoding="utf-8") == "hello"
    resumed = await runtime.workflows.run("files", run_id=run.run_id)
    assert resumed.results == run.results
    await runtime.close()
