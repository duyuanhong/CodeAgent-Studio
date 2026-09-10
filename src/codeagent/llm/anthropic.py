from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from anthropic import Anthropic

from codeagent.llm.base import ModelProvider
from codeagent.models import ModelTurn, ToolCall


class AnthropicProvider(ModelProvider):
    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        if not model:
            raise ValueError("MODEL_ID or ANTHROPIC_MODEL is required")
        self.model = model
        kwargs: dict[str, Any] = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        self.client = Anthropic(**kwargs)

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str,
        tools: Sequence[dict[str, Any]],
        max_tokens: int,
    ) -> ModelTurn:
        return await asyncio.to_thread(
            self._complete_sync,
            messages,
            system,
            list(tools),
            max_tokens,
        )

    def _complete_sync(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]],
        max_tokens: int,
    ) -> ModelTurn:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        response = self.client.messages.create(**kwargs)

        blocks: list[dict[str, Any]] = []
        tool_calls: list[ToolCall] = []
        texts: list[str] = []
        for block in response.content:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text = str(getattr(block, "text", ""))
                blocks.append({"type": "text", "text": text})
                texts.append(text)
            elif block_type == "tool_use":
                call = ToolCall(
                    id=str(block.id),
                    name=str(block.name),
                    arguments=dict(block.input or {}),
                )
                tool_calls.append(call)
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": call.id,
                        "name": call.name,
                        "input": call.arguments,
                    }
                )

        usage = getattr(response, "usage", None)
        return ModelTurn(
            blocks=blocks,
            text="\n".join(texts).strip(),
            tool_calls=tool_calls,
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        )
