# Demo guide

This walkthrough demonstrates the runtime in roughly two minutes without requiring an API key.

## Start

```bash
conda activate codeagent
python web/build.py
codeagent-web --workspace . --demo
```

Open `http://127.0.0.1:8765`.

## Walkthrough

### 1. Open the runtime

Use Explorer or `Ctrl/Cmd + K` to open `src/codeagent/runtime.py`. Point out that the editor and file tree operate on the same workspace used by the agent.

### 2. Run an agent task

Use the Run button or ask:

```text
Inspect this repository and explain the most important runtime boundary. Use tools to verify the answer.
```

The deterministic demo provider still runs through `AgentRuntime`, permissions, tool dispatch, and the event stream.

### 3. Open Trace

Switch from **Agent** to **Trace**. Show the ordered sequence:

```text
model turn
→ tool requested
→ permission decision
→ tool start
→ tool result
→ next model turn
→ final
```

This is the key observability surface.

### 4. Open Inspect

Switch to **Inspect** and show runtime state, tool surface, session information, context usage, and permission policy.

### 5. Show the terminal

Run a harmless command such as:

```bash
pytest -q
```

Explain that destructive shell requests pass through the host permission policy.

### 6. Show long-running primitives

Open the left navigation and briefly show Sessions, Tasks, Worktrees, and Workflows. These map to persisted runtime objects rather than decorative UI panels.

## Live-model demo

For a live session, configure `.env` and start without `--demo`:

```bash
codeagent-web --workspace .
```

A useful end-to-end prompt is:

```text
Inspect the current repository, find one small maintainability issue, make a safe improvement, run the relevant tests, and summarize the diff.
```

Commit or back up the repository before allowing a live model to edit files.
