from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from codeagent.webapp.app import create_app


def seed_workspace(tmp_path: Path) -> None:
    (tmp_path / "src" / "codeagent").mkdir(parents=True)
    (tmp_path / "src" / "codeagent" / "runtime.py").write_text("print('runtime')\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_smoke.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    (tmp_path / "web" / "dist").mkdir(parents=True)
    (tmp_path / "web" / "dist" / "index.html").write_text("<html>studio</html>", encoding="utf-8")


def test_health_and_workspace_file(tmp_path: Path) -> None:
    seed_workspace(tmp_path)
    client = TestClient(create_app(tmp_path, demo=True))
    health = client.get("/api/health").json()
    assert health["status"] == "ok"
    assert health["demo"] is True
    assert health["metrics"]["modules"] == 1

    file = client.get("/api/workspace/file", params={"path": "src/codeagent/runtime.py"}).json()
    assert file["content"] == "print('runtime')\n"


def test_workspace_traversal_is_rejected(tmp_path: Path) -> None:
    seed_workspace(tmp_path)
    client = TestClient(create_app(tmp_path, demo=True))
    response = client.get("/api/workspace/file", params={"path": "../secret.txt"})
    assert response.status_code == 400


def test_agent_websocket_preserves_event_order(tmp_path: Path) -> None:
    seed_workspace(tmp_path)
    client = TestClient(create_app(tmp_path, demo=True))
    with client.websocket_connect("/ws/agent") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        assert ready["demo"] is True
        ws.send_json({"type": "prompt", "prompt": "inspect runtime"})
        received = []
        while True:
            message = ws.receive_json()
            received.append(message)
            if message["type"] == "run_complete":
                break

    events = [item["event"]["type"] for item in received if item["type"] == "agent_event"]
    assert events[0] == "user_prompt"
    assert "tool_start" in events
    assert "tool_end" in events
    assert events[-1] == "final"
    assert received[-1]["type"] == "run_complete"
