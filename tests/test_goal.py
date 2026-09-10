from pathlib import Path

import pytest

from codeagent.config import Settings
from codeagent.llm.scripted import ScriptedProvider
from codeagent.models import ModelTurn
from codeagent.runtime import AgentRuntime


@pytest.mark.asyncio
async def test_goal_evaluator_allows_verified_stop(tmp_path: Path):
    worker = ModelTurn(blocks=[{"type": "text", "text": "Tests passed."}], text="Tests passed.")
    evaluator = ModelTurn(
        blocks=[{"type": "text", "text": '{"ok": true, "reason": "test result is present", "impossible": false}'}],
        text='{"ok": true, "reason": "test result is present", "impossible": false}',
    )
    provider = ScriptedProvider([worker, evaluator])
    runtime = AgentRuntime(provider, Settings(workspace=tmp_path, non_interactive=True))
    runtime.set_goal("tests passed")
    result = await runtime.run("Finish the task", save_session=False)
    assert result.status == "completed"
    assert runtime.goal.condition is None
    await runtime.close()
