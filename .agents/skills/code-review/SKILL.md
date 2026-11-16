---
name: code-review
description: Review a diff or pull request for correctness, regressions, maintainability, and test gaps. Use when asked to review changes; do not silently modify code in review-only mode.
---

# Code review

## Workflow
1. Read repository guidance, change intent, and the actual diff; inspect surrounding code and tests for context.
2. Prioritize correctness, data loss, authorization, concurrency, compatibility, performance regressions, and missing verification.
3. For each finding, verify it against the affected behavior and cite the exact file and line range when possible.
4. Classify impact: critical (security/data loss), high (major broken behavior), medium (meaningful bug), low (minor maintainability).
5. Avoid subjective style comments unless they contradict explicit project standards or impair clarity.
6. Separate confirmed defects from questions and optional improvements.
7. Report any commands/tests run and note review scope limits.

## Output format
- Findings first, ordered by severity: `severity — file:line — issue — scenario — proposed fix`.
- Then outstanding questions and validation summary.
- If none found: state 'No actionable findings' and disclose remaining test/review gaps.

## Boundaries
Do not claim code is safe or bug-free; no production-changing operations during review.
