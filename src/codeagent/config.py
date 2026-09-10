from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    workspace: Path = field(default_factory=lambda: Path.cwd().resolve())
    model: str = ""
    anthropic_api_key: str | None = None
    anthropic_base_url: str | None = None
    max_tokens: int = 8000
    max_iterations: int = 80
    context_char_limit: int = 120_000
    keep_recent_tool_results: int = 4
    command_timeout: int = 120
    max_tool_output_chars: int = 50_000
    auto_extract_memory: bool = False
    non_interactive: bool = False

    @property
    def state_dir(self) -> Path:
        return self.workspace / ".codeagent"

    @classmethod
    def from_env(cls, workspace: str | Path | None = None) -> "Settings":
        load_dotenv(override=False)
        base = Path(workspace or os.getenv("CODEAGENT_WORKSPACE") or Path.cwd()).resolve()
        return cls(
            workspace=base,
            model=os.getenv("MODEL_ID", os.getenv("ANTHROPIC_MODEL", "")),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            anthropic_base_url=os.getenv("ANTHROPIC_BASE_URL"),
            max_tokens=int(os.getenv("CODEAGENT_MAX_TOKENS", "8000")),
            max_iterations=int(os.getenv("CODEAGENT_MAX_ITERATIONS", "80")),
            context_char_limit=int(os.getenv("CODEAGENT_CONTEXT_CHAR_LIMIT", "120000")),
            command_timeout=int(os.getenv("CODEAGENT_COMMAND_TIMEOUT", "120")),
            auto_extract_memory=os.getenv("CODEAGENT_AUTO_MEMORY", "0") == "1",
            non_interactive=os.getenv("CODEAGENT_NON_INTERACTIVE", "0") == "1",
        )
