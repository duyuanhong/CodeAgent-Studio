# CodeAgent Studio UI Research

Research date: 2026-09-10

This document records the product and interface research behind the Phase 2 Web IDE. The goal is to learn from current best-in-class developer tools while keeping the final system visually and structurally original.

## 1. Market direction: agent-first workspaces

Cursor 3.0, released on 2026-04-02, introduced an Agents Window that can run multiple agents across local repositories, Git worktrees, cloud environments, remote SSH, and other environments while retaining full IDE depth.

Source: Cursor, "New Cursor Interface"  
https://cursor.com/changelog/3-0

VS Code's 2026 Agents Window follows the same direction. GitHub's July 2026 Copilot update added side-by-side code review, compact diffs, worktree-backed sessions, grouped sessions, and visible subagent status. The August 2026 update continued improving multi-chat and review workflows.

Sources:  
https://github.blog/changelog/2026-07-30-github-copilot-in-visual-studio-code-july-2026-releases/  
https://github.blog/changelog/2026-08-31-github-copilot-in-vs-code-august-2026-releases/

### CodeAgent decision

The Agent Console is a first-class workspace next to code, review, terminal and repository state. It is not a floating chatbot. Sessions, task graphs, worktrees, permission decisions and traces are part of the same execution surface.

## 2. Direct manipulation and spatial context

Cursor Design Mode lets a user select UI elements, draw on the page, or provide voice instructions while preserving visual and code context. Replit Agent 4 moved further toward a Design Canvas where interactive previews and design mockups can be manipulated while agents continue working.

Sources:  
https://cursor.com/blog/design-mode  
https://replit.com/blog/whats-changed-agent3-to-agent4

### CodeAgent decision

Phase 2 keeps editor, Git review, terminal and agent trace spatially adjacent. The runtime EventBus and WebSocket transport are designed so a later browser preview or direct-manipulation surface can consume the same event model without adding a second orchestration layer.

## 3. Calm density beats decorative AI styling

Linear's March 2026 UI refresh focused on a calmer, more consistent interface, with dimmer navigation, consistent headers and view controls, and reduced visual competition around the primary work surface.

Sources:  
https://linear.app/changelog/2026-03-12-ui-refresh  
https://linear.app/now/behind-the-latest-design-refresh

### CodeAgent decision

The visual system is called **Quiet Density**:

- warm graphite surfaces instead of pure black
- low-contrast separators instead of card-heavy chrome
- one copper-orange accent rather than purple/blue AI gradients
- compact type and row heights suitable for professional developer tools
- almost no ornamental motion
- state colors reserved for real operational meaning

## 4. Navigation should follow real developer workflows

Vercel's 2026 dashboard redesign moved frequently used navigation into a resizable sidebar, unified navigation patterns between team and project scopes, and reordered items around common workflows.

Source:  
https://vercel.com/changelog/dashboard-navigation-redesign-rollout

### CodeAgent decision

The activity rail prioritizes Explorer, Sessions, Tasks, Worktrees and Workflows. These are durable runtime objects rather than arbitrary feature buckets.

## 5. Explicit agent modes and operational state

Windsurf Cascade separates Code, Plan and Ask modes and exposes planning, tools, terminal, memory, MCP and workflows. This reinforces that serious agent UX must expose execution state rather than reduce everything to conversational messages.

Sources:  
https://docs.windsurf.com/windsurf/cascade/modes  
https://docs.windsurf.com/windsurf/cascade/cascade

### CodeAgent decision

Agent, Trace and Inspect are separate views. The composer exposes completion Goal state. Destructive operations interrupt the run with a host-controlled permission gate. The Trace view shows actual event order instead of rendering a fabricated "thinking" animation.

## 6. Keyboard, focus and state completeness are baseline quality

Vercel's Web Interface Guidelines explicitly recommend full keyboard operability, visible focus, correct focus management, adequate hit targets, stable interaction states, and accessible behavior.

Source:  
https://vercel.com/design/guidelines

Raycast similarly treats keyboard-first navigation and a discoverable action panel as fundamental interaction patterns rather than optional shortcuts.

Sources:  
https://manual.raycast.com/quickstart  
https://developers.raycast.com/api-reference/user-interface

### CodeAgent decision

CodeAgent Studio includes a command palette, keyboard save, terminal toggle, diff shortcut, visible focus rings, connection/error states, command discovery and clear permission actions.

## Original design system: Quiet Density

| Token | Decision |
| --- | --- |
| Core surfaces | graphite black, `#090b0e` to `#151a20` |
| Primary accent | copper orange, approximately `#d09461` |
| Status colors | desaturated green, amber, red and blue |
| Corners | mostly 4 to 6 px |
| Structure | 1 px low-contrast separators, very limited shadows |
| Typography | native sans UI stack + native monospace code stack |
| Density | 22 to 34 px rows, compact metadata, dense code surfaces |
| Motion | state transitions and progress only |
| Brand mark | compact `CA` terminal-style monogram |

## Information architecture

```text
Top command bar
  repository / branch / command palette / runtime / model / run

Activity rail
  Explorer / Sessions / Tasks / Worktrees / Workflows

Main work surface
  editor tabs / code editor / review diff / terminal

Runtime session
  Agent / Trace / Inspect / Permission Gate / Prompt + Goal

Status bar
  branch / editor buffer / permission / runtime / tools / provider / socket
```

## Evaluation criterion

A first-time user should understand the product category and technical differentiation in one screen. An engineer should be able to click deeper and find real runtime behavior behind every important visible surface. The UI therefore exposes the same objects used by the Python Harness instead of presenting a disconnected mock dashboard.
