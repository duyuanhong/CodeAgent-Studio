from codeagent.llm.base import ModelProvider
from codeagent.llm.scripted import ScriptedProvider

__all__ = ["ModelProvider", "ScriptedProvider", "AnthropicProvider"]


def __getattr__(name: str):
    if name == "AnthropicProvider":
        from codeagent.llm.anthropic import AnthropicProvider
        return AnthropicProvider
    raise AttributeError(name)
