# learn-claude-code mapping

Upstream learning reference: https://github.com/shareAI-lab/learn-claude-code

| Upstream lesson | Mechanism | This repository |
| --- | --- | --- |
| s01 | Agent Loop | `runtime.py` |
| s02 | Tool Use | `tools/` |
| s03 | Permission | `permission.py` |
| s04 | Hooks | `hooks.py` |
| s05 | TodoWrite | `todo.py` |
| s06 | Subagent | `subagents.py` |
| s07 | Skill Loading | `skills.py` |
| s08 | Context Compact | `context.py` |
| s09 | Memory | `memory.py` |
| s10 | Task System | `tasks.py` |
| s11 | Background Tasks | `background.py` |
| s12 | Cron Scheduler | `scheduler.py` |
| s13 | Agent Teams | `teams.py`, `worktrees.py` |
| s14 | MCP | `mcp.py` |
| s15 | Integrated Harness | `runtime.py` |
| s16 | Workflow Runtime | `workflow.py` |
| s17 | Goal Loop | `goal.py` |

## Independent extensions

`llm/base.py` introduces a provider boundary. `events.py` exposes an event stream for a future Web IDE. `session.py` persists conversations. Centralized direct tool execution ensures workflow steps and other host-driven calls still pass through permission and hook gates.

## Important scope note

This is a mechanism-level reimplementation for learning and experimentation. It does not claim source compatibility with Claude Code or internal implementation equivalence with Anthropic products.
