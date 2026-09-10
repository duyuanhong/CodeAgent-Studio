# Code Review

Use this skill when the user asks for a repository or patch review.

## Procedure

1. Inspect the changed files and surrounding call sites.
2. Prioritize correctness, security, data loss, concurrency, and API contract issues.
3. Run focused tests or static checks when they are available and safe.
4. Report findings with file locations and concrete failure modes.
5. Avoid style-only findings unless they materially affect maintenance or correctness.
