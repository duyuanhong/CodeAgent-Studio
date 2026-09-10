from pathlib import Path

import pytest

from codeagent.tasks import TaskStore


def test_task_dependencies_and_claim(tmp_path: Path):
    store = TaskStore(tmp_path / "tasks.json")
    a = store.create("inspect")
    b = store.create("implement", blocked_by=[a.id])
    with pytest.raises(ValueError):
        store.claim(b.id, "coder")
    store.complete(a.id)
    claimed = store.claim(b.id, "coder")
    assert claimed.status == "in_progress"
    assert claimed.owner == "coder"


def test_task_cycle_rejected(tmp_path: Path):
    store = TaskStore(tmp_path / "tasks.json")
    a = store.create("a")
    b = store.create("b", blocked_by=[a.id])
    with pytest.raises(ValueError, match="cycle"):
        store.update(a.id, blocked_by=[b.id])
