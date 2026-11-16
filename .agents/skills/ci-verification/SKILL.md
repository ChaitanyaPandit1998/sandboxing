---
name: ci-verification
description: Run and report build, formatter, lint, tests, type checks, and security checks before declaring changes complete. Use as a final verification step after code modifications.
---

# CI and local verification

## Workflow
1. Detect the repository's canonical build/test commands from manifests, Makefile, CI workflows, or docs; do not invent successful runs.
2. Check the working-tree diff and ensure no unrelated files or secrets were introduced.
3. Run targeted tests first, then broader tests, formatter/linter, type checking, build, and relevant security checks if available and reasonable.
4. If a command fails, classify: introduced defect, pre-existing failure, environment limitation, or flaky behavior. Fix introduced defects and rerun.
5. Verify generated code and schema changes are synchronized with their sources.
6. Report each command and outcome (pass/fail/not run) plus any remaining risks.

## Completion contract
- State what changed and why.
- State exact checks executed, with results.
- Explicitly identify checks not run and the reason.
- Do not report success based solely on code inspection.

## Safety
Do not execute unknown project scripts with destructive effects without inspecting them. Never deploy or push unless asked.
