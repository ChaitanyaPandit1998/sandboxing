---
name: git-change-hygiene
description: Prepare narrow, reviewable Git changes and commit messages. Use when editing repositories, preparing PRs, or summarizing a diff; do not commit or push unless requested.
---

# Git change hygiene

## Workflow
1. Inspect status before editing; preserve pre-existing user changes and untracked files.
2. Keep each change aligned with one clear objective. Avoid whitespace-only churn and generated artifacts unless required.
3. Review `git diff` for unintended edits, stale debug statements, credentials, and oversized files.
4. Run relevant checks before proposing a commit.
5. If asked for a commit, stage only intended paths and use a concise imperative message describing behavior, not internal implementation.
6. If asked for a PR summary, include motivation, approach, tests, risks, and migration notes.

## Guardrails
Never run destructive Git commands (`reset --hard`, broad `clean`, force-push) to solve a problem. Do not overwrite existing user work. Do not push or open external PRs without user authorization.
