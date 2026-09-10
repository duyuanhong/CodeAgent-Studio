from codeagent.permission import PermissionAction, PermissionManager


def test_hard_deny_shell_command():
    manager = PermissionManager(non_interactive=True)
    decision = manager.check("bash", {"command": "rm -rf /"})
    assert decision.action == PermissionAction.DENY


def test_destructive_command_requires_confirmation():
    manager = PermissionManager(non_interactive=True)
    decision = manager.check("bash", {"command": "rm build.log"})
    assert decision.action == PermissionAction.CONFIRM
