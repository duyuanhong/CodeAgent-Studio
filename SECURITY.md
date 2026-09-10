# Security

CodeAgent Studio is a local developer tool that can execute model-requested shell commands and modify repository files. Treat the model and all tool inputs as untrusted.

## Trust boundaries

The runtime provides application-level guardrails:

- repository-relative file access
- path traversal checks
- host-controlled permission policy
- confirmation for risky tool calls
- deny patterns for destructive shell commands
- lifecycle hooks and observable execution events

These controls reduce accidental damage. They are **not** a hardened sandbox and do not provide kernel-level isolation.

## Safe usage

Use CodeAgent Studio only inside repositories you are willing to modify. Before running a live model:

1. Commit or back up important work.
2. Review the active workspace path.
3. Keep API keys in `.env`; never commit them.
4. Do not expose the local Web IDE directly to an untrusted network.
5. Run untrusted repositories or autonomous workloads inside a disposable container or VM.

## Public deployment

A public deployment should add an OS-level sandbox or disposable container per session, authentication, quotas, CPU/memory/time limits, network policy, audit logging, and explicit secret isolation. The built-in permission system should remain as a second layer, not the primary containment boundary.

## Reporting a vulnerability

Please open a GitHub issue without publishing secrets, credentials, or exploit payloads that could harm other users. For a sensitive report, contact the repository owner privately through GitHub before posting reproduction details.
