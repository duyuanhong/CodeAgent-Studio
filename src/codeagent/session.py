from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


class SessionStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def new_id(self) -> str:
        return time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]

    def save(self, session_id: str, messages: list[dict[str, Any]], metadata: dict[str, Any] | None = None) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{session_id}.json"
        payload = {"session_id": session_id, "messages": messages, "metadata": metadata or {}}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path

    def load(self, session_id: str) -> dict[str, Any]:
        path = self.root / f"{session_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"unknown session: {session_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list(self) -> list[str]:
        if not self.root.exists():
            return []
        return [path.stem for path in sorted(self.root.glob("*.json"), reverse=True)]
