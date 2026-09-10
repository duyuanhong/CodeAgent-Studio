from codeagent.context import ContextManager


def test_compacts_old_tool_results():
    messages = [
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "1", "name": "bash", "input": {"command": "x"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "1", "content": "x" * 10000}]},
        {"role": "assistant", "content": [{"type": "text", "text": "continue"}]},
    ]
    manager = ContextManager(char_limit=3000, keep_recent_tool_results=0)
    compacted = manager.prepare(messages)
    serialized = str(compacted)
    assert "compacted" in serialized
    assert len(serialized) < len(str(messages))


def test_retained_context_never_starts_with_dangling_tool_result():
    messages = [
        {"role": "user", "content": "old" * 3000},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "read_file", "input": {"path": "a"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "result" * 500}]},
        {"role": "assistant", "content": [{"type": "text", "text": "latest"}]},
    ]
    manager = ContextManager(char_limit=1600, keep_recent_tool_results=1)
    compacted = manager.prepare(messages)
    for index, message in enumerate(compacted):
        content = message.get("content")
        if isinstance(content, list) and any(block.get("type") == "tool_result" for block in content):
            assert index > 0
            previous = compacted[index - 1].get("content")
            assert isinstance(previous, list)
            assert any(block.get("type") == "tool_use" for block in previous)
