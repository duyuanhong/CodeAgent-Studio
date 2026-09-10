# Changelog

All notable project changes are documented here.

## 0.2.1 - 2026-09-10

### Changed

- Increased Web IDE typography and panel proportions for improved HiDPI readability.
- Fixed command-palette visibility so the hidden overlay no longer leaves the workspace dimmed.
- Removed backdrop blur from the command palette and retained a simple dim layer.
- Reworked repository documentation around architecture, runtime verification, security, and demo flow.
- Added GitHub Actions CI for Python 3.10, 3.11, and 3.12.
- Added repository-wide LF normalization rules through `.gitattributes`.

## 0.2.0 - 2026-09-10

### Added

- FastAPI + WebSocket Web IDE gateway.
- Explorer, editor, diff review, terminal, Agent / Trace / Inspect views, sessions, tasks, worktrees, workflows, permission approval, and goal UI.
- Runtime `EventBus` integration for ordered execution traces.
- Quiet Density visual system and design research notes.

## 0.1.0 - 2026-09-10

### Added

- Core coding-agent runtime.
- Tool registry, permissions, hooks, todo, skills, context compaction, memory, tasks, background execution, cron, subagents, teams, worktrees, MCP, resumable workflows, goal loop, sessions, and deterministic test provider.
