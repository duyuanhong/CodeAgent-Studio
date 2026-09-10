# CodeAgent Studio Web IDE

The Phase 2 interface is served by the same Python package as the Harness Core.

## Run

```bash
pip install -e ".[web,dev]"
python web/build.py
codeagent-web --workspace . --demo
```

Open `http://127.0.0.1:8765`.

Remove `--demo` after configuring `ANTHROPIC_API_KEY` and `MODEL_ID` to use a live provider.

## Surfaces

The workspace is intentionally dense and desktop-oriented. Explorer, Sessions, Tasks, Worktrees and Workflows live in the activity rail. The center contains the editable code surface, Git comparison view and local terminal. The Agent Console contains conversation, a strict-order execution Trace, runtime Inspector, completion Goal and host-controlled permission approvals.

The browser client communicates through REST for repository operations and WebSocket for agent execution. UI state derives from the same EventBus emitted by `AgentRuntime`.

## Frontend build

`web/build.py` copies `web/src` plus vendored Prism assets into `web/dist`. There is no mandatory npm dependency for the portfolio build. This is deliberate so the artifact can be built and demonstrated in restricted environments.

Visual rationale and current-market references are documented in `../docs/DESIGN_RESEARCH.md`.
