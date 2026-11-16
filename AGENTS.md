# Development log maintenance

For each meaningful implementation, documentation, or validation batch, update the root `DEVLOG.md` with the change, checks actually run, relevant failures/limitations, evidence links, and next step.

Use actual ISO 8601 timestamps in Asia/Kolkata (`+05:30`). Distinguish commit timestamps from test execution times; mark historical entries date-only when exact execution times are unavailable. Keep uncommitted/pushed status accurate and never include credentials, login codes, private keys, auth files, or private prompts.

Preserve existing historical entries; add corrections or follow-ups when evidence changes. A batch's own log update does not require a separate recursive log entry.

# Coding skills

The user-provided coding skills are installed under `.agents/skills/` for this repository. Read the relevant `SKILL.md` before applying it, and announce the selected skills briefly when first used. Select the skills needed for the task; do not load every skill for every edit. User instructions and higher-priority instructions take precedence over these templates.

| Task | Skills to apply |
|---|---|
| Substantial feature or multi-file change | [implementation-planning](.agents/skills/implementation-planning/SKILL.md), [coding-standards](.agents/skills/coding-standards/SKILL.md) |
| Behavior change or regression | [unit-integration-testing](.agents/skills/unit-integration-testing/SKILL.md), [test-driven-development](.agents/skills/test-driven-development/SKILL.md) where a meaningful deterministic regression test is appropriate |
| Unexpected failure | [systematic-debugging](.agents/skills/systematic-debugging/SKILL.md) |
| Authorization, sandbox boundaries, secrets, files, or external input | [secure-coding](.agents/skills/secure-coding/SKILL.md) |
| HTTP endpoints or service contracts | [api-contract-design](.agents/skills/api-contract-design/SKILL.md) |
| SQLite schema, migrations, or persistent data | [database-change-safety](.agents/skills/database-change-safety/SKILL.md) |
| Session lifecycle, PTYs, threads, retries, or shared state | [concurrency-reliability](.agents/skills/concurrency-reliability/SKILL.md) |
| Structural cleanup | [behavior-preserving-refactoring](.agents/skills/behavior-preserving-refactoring/SKILL.md) |
| Logs, metrics, traces, or alerts | [observability](.agents/skills/observability/SKILL.md) |
| Latency, capacity, or resource optimization | [performance-profiling](.agents/skills/performance-profiling/SKILL.md) |
| Verification and final diff review | [ci-verification](.agents/skills/ci-verification/SKILL.md), [git-change-hygiene](.agents/skills/git-change-hygiene/SKILL.md) |
| Review-only request | [code-review](.agents/skills/code-review/SKILL.md); report actionable findings without silently changing code |

Use the repository's existing commands and conventions. Match verification to the change: documentation and instruction-only edits need link/content/diff checks, not new runtime tests. Preserve unrelated work, and commit or push only when requested. Report what succeeded, what failed or remains unverified, and the next step. Skill adoption is workflow guidance, not evidence that existing code has passed review or security validation.
