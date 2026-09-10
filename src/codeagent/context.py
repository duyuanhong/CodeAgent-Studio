from __future__ import annotations

import copy
import json
from typing import Any


class ContextManager:
    """Keeps tool-call pairs valid while shrinking old tool output first."""

    def __init__(self, char_limit: int = 120_000, keep_recent_tool_results: int = 4) -> None:
        self.char_limit = char_limit
        self.keep_recent_tool_results = keep_recent_tool_results

    @staticmethod
    def estimate(messages: list[dict[str, Any]]) -> int:
        return len(json.dumps(messages, ensure_ascii=False, default=str))

    def prepare(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.estimate(messages) <= self.char_limit:
            return messages
        compacted = copy.deepcopy(messages)
        positions: list[tuple[int, int]] = []
        for mi, message in enumerate(compacted):
            content = message.get("content")
            if isinstance(content, list):
                for bi, block in enumerate(content):
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        positions.append((mi, bi))
        for mi, bi in positions[: max(0, len(positions) - self.keep_recent_tool_results)]:
            block = compacted[mi]["content"][bi]
            raw = str(block.get("content", ""))
            if len(raw) > 1000:
                block["content"] = raw[:400] + f"\n...[compacted {len(raw) - 800} chars]...\n" + raw[-400:]
            if self.estimate(compacted) <= self.char_limit:
                return compacted

        # Keep recent complete messages. This is a final guard when tool-result
        # shrinking is still insufficient. A summary marker records truncation.
        size = 0
        budget = max(1000, self.char_limit - 1000)
        start = len(compacted)
        for index in range(len(compacted) - 1, -1, -1):
            message = compacted[index]
            item_size = len(json.dumps(message, ensure_ascii=False, default=str))
            if start < len(compacted) and size + item_size > budget:
                break
            start = index
            size += item_size

        # Never start the retained suffix with a dangling tool_result. Anthropic
        # requires every tool_result to have its preceding assistant tool_use.
        if start > 0 and self._contains_tool_result(compacted[start]):
            previous = compacted[start - 1]
            if previous.get("role") == "assistant" and self._contains_tool_use(previous):
                start -= 1

        selected = compacted[start:]
        return [{"role": "user", "content": "[Earlier conversation compacted by ContextManager]"}, *selected]

    @staticmethod
    def _contains_tool_result(message: dict[str, Any]) -> bool:
        content = message.get("content")
        return isinstance(content, list) and any(
            isinstance(block, dict) and block.get("type") == "tool_result" for block in content
        )

    @staticmethod
    def _contains_tool_use(message: dict[str, Any]) -> bool:
        content = message.get("content")
        return isinstance(content, list) and any(
            isinstance(block, dict) and block.get("type") == "tool_use" for block in content
        )
