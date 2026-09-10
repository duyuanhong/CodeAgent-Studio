import pytest

from codeagent.worktrees import WorktreeManager


def test_worktree_name_validation():
    assert WorktreeManager.validate_name("task-123") == "task-123"
    with pytest.raises(ValueError):
        WorktreeManager.validate_name("../escape")
